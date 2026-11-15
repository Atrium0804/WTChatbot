"""Configuratie via environment variables.

Secrets (MISTRAL_API_KEY) staan alleen in .env op de server — nooit in git.
Zonder MISTRAL_API_KEY/MISTRAL_AGENT_ID draait de app in stub-mode (offline
development en tests).

Laadt `.env` (override=False): de environment wint, zodat docker/CI env-vars
direct kunnen injecteren.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent


load_dotenv()

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_AGENT_ID = os.environ.get("MISTRAL_AGENT_ID", "")
MISTRAL_CONVERSATIONS_URL = os.environ.get(
    "MISTRAL_CONVERSATIONS_URL", "https://api.mistral.ai/v1/conversations"
)
# Chat Completions API voor de light-model intake (#91)
MISTRAL_CHAT_COMPLETIONS_URL = os.environ.get(
    "MISTRAL_CHAT_COMPLETIONS_URL", "https://api.mistral.ai/v1/chat/completions"
)

# Expert-agent-ids voor direct-to-expert (#88/#91); leeg = niet
# geconfigureerd, dan start de conversatie altijd bij de router.
MISTRAL_AGENT_ID_KNWU = os.environ.get("MISTRAL_AGENT_ID_KNWU", "")
MISTRAL_AGENT_ID_REGIO = os.environ.get("MISTRAL_AGENT_ID_REGIO", "")
MISTRAL_AGENT_ID_CLUB = os.environ.get("MISTRAL_AGENT_ID_CLUB", "")
MISTRAL_AGENT_ID_ARCHIEF = os.environ.get("MISTRAL_AGENT_ID_ARCHIEF", "")
EXPERT_AGENT_IDS = {
    "knwu": MISTRAL_AGENT_ID_KNWU,
    "regio": MISTRAL_AGENT_ID_REGIO,
    "club": MISTRAL_AGENT_ID_CLUB,
    "archief": MISTRAL_AGENT_ID_ARCHIEF,
}

# Light-model intake (#91): klein model, drempel voor direct-to-expert.
MISTRAL_INTAKE_MODEL = os.environ.get("MISTRAL_INTAKE_MODEL", "mistral-small-latest")
INTAKE_TIMEOUT = int(os.environ.get("INTAKE_TIMEOUT", "30"))
INTAKE_CONFIDENCE_THRESHOLD = float(os.environ.get("INTAKE_CONFIDENCE_THRESHOLD", "0.8"))

# Prompt caching aan (#88 besluit 6): gecachte input kost 10%.
PROMPT_CACHE_KEY = os.environ.get("PROMPT_CACHE_KEY", "wtchatbot-v1")

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "wtchat.db"))
LOCAL_DEBUG_TRACES = os.environ.get("LOCAL_DEBUG_TRACES", "").lower() in ("1", "true")

MAX_QUESTION_LENGTH = int(os.environ.get("MAX_QUESTION_LENGTH", "1000"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "20"))
RATE_WINDOW_SECONDS = 3600
FEEDBACK_RETENTION_DAYS = int(os.environ.get("FEEDBACK_RETENTION_DAYS", "30"))
# Bij duim-omlaag slaan we de laatste FEEDBACK_HISTORY_TURNS turns (vraag/antwoord)
# op als feedbackgeschiedenis, naast de losse question/answer-kolommen (laatste turn).
FEEDBACK_HISTORY_TURNS = int(os.environ.get("FEEDBACK_HISTORY_TURNS", "10"))
# Max tekens per opgeslagen tekstveld (toelichting én per turn in de feedbackgeschiedenis).
FEEDBACK_MAX_TEXT_LENGTH = int(os.environ.get("FEEDBACK_MAX_TEXT_LENGTH", "2000"))

# Iframe-embed is post-MVP: 'self' volstaat. Post-MVP verbreden naar de
# clubsite-origin (frame-ancestors 'self' https://wtcwoerden.nl ...) en geen
# X-Frame-Options sturen — zie issue #14.
FRAME_ANCESTORS = os.environ.get("FRAME_ANCESTORS", "'self'")
