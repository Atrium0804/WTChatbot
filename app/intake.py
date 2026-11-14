"""Light-model intake (#91): één kleine LLM-call per bericht.

De intake classificeert het bericht als JSON via de Chat Completions API
(mistral-small-latest): intentie, domein, discipline, geboortejaar en
confidence. Samen met de deterministische regex-lookup
(lookups.match_lookup) bepaalt decide_route() de route van het bericht:

- "bypass": pure lookup met complete data -> direct app-antwoord uit
  knwu_categories.json, de Mistral-conversation start niet eens (#88);
- "direct": domein bekend én confidence >= drempel -> direct-to-expert
  (MISTRAL_AGENT_ID_<DOMEIN>), de router-call wordt bespaard (#88/#91);
- "router": alles anders -> de router-agent als voordeur.

Bij een intake-fout is de fallback altijd de router (veilig).
"""

import json
from datetime import date

import requests

import lookups

INTAKE_SYSTEM_PROMPT = """Je bent de intake van de WTC-kennischatbot Wielie. Classificeer het bericht van de gebruiker en antwoord ALLEEN met een JSON-object:
{
  "intentie": "lookup" | "regelgeving" | "verheldering" | "onbekend",
  "domein": "knwu" | "regio" | "club" | "onbekend",
  "discipline": "weg" | "veld" | "baan" | "onbekend",
  "geboortejaar": <jaar als getal, of null>,
  "leeftijd": <leeftijd in jaren als getal, of null>,
  "confidence": <getal tussen 0.0 en 1.0>
}
- domein "knwu": nationale KNWU-zaken (Titel 20, Nationale Besluiten, licenties, verzekeringen, NK, verzet, leeftijdscategorie); "regio": MNC-wedstrijden in regio Midden; "club": WTC Woerden (ZMC, contributie, clubreglementen, jeugdsite).
- "intentie": "lookup" ALLEEN als de vraag puur een feitelijk lookup is (leeftijdscategorie, licentie, maximaal verzet, oude categorie-aanduiding) én alle benodigde gegevens in het bericht staan; anders "regelgeving" (er wordt naar een regel/feit in documenten gevraagd) of "verheldering" (gegevens ontbreken).
- discipline alleen als weg/veld/baan expliciet blijkt; geboortejaar/leeftijd alleen als ze expliciet in het bericht staan.
- confidence: hoe zeker je bent van domein én intentie samen (1.0 = volstrekt zeker).
"""

FALLBACK: dict = {
    "intentie": "onbekend",
    "domein": "onbekend",
    "discipline": "onbekend",
    "geboortejaar": None,
    "leeftijd": None,
    "confidence": 0.0,
}

DOMEINEN = ("knwu", "regio", "club", "archief")


def _normaliseer(data: dict) -> dict:
    """Zet de ruwe JSON van het model om in het vaste intake-schema."""
    result = dict(FALLBACK)
    if not isinstance(data, dict):
        return result
    intentie = str(data.get("intentie") or "onbekend").lower()
    result["intentie"] = intentie if intentie in ("lookup", "regelgeving", "verheldering", "onbekend") else "onbekend"
    domein = str(data.get("domein") or "onbekend").lower()
    result["domein"] = domein if domein in DOMEINEN else "onbekend"
    discipline = str(data.get("discipline") or "onbekend").lower()
    result["discipline"] = discipline if discipline in ("weg", "veld", "baan") else "onbekend"
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
) -> dict:
    """Eén call naar de Chat Completions API; geef het intake-schema.

    Bij elke fout (netwerk, HTTP, ongeldige JSON) de veilige fallback:
    domein onbekend, confidence 0 — de route wordt dan altijd "router".
    """
    try:
        resp = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _normaliseer(json.loads(content))
    except Exception:
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
