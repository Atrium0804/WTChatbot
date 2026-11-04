"""WTChatbot MVP — FastAPI-proxy + static chat-UI.

Draait op de VPS achter Caddy (automatische HTTPS, zie Caddyfile/docker-compose.yml).
De Mistral API-key staat alleen in .env op de server. Zonder
MISTRAL_API_KEY/MISTRAL_AGENT_ID draait de app in stub-mode (duidelijk gemarkeerd)
— handig voor offline development en tests.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000   (vanuit app/)
"""

import time
import uuid
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import mistral_client
import store

STATIC_DIR = config.BASE_DIR / "static"


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=100_000)  # harde limiet checkt /chat zelf
    conversation_id: str = ""
    client_id: str = ""  # anonieme client-ID (random UUID), puur voor de rate limiter — geen IP-logging


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


def stub_answer(message: str) -> str:
    return (
        "STUB (geen MISTRAL_API_KEY/MISTRAL_AGENT_ID geconfigureerd): "
        f'dit zou een antwoord zijn op: "{message[:120]}".\n\n'
        "Bron: stub (geen echte bron geraadpleegd)."
    )


def create_app(db_path: Optional[str] = None) -> FastAPI:
    db = db_path or config.DATABASE_PATH
    store.init_db(db)
    store.purge_old(db, config.FEEDBACK_RETENTION_DAYS)

    app = FastAPI(title="WTChatbot")
    # In-memory state: conversaties, laatste uitwisseling (voor feedback-koppeling), rate-limit buckets.
    state: dict = {"conversations": {}, "last_exchange": {}, "buckets": {}}

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        # Let op: expres GEEN X-Frame-Options. Post-MVP iframe-embed: FRAME_ANCESTORS
        # verbreden naar de clubsite-origin (zie config.py, issue #14).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            f"frame-ancestors {config.FRAME_ANCESTORS}; "
            "base-uri 'self'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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
            mistral_conv_id = state["conversations"].get(conversation_id)
            try:
                mistral_conv_id, answer = mistral_client.answer_question(
                    api_key=config.MISTRAL_API_KEY,
                    agent_id=config.MISTRAL_AGENT_ID,
                    base_url=config.MISTRAL_CONVERSATIONS_URL,
                    message=message,
                    conversation_id=mistral_conv_id or None,
                )
            except Exception as exc:
                return JSONResponse(
                    {"error": f"Er ging iets mis bij het ophalen van het antwoord. Probeer het opnieuw. ({exc})"},
                    status_code=502,
                )
            state["conversations"][conversation_id] = mistral_conv_id
        else:
            answer = stub_answer(message)
        state["last_exchange"][conversation_id] = {"question": message, "answer": answer}
        return {"conversation_id": conversation_id, "answer": answer}

    @app.post("/feedback")
    async def feedback(payload: FeedbackRequest):
        """Content (vraag/antwoord) wordt ALLEEN opgeslagen bij duim-omlaag."""
        if payload.rating not in ("positive", "negative"):
            return JSONResponse(
                {"error": "rating moet 'positive' of 'negative' zijn."}, status_code=400
            )
        if payload.rating == "negative":
            exchange = state["last_exchange"].get(payload.conversation_id, {})
            store.save_feedback(
                db,
                rating="negative",
                conversation_id=payload.conversation_id,
                question=exchange.get("question", ""),
                answer=exchange.get("answer", ""),
                text=payload.text[:2000],
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
            reachable = mistral_client.check_reachable(
                api_key=config.MISTRAL_API_KEY, base_url=config.MISTRAL_CONVERSATIONS_URL
            )
        return {
            "status": "ok",
            "mistral_configured": configured,
            "mistral_reachable": reachable,
        }

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
