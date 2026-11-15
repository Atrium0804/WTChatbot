"""Light-model intake (#91): één kleine LLM-call per bericht.

De intake classificeert het bericht als JSON via de Chat Completions API
(mistral-small-latest; de HTTP-call zit in de dunne API-laag
mistral_client.chat_completion): intentie, domein, discipline, geboortejaar
en confidence. Samen met de deterministische regex-lookup
(lookups.match_lookup) bepaalt decide_route() de route van het bericht:

- "bypass": pure lookup met complete data -> direct app-antwoord uit
  knwu_categories.json, de Mistral-conversation start niet eens (#88);
- "direct": domein bekend én confidence >= drempel -> direct-to-expert
  (MISTRAL_AGENT_ID_<DOMEIN>), de router-call wordt bespaard (#88/#91);
- "router": alles anders -> de router-agent als voordeur.

Bij een intake-fout is de fallback altijd de router (veilig).

De intake-prompt staat in een apart bestand (prompts/intake-system.md),
volgens CODING_PRINCIPLES.md ("prompts staan in aparte bestanden").
"""

import json
import logging
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path

import requests

import lookups
import mistral_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "intake-system.md"


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    """Lees de intake-prompt uit het aparte promptbestand (eenmalig)."""
    return PROMPT_PATH.read_text(encoding="utf-8")

FALLBACK: dict = {
    "intentie": "onbekend",
    "domein": "onbekend",
    "discipline": "onbekend",
    "geboortejaar": None,
    "leeftijd": None,
    "confidence": 0.0,
}

DOMAINS = ("knwu", "regio", "club", "archief")


def _normalize(data: dict) -> dict:
    """Zet de ruwe JSON van het model om in het vaste intake-schema."""
    result = dict(FALLBACK)
    if not isinstance(data, dict):
        return result
    intentie = str(data.get("intentie") or "onbekend").lower()
    result["intentie"] = intentie if intentie in ("lookup", "regelgeving", "verheldering", "onbekend") else "onbekend"
    domein = str(data.get("domein") or "onbekend").lower()
    result["domein"] = domein if domein in DOMAINS else "onbekend"
    discipline = str(data.get("discipline") or "onbekend").lower()
    result["discipline"] = discipline if discipline in ("weg", "veld") else "onbekend"
    for key in ("geboortejaar", "leeftijd"):
        value = data.get(key)
        result[key] = int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    try:
        result["confidence"] = max(0.0, min(1.0, float(data.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        result["confidence"] = 0.0
    return result


def classify_message(
    *,
    api_key: str,
    base_url: str,
    model: str,
    message: str,
    timeout: int = 30,
    on_fallback: Callable[[str], None] | None = None,
) -> dict:
    """Eén call via de dunne API-laag (mistral_client.chat_completion); geef het intake-schema.

    Bij elke fout (netwerk, HTTP, ongeldige JSON) loggen en de veilige
    fallback teruggeven: domein onbekend, confidence 0 — de route wordt
    dan altijd "router".
    """
    try:
        content = mistral_client.chat_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=_system_prompt(),
            message=message,
            timeout=timeout,
        )
        return _normalize(json.loads(content))
    except Exception as exc:
        reason = "intake_error"
        cause: BaseException | None = exc
        while cause is not None:
            if isinstance(cause, requests.HTTPError) and cause.response is not None:
                reason = f"http_{cause.response.status_code}"
                break
            if isinstance(cause, requests.Timeout):
                reason = "timeout"
                break
            if isinstance(cause, json.JSONDecodeError):
                reason = "invalid_json"
                break
            cause = cause.__cause__
        logger.warning("Intake-call mislukt (%s); val terug op de router", reason)
        if on_fallback is not None:
            on_fallback(reason)
        return dict(FALLBACK)


def decide_route(
    *,
    message: str,
    today: date,
    rules: dict,
    intake_result: dict,
    expert_agent_ids: dict[str, str],
    threshold: float,
) -> dict:
    """Route-beslissing per bericht (#91): bypass | direct | router.

    `expert_agent_ids` mapt domein -> MISTRAL_AGENT_ID_<DOMEIN> (leeg =
    niet geconfigureerd -> dan kan er geen direct-to-expert plaatsvinden).
    """
    lookup = lookups.match_lookup(message, today, rules, extra=intake_result)
    if lookup:
        return {"route": "bypass", "lookup": lookup, "intake": intake_result}
    domein = str(intake_result.get("domein") or "onbekend")
    confidence = float(intake_result.get("confidence") or 0.0)
    agent_id = expert_agent_ids.get(domein, "")
    if agent_id and confidence >= threshold:
        return {
            "route": "direct",
            "agent_id": agent_id,
            "domein": domein,
            "intake": intake_result,
        }
    return {"route": "router", "intake": intake_result}
