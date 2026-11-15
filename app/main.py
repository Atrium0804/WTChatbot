"""WTChatbot MVP — FastAPI-proxy + static chat-UI.

Draait op de VPS achter Caddy (automatische HTTPS, zie Caddyfile/docker-compose.yml).
De Mistral API-key staat alleen in .env op de server. Zonder
MISTRAL_API_KEY/MISTRAL_AGENT_ID draait de app in stub-mode (duidelijk gemarkeerd)
— handig voor offline development en tests.

Flow per bericht (#88/#91/#93): deterministische lookup (lookups.py) -> bij een
pure feitelijke vraag direct app-antwoord zonder LLM-call; anders 202 + background
job met light-model intake (intake.py), route direct-to-expert of router, en een
streaming Mistral-call wier SSE-events de fase in /chat/status voeden (phases.py).

Run:  uvicorn main:app --host 0.0.0.0 --port 8000   (vanuit app/)
"""

import asyncio
import re
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import date
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config
import context
import intake
import knwu_categories
import lookups
import mistral_client
import phases
import store
import tracing

STATIC_DIR = config.BASE_DIR / "static"


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=100_000)  # harde limiet checkt /chat zelf
    conversation_id: str = ""
    client_id: str = ""  # anonieme client-ID (random UUID), puur voor de rate limiter — geen IP-logging
    language_level: str = ""  # "B1" (standaard) of "B2"; ongeldige waarde wordt B1 (zie context.normalize_language_level)


class FeedbackRequest(BaseModel):
    conversation_id: str = ""
    rating: str  # "positive" | "negative"
    text: str = ""


def rate_limit_ok(buckets: dict[str, list[float]], key: str, limit: int, window: int) -> bool:
    """In-memory rate limiter: maximaal `limit` requests per `window` seconden per key."""
    now = time.time()
    hits = [t for t in buckets.get(key, []) if now - t < window]
    buckets[key] = hits
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True


BRONCONFLICT_RE = re.compile(r"^\s*\[BRONCONFLICT\]\s*(.+?)\s*$", re.MULTILINE)


def split_bronconflict_markers(answer: str) -> tuple[str, list[str]]:
    """Split [BRONCONFLICT]-markerregels van het antwoord (#47).

    Geef (antwoord zonder markerregels, lijst marker-inhoud per regel). De
    marker is een beheerderssignaal en wordt vóór de gebruiker het ziet uit
    het antwoord én de feedbackgeschiedenis gehaald.
    """
    markers = [m.group(1) for m in BRONCONFLICT_RE.finditer(answer)]
    if not markers:
        return answer, []
    stripped = BRONCONFLICT_RE.sub("", answer)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return stripped, markers


def stub_answer(message: str) -> str:
    return (
        "STUB (geen MISTRAL_API_KEY/MISTRAL_AGENT_ID geconfigureerd): "
        f'dit zou een antwoord zijn op: "{message[:120]}".\n\n'
        "Bron: stub (geen echte bron geraadpleegd)."
    )


