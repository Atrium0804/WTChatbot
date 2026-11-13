"""WTChatbot MVP — FastAPI-proxy + static chat-UI.

Draait op de VPS achter Caddy (automatische HTTPS, zie Caddyfile/docker-compose.yml).
De Mistral API-key staat alleen in .env op de server. Zonder
MISTRAL_API_KEY/MISTRAL_AGENT_ID draait de app in stub-mode (duidelijk gemarkeerd)
— handig voor offline development en tests.

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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config
import context
import knwu_categories
import mistral_client
import store

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

    app = FastAPI(title="WTChatbot")
    # In-memory state: conversaties, feedbackgeschiedenis per conversatie (rolling
    # window van de laatste FEEDBACK_HISTORY_TURNS turns, voor feedback-koppeling),
    # rate-limit buckets.
    state: dict = {"conversations": {}, "history": {}, "buckets": {}, "jobs": {}}

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
        if request.method == "GET":
            if path in ("/", "/sw.js", "/manifest.webmanifest") or path.endswith(".html"):
                response.headers["Cache-Control"] = "no-cache"
            elif path.startswith("/icons/") or path.rsplit(".", 1)[-1].lower() in (
                "png", "jpg", "jpeg", "webp", "svg", "ico", "gif",
            ):
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    async def _run_chat_job(
        job_id: str,
        conversation_id: str,
        message: str,
        context_message: str,
        mistral_conv_id: str | None,
    ) -> None:
        """Background task (#85): draait de Mistral-call off-loop en slaat het
        resultaat op in de job-state. De /chat-status endpoint leest die state."""
        job = state["jobs"][job_id]
        job["status"] = "working"
        job["phase"] = "Wielie denkt na…"
        try:
            new_conv_id, answer = await run_in_threadpool(
                mistral_client.answer_question,
                api_key=config.MISTRAL_API_KEY,
                agent_id=config.MISTRAL_AGENT_ID,
                base_url=config.MISTRAL_CONVERSATIONS_URL,
                message=context_message,
                conversation_id=mistral_conv_id or None,
                metadata={"app_conversation_id": conversation_id},
            )
            state["conversations"][conversation_id] = new_conv_id
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
            job["status"] = "done"
            job["phase"] = "Klaar"
            job["answer"] = answer
            job["conversation_id"] = conversation_id
        except Exception as exc:
            job["status"] = "error"
            job["phase"] = "Fout"
            job["error"] = f"Er ging iets mis bij het ophalen van het antwoord. Probeer het opnieuw. ({exc})"

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
        if config.MISTRAL_API_KEY and config.MISTRAL_AGENT_ID:
            # #85: 202 + job-id; de Mistral-call draait in een background task.
            mistral_conv_id = state["conversations"].get(conversation_id)
            context_lines = context.build_context_lines(
                message,
                today(),
                category_rules,
                new_conversation=not mistral_conv_id,
                language_level=payload.language_level,
            )
            job_id = uuid.uuid4().hex
            state["jobs"][job_id] = {
                "status": "pending",
                "phase": "Wielie denkt na…",
                "created_at": time.time(),
            }
            asyncio.create_task(
                _run_chat_job(
                    job_id,
                    conversation_id,
                    message,
                    context.add_context(message, context_lines),
                    mistral_conv_id,
                )
            )
            return JSONResponse(
                {"job_id": job_id, "conversation_id": conversation_id},
                status_code=202,
            )
        # stub-mode: synchroon antwoord (handig voor offline development en tests)
        answer = stub_answer(message)
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
        return {"conversation_id": conversation_id, "answer": answer}

    @app.get("/chat/status/{job_id}")
    async def chat_status(job_id: str):
        """#85: poll-endpoint voor de achtergrond-job van /chat. Geeft status +
        phase terug; bij 'done' ook het antwoord, bij 'error' de foutmelding."""
        job = state["jobs"].get(job_id)
        if not job:
            return JSONResponse({"error": "Onbekende job."}, status_code=404)
        result: dict = {"status": job["status"], "phase": job.get("phase", "")}
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
