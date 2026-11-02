"""PROTOTYPE (issue #14) — wegwerp chat-UI + FastAPI-proxy voor WTChatbot.

Vraag die dit prototype beantwoordt: staat de clubsite (AllUnited,
wtcwoerden.nl) toe dat we de chatpagina via een iframe embedden (CSP
frame-ancestors / geen X-Frame-Options), en werkt een minimale responsive
chat-UI die de /chat-endpoint aanroept (ook op mobiel)?

DIT IS WEGWERPCODE — geen productie. Zie README.md in deze map.

Run:  uvicorn app:app --reload --port 8000   (vanuit deze map)
Env:  MISTRAL_API_KEY + MISTRAL_AGENT_ID (optioneel; zonder = stub-answers)
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
FEEDBACK_LOG = BASE_DIR / "feedback.log"  # PROTOTYPE, wipe me — gitignored

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.environ.get("MISTRAL_AGENT_ID")
MISTRAL_CONVERSATIONS_URL = "https://api.mistral.ai/v1/conversations"

MAX_QUESTION_LENGTH = 1000
RATE_LIMIT_PER_HOUR = 10
RATE_WINDOW_SECONDS = 3600
# Privacy-beslissing (HITL na #14): er worden GEEN IP-adressen gelogd.
# Rate limiting werkt in-memory per anonieme client-ID (random UUID, client-side).

# Clubsite-origins die ons mogen framen (zie ook Caddyfile in deze map).
FRAME_ANCESTORS = "'self' https://wtcwoerden.nl https://www.wtcwoerden.nl"

app = FastAPI(title="WTChatbot prototype (wegwerp, #14)")

# Alleen in-memory: een prototype persist niet (state rule van de prototype-skill).
conversations: dict[str, str] = {}  # eigen conversation_id -> Mistral conversation_id
last_exchange: dict[str, dict] = {}  # conversation_id -> {"question", "answer"} — alleen nodig om feedback te koppelen
rate_limit_buckets: dict[str, list[float]] = {}  # client_id -> timestamps


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Let op: expres GEEN X-Frame-Options — de clubsite moet ons mogen framen.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        f"frame-ancestors {FRAME_ANCESTORS}; "
        "base-uri 'self'; form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=100_000)  # harde limiet checkt /chat zelf
    conversation_id: str = ""
    client_id: str = ""  # anonieme client-ID (random UUID), puur voor de rate limiter


class FeedbackRequest(BaseModel):
    conversation_id: str = ""
    rating: str  # "positive" | "negative"
    text: str = ""


def rate_limit_ok(key: str) -> bool:
    now = time.time()
    hits = [t for t in rate_limit_buckets.get(key, []) if now - t < RATE_WINDOW_SECONDS]
    rate_limit_buckets[key] = hits
    if len(hits) >= RATE_LIMIT_PER_HOUR:
        return False
    hits.append(now)
    return True


def extract_text(outputs: list) -> str:
    texts = []
    for out in outputs:
        content = out.get("message", {}).get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    texts.append(chunk.get("text", ""))
    return "\n".join(texts)


def answer_question(message: str, conversation_id: str) -> str:
    """Stuur de vraag naar de Mistral-agent; stub als er geen key/agent is."""
    if not (MISTRAL_API_KEY and MISTRAL_AGENT_ID):
        return (
            "PROTOTYPE-stub: er is geen MISTRAL_API_KEY/MISTRAL_AGENT_ID configured, "
            f"dus dit is een canned antwoord op: \"{message[:120]}\".\n\n"
            "Bron: prototype-stub (geen echte bron geraadpleegd)."
        )
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    mistral_id = conversations.get(conversation_id)
    if mistral_id:
        resp = requests.post(
            f"{MISTRAL_CONVERSATIONS_URL}/{mistral_id}",
            headers=headers,
            json={"inputs": message},
            timeout=180,
        )
    else:
        resp = requests.post(
            MISTRAL_CONVERSATIONS_URL,
            headers=headers,
            json={"agent_id": MISTRAL_AGENT_ID, "inputs": message},
            timeout=180,
        )
    resp.raise_for_status()
    data = resp.json()
    new_id = data.get("conversation_id")
    if new_id:
        conversations[conversation_id] = new_id
    return extract_text(data.get("outputs", []))


@app.post("/chat")
async def chat(request: Request, payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        return JSONResponse({"error": "Stuur een vraag mee."}, status_code=400)
    if len(message) > MAX_QUESTION_LENGTH:
        return JSONResponse(
            {"error": f"Je vraag is te lang (maximaal {MAX_QUESTION_LENGTH} tekens)."},
            status_code=413,
        )
    if not rate_limit_ok(payload.client_id.strip() or "unknown"):
        return JSONResponse(
            {"error": "Te veel vragen in één uur. Probeer het later opnieuw."},
            status_code=429,
        )
    conversation_id = payload.conversation_id.strip() or uuid.uuid4().hex
    try:
        answer = answer_question(message, conversation_id)
    except Exception as exc:
        return JSONResponse(
            {"error": f"Er ging iets mis bij het ophalen van het antwoord ({exc}). Probeer het opnieuw."},
            status_code=502,
        )
    last_exchange[conversation_id] = {"question": message, "answer": answer}
    return {"conversation_id": conversation_id, "answer": answer}


@app.post("/feedback")
async def feedback(payload: FeedbackRequest):
    """Privacy-beslissing (HITL na #14): content wordt ALLEEN opgeslagen bij
    duim-omlaag. Bij duim-omhoog slaan we alleen een teller op (geen tekst)."""
    if payload.rating not in ("positive", "negative"):
        return JSONResponse({"error": "rating moet 'positive' of 'negative' zijn."}, status_code=400)
    timestamp = datetime.now(timezone.utc).isoformat()
    if payload.rating == "negative":
        exchange = last_exchange.get(payload.conversation_id, {})
        entry = {
            "timestamp": timestamp,
            "conversation_id": payload.conversation_id,
            "rating": payload.rating,
            "question": exchange.get("question", ""),
            "answer": exchange.get("answer", ""),
            "text": payload.text[:2000],
        }
    else:
        entry = {"timestamp": timestamp, "rating": payload.rating}
    with FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "mistral_configured": bool(MISTRAL_API_KEY and MISTRAL_AGENT_ID),
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