def create_app(
    db_path: Optional[str] = None,
    today: Callable[[], date] = context.today_in_netherlands,
) -> FastAPI:
    db = db_path or config.DATABASE_PATH
    store.init_db(db)
    store.purge_old(db, config.FEEDBACK_RETENTION_DAYS)
    category_rules = knwu_categories.load_rules()
    # #88/#91: expert-ids voor direct-to-expert; agent-id -> naam voor de fase-mapping
    expert_agent_ids = {k: v for k, v in config.EXPERT_AGENT_IDS.items() if v}
    agent_names = {agent_id: f"{domein}-agent" for domein, agent_id in expert_agent_ids.items()}
    if config.MISTRAL_AGENT_ID:
        agent_names[config.MISTRAL_AGENT_ID] = "router-agent"

    app = FastAPI(title="WTChatbot")
    # In-memory state: conversaties, feedbackgeschiedenis per conversatie (rolling
    # window van de laatste FEEDBACK_HISTORY_TURNS turns, voor feedback-koppeling),
    # rate-limit buckets.
    state: dict = {"conversations": {}, "history": {}, "buckets": {}, "jobs": {}}
    traces = tracing.TraceStore(enabled=config.LOCAL_DEBUG_TRACES)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        # Let op: expres GEEN X-Frame-Options. Post-MVP iframe-embed: FRAME_ANCESTORS
        # verbreden naar de clubsite-origin (zie config.py, issue #14).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            # worker-src/manifest-src voor de PWA (service worker + manifest, issue #35)
            "worker-src 'self'; "
            "manifest-src 'self'; "
            f"frame-ancestors {config.FRAME_ANCESTORS}; "
            "base-uri 'self'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Cache-Control: API-antwoorden nooit cachen; html/manifest/sw.js altijd
        # revalideren (no-cache); statische assets (icons, afbeeldingen) kort cachen.
        path = request.url.path
        if path == "/debug" or path.startswith("/debug/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = response.headers[
                "Content-Security-Policy"
            ].replace(f"frame-ancestors {config.FRAME_ANCESTORS}", "frame-ancestors 'none'")
            response.headers["X-Frame-Options"] = "DENY"
        if request.method == "GET":
            if path in ("/", "/sw.js", "/manifest.webmanifest") or path.endswith(".html"):
                response.headers["Cache-Control"] = "no-cache"
            elif path.startswith("/icons/") or path.rsplit(".", 1)[-1].lower() in (
                "png", "jpg", "jpeg", "webp", "svg", "ico", "gif",
            ):
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    def _record_turn(conversation_id: str, message: str, answer: str) -> str:
        """[BRONCONFLICT]-markers als feedback opslaan en de turn in de
        feedbackgeschiedenis bewaren; geef het antwoord zonder markers terug."""
        answer, bronconflicts = split_bronconflict_markers(answer)
        for marker in bronconflicts:
            store.save_feedback(
                db,
                rating="bronconflict",
                conversation_id=conversation_id,
                text=marker[: config.FEEDBACK_MAX_TEXT_LENGTH],
            )
        turns = state["history"].setdefault(
            conversation_id, deque(maxlen=config.FEEDBACK_HISTORY_TURNS)
        )
        turns.append({"question": message, "answer": answer})
        return answer

    def _direct_response(
        conversation_id: str, message: str, answer: str, trace: tracing.Trace
    ) -> JSONResponse:
        """Synchroon 200-antwoord: stub-mode óf deterministische bypass (#91)."""
        answer = _record_turn(conversation_id, message, answer)
        trace.record("done")
        return JSONResponse(
            {"conversation_id": conversation_id, "answer": answer},
            headers={"X-Trace-ID": trace.id},
        )

    async def _run_chat_job(
        job_id: str,
        conversation_id: str,
        message: str,
        lookup_message: str,
        context_message: str,
        mistral_conv_id: str | None,
        today_date: date,
        language_level: str,
        trace: tracing.Trace,
    ) -> None:
        """Background task (#85 + #91/#93): light intake + route + streaming
        Mistral-call off-loop; SSE-events worden omgezet in job["phase"].
        De /chat/status endpoint leest die state."""
        job = state["jobs"][job_id]
        job["status"] = "working"
        job["phase"] = phases.PHASE_LEES
        try:
            intake_started = time.monotonic()
            fallback_reason = ""

            def on_intake_fallback(reason: str) -> None:
                nonlocal fallback_reason
                fallback_reason = reason

            # #91: light intake (1 kleine call) + regex-lookup bepalen de route
            intake_result = await run_in_threadpool(
                intake.classify_message,
                api_key=config.MISTRAL_API_KEY,
                base_url=config.MISTRAL_CHAT_COMPLETIONS_URL,
                model=config.MISTRAL_INTAKE_MODEL,
                message=lookup_message,
                timeout=config.INTAKE_TIMEOUT,
                on_fallback=on_intake_fallback,
            )
            trace.record(
                "intake",
                confidence=intake_result["confidence"],
                duration_ms=round((time.monotonic() - intake_started) * 1000, 1),
                reason=fallback_reason or "classified",
            )
            route = intake.decide_route(
                message=lookup_message,
                today=today_date,
                rules=category_rules,
                intake_result=intake_result,
                expert_agent_ids=expert_agent_ids,
                threshold=config.INTAKE_CONFIDENCE_THRESHOLD,
            )
            job["route"] = route["route"] + (
                f"-{route['domein']}" if route["route"] == "direct" else ""
            )
            route_reason = "intake_lookup" if route["route"] == "bypass" else "confident_domain"
            if route["route"] == "router":
                if fallback_reason:
                    route_reason = fallback_reason
                elif intake_result["domein"] not in expert_agent_ids:
                    route_reason = "expert_not_configured"
                else:
                    route_reason = "low_confidence"
            trace.record("route", route=job["route"], reason=route_reason)
            if route["route"] == "bypass":
                # deterministische lookup met complete data: direct app-antwoord,
                # de Mistral-conversation start niet (#88/#91)
                job["phase"] = phases.PHASE_BEREKEN
                answer = lookups.render_lookup_answer(
                    route["lookup"], lookup_message, category_rules, today_date, language_level
                )
                new_conv_id = mistral_conv_id or ""
            else:
                agent_id = route.get("agent_id") or config.MISTRAL_AGENT_ID
                current_agent = agent_names.get(agent_id, "")
                job["phase"] = phases.fase_voor_startagent(current_agent)
                trace.record(
                    "agent_request",
                    agent=current_agent or "unknown",
                    reason="continue_conversation" if mistral_conv_id else "new_conversation",
                )
                observed_agent = "" if mistral_conv_id else current_agent

                def on_event(event: str, data: dict) -> None:
                    nonlocal current_agent, observed_agent
                    event_agent_id = data.get("agent_id")
                    if isinstance(event_agent_id, str) and event_agent_id in agent_names:
                        observed_agent = agent_names[event_agent_id]
                    trace.stream_event(event, data, observed_agent)
                    if event == "agent.handoff.done":
                        next_agent = data.get("next_agent_name")
                        observed_agent = (
                            next_agent if isinstance(next_agent, str) and next_agent in tracing.AGENTS else ""
                        )
                    elif event == "message.output.done":
                        trace.record("agent_output", agent=observed_agent or "unknown")
                    mapping = phases.phase_for_event(event, data, current_agent)
                    if mapping is not None:
                        new_phase, current_agent = mapping
                        job["phase"] = new_phase

                try:
                    new_conv_id, answer = await run_in_threadpool(
                        mistral_client.stream_answer,
                        api_key=config.MISTRAL_API_KEY,
                        agent_id=agent_id,
                        base_url=config.MISTRAL_CONVERSATIONS_URL,
                        message=context_message,
                        conversation_id=mistral_conv_id or None,
                        metadata={"app_conversation_id": conversation_id},
                        prompt_cache_key=config.PROMPT_CACHE_KEY,
                        on_event=on_event,
                    )
                except mistral_client.StreamStartError:
                    # stream startte niet: val terug op de non-streaming call (#93)
                    job["phase"] = phases.PHASE_OPSTELLEN
                    trace.record("stream_fallback", reason="stream_start_error")
                    new_conv_id, answer = await run_in_threadpool(
                        mistral_client.answer_question,
                        api_key=config.MISTRAL_API_KEY,
                        agent_id=agent_id,
                        base_url=config.MISTRAL_CONVERSATIONS_URL,
                        message=context_message,
                        conversation_id=mistral_conv_id or None,
                        metadata={"app_conversation_id": conversation_id},
                        prompt_cache_key=config.PROMPT_CACHE_KEY,
                    )
            if not answer.strip():
                # bv. een agent die alleen "thinking" teruggeeft: liever een foutmelding dan een leeg antwoord
                raise RuntimeError("het model gaf een leeg antwoord")
            if new_conv_id:
                state["conversations"][conversation_id] = new_conv_id
            answer = _record_turn(conversation_id, message, answer)
            job["status"] = "done"
            job["phase"] = phases.PHASE_KLAAR
            job["answer"] = answer
            job["conversation_id"] = conversation_id
            trace.record("done")
        except asyncio.CancelledError:
            trace.record("cancelled", reason="job_cancelled")
            raise
        except Exception as exc:
            job["status"] = "error"
            job["phase"] = phases.PHASE_FOUT
            job["error"] = f"Er ging iets mis bij het ophalen van het antwoord. Probeer het opnieuw. ({exc})"
            trace.record("error", reason=type(exc).__name__)

    @app.post("/chat")
    async def chat(payload: ChatRequest):
        message = payload.message.strip()
        if not message:
            return JSONResponse({"error": "Stuur een vraag mee."}, status_code=400)
        if len(message) > config.MAX_QUESTION_LENGTH:
            return JSONResponse(
                {"error": f"Je vraag is te lang (maximaal {config.MAX_QUESTION_LENGTH} tekens)."},
                status_code=413,
            )
        if not rate_limit_ok(
            state["buckets"],
            payload.client_id.strip() or "unknown",
            config.RATE_LIMIT_PER_HOUR,
            config.RATE_WINDOW_SECONDS,
        ):
            return JSONResponse(
                {"error": "Te veel vragen in één uur. Probeer het later opnieuw."},
                status_code=429,
            )
        conversation_id = payload.conversation_id.strip() or uuid.uuid4().hex
        trace = traces.start(conversation_id)
        today_date = today()
        previous_messages = [turn["question"] for turn in state["history"].get(conversation_id, [])]
        lookup_message = lookups.resolve_lookup_message(
            message, previous_messages, today_date, category_rules
        )
        # #91: pure lookup met complete data -> direct app-antwoord (0 LLM-calls,
        # géén job/fase — de snelheid is zo direct zichtbaar), ook midden in een
        # bestaand gesprek
        lookup = lookups.match_lookup(lookup_message, today_date, category_rules)
        if lookup:
            trace.record("route", route="bypass", reason="regex_lookup")
            answer = lookups.render_lookup_answer(
                lookup, lookup_message, category_rules, today_date, payload.language_level
            )
            return _direct_response(conversation_id, message, answer, trace)
        if config.MISTRAL_API_KEY and config.MISTRAL_AGENT_ID:
            # #85: 202 + job-id; intake + Mistral-call draaien in een background task.
            mistral_conv_id = state["conversations"].get(conversation_id)
            context_lines = context.build_context_lines(
                lookup_message,
                today_date,
                category_rules,
                new_conversation=not mistral_conv_id,
                language_level=payload.language_level,
            )
            job_id = uuid.uuid4().hex
            state["jobs"][job_id] = {
                "status": "pending",
                "phase": phases.PHASE_LEES,
                "created_at": time.time(),
            }
            asyncio.create_task(
                _run_chat_job(
                    job_id,
                    conversation_id,
                    message,
                    lookup_message,
                    context.add_context(lookup_message, context_lines),
                    mistral_conv_id,
                    today_date,
                    payload.language_level,
                    trace,
                )
            )
            return JSONResponse(
                {"job_id": job_id, "conversation_id": conversation_id},
                status_code=202,
                headers={"X-Trace-ID": trace.id},
            )
        # stub-mode: synchroon antwoord (handig voor offline development en tests)
        trace.record("route", route="stub", reason="mistral_not_configured")
        return _direct_response(conversation_id, message, stub_answer(message), trace)

    @app.get("/debug")
    async def debug_panel(request: Request):
        if not tracing.local_debug_allowed(request, config.LOCAL_DEBUG_TRACES):
            return JSONResponse({"error": "Niet gevonden."}, status_code=404)
        return FileResponse(config.BASE_DIR / "debug.html")

    @app.get("/debug/traces")
    async def debug_traces(request: Request):
        if not tracing.local_debug_allowed(request, config.LOCAL_DEBUG_TRACES):
            return JSONResponse({"error": "Niet gevonden."}, status_code=404)
        return {"traces": traces.snapshot()}

    @app.get("/chat/status/{job_id}")
    async def chat_status(job_id: str):
        """#85: poll-endpoint voor de achtergrond-job van /chat. Geeft status +
        phase terug; bij 'done' ook het antwoord, bij 'error' de foutmelding."""
        job = state["jobs"].get(job_id)
        if not job:
            return JSONResponse({"error": "Onbekende job."}, status_code=404)
        result: dict = {"status": job["status"], "phase": job.get("phase", "")}
        if job.get("route"):
            result["route"] = job["route"]
        if job["status"] == "done":
            result["answer"] = job.get("answer", "")
            result["conversation_id"] = job.get("conversation_id", "")
        elif job["status"] == "error":
            result["error"] = job.get("error", "Er ging iets mis.")
        return result

    @app.post("/feedback")
    async def feedback(payload: FeedbackRequest):
        """Content wordt ALLEEN opgeslagen bij duim-omlaag: de feedbackgeschiedenis
        (laatste FEEDBACK_HISTORY_TURNS turns, oudste eerst) plus de laatste turn
        los in question/answer en de toelichting. Bij duim-omhoog alleen een teller."""
        if payload.rating not in ("positive", "negative"):
            return JSONResponse(
                {"error": "rating moet 'positive' of 'negative' zijn."}, status_code=400
            )
        if payload.rating == "negative":
            turns = list(state["history"].get(payload.conversation_id, []))[
                -config.FEEDBACK_HISTORY_TURNS:
            ]
            history = [
                {
                    "question": t["question"],
                    "answer": t["answer"][: config.FEEDBACK_MAX_TEXT_LENGTH],
                }
                for t in turns
            ]
            last = turns[-1] if turns else {}
            store.save_feedback(
                db,
                rating="negative",
                conversation_id=payload.conversation_id,
                question=last.get("question", ""),
                answer=last.get("answer", "")[: config.FEEDBACK_MAX_TEXT_LENGTH],
                text=payload.text[: config.FEEDBACK_MAX_TEXT_LENGTH],
                history=history,
            )
        else:
            store.save_feedback(db, rating="positive")
        store.purge_old(db, config.FEEDBACK_RETENTION_DAYS)
        return {"ok": True}

    @app.get("/healthz")
    async def healthz():
        configured = bool(config.MISTRAL_API_KEY and config.MISTRAL_AGENT_ID)
        reachable = False
        if configured:
            # idem: blocking requests.get off-loop (#80)
            reachable = await run_in_threadpool(
                mistral_client.check_reachable,
                api_key=config.MISTRAL_API_KEY,
                base_url=config.MISTRAL_CONVERSATIONS_URL,
            )
        return {
            "status": "ok",
            "mistral_configured": configured,
            "mistral_reachable": reachable,
        }

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
