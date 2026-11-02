"""Configuratie via environment variables.

Secrets (MISTRAL_API_KEY) staan alleen in .env op de server — nooit in git.
Zonder MISTRAL_API_KEY/MISTRAL_AGENT_ID draait de app in stub-mode (offline
development en tests).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_AGENT_ID = os.environ.get("MISTRAL_AGENT_ID", "")
MISTRAL_CONVERSATIONS_URL = os.environ.get(
    "MISTRAL_CONVERSATIONS_URL", "https://api.mistral.ai/v1/conversations"
)

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "wtchat.db"))

MAX_QUESTION_LENGTH = int(os.environ.get("MAX_QUESTION_LENGTH", "1000"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "10"))
RATE_WINDOW_SECONDS = 3600
FEEDBACK_RETENTION_DAYS = int(os.environ.get("FEEDBACK_RETENTION_DAYS", "30"))

# Iframe-embed is post-MVP: 'self' volstaat. Post-MVP verbreden naar de
# clubsite-origin (frame-ancestors 'self' https://wtcwoerden.nl ...) en geen
# X-Frame-Options sturen — zie issue #14.
FRAME_ANCESTORS = os.environ.get("FRAME_ANCESTORS", "'self'")
