"""Tests voor de light-model intake en de route-beslissing (#91) — offline."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import intake  # noqa: E402
import knwu_categories  # noqa: E402
import lookups  # noqa: E402

RULES = knwu_categories.load_rules()
NOVEMBER_2026 = date(2026, 11, 9)
EXPERTS = {"knwu": "ag_knwu", "regio": "ag_regio", "club": "ag_club", "archief": ""}


def route_for(message: str, intake_result: dict, threshold: float = 0.8) -> intake.Route:
    decision = lookups.recognize_turn(message, None, NOVEMBER_2026, RULES)
    assert not isinstance(decision, lookups.ReadyForBypass), message
    return intake.decide_route(
        decision=decision,
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result=intake_result,
        expert_agent_ids=EXPERTS,
        threshold=threshold,
    )


# --- decide_route ---


def test_route_bypass_only_completes_a_grounded_pending_lookup():
    route = route_for("Welk verzet? 2012", {**intake.FALLBACK, "geboortejaar": 2012})
    assert route.kind == "bypass"
    assert isinstance(route.lookup, lookups.ReadyForBypass)


def test_rejected_input_is_never_rescued_into_a_bypass():
    route = route_for(
        "Welke categorie voor geboortejaar 2015 in 2025?",
        {**intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2015, "discipline": "weg"},
    )
    assert route.kind == "router"
    assert route.lookup.next_state.kind == "none"


def test_decide_route_refuses_a_ready_decision():
    ready = lookups.recognize_turn("2015", None, NOVEMBER_2026, RULES)
    with pytest.raises(TypeError, match="NeedsInputForBypass or NotEligibleForBypass"):
        intake.decide_route(
            decision=ready,  # type: ignore[arg-type]
            today=NOVEMBER_2026,
            rules=RULES,
            intake_result=dict(intake.FALLBACK),
            expert_agent_ids=EXPERTS,
            threshold=0.8,
        )


def test_route_direct_bij_hoge_confidence_en_expert_bekend():
    route = route_for(
        "Wat kost de contributie bij WTC Woerden?",
        {"domein": "club", "confidence": 0.95, "intentie": "regelgeving"},
    )
    assert route.kind == "direct"
    assert route.agent_id == "ag_club"
    assert route.domein == "club"


def test_route_router_bij_lage_confidence():
    route = route_for(
        "Hoe zit het met die wedstrijd?",
        {"domein": "regio", "confidence": 0.5, "intentie": "onbekend"},
    )
    assert route.kind == "router"


def test_route_router_bij_ontbrekende_expert_id():
    # archief heeft geen id geconfigureerd -> geen direct-to-expert mogelijk
    route = route_for(
        "Wat is er veranderd in Titel 20?",
        {"domein": "archief", "confidence": 0.99, "intentie": "regelgeving"},
    )
    assert route.kind == "router"


def test_route_router_bij_intake_fout():
    route = route_for("Iets vaags", dict(intake.FALLBACK))
    assert route.kind == "router"


def test_drempel_is_configureerbaar():
    route = route_for(
        "Wat kost de contributie?",
        {"domein": "club", "confidence": 0.7, "intentie": "regelgeving"},
        threshold=0.6,
    )
    assert route.kind == "direct"


# --- classify_message: parsing + fallback (netwerk gemockt) ---


def _resp(payload: dict):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": payload}}]}

    return R()


def test_classify_message_parseert_json():
    payload = (
        '{"intentie": "lookup", "domein": "knwu", "discipline": "weg", '
        '"geboortejaar": 2015, "leeftijd": null, "confidence": 0.9}'
    )
    with patch("requests.post", return_value=_resp(payload)) as post:
        result = intake.classify_message(
            api_key="k", base_url="https://example.test/v1/chat/completions",
            model="mistral-small-latest", message="vraag",
        )
    assert result["domein"] == "knwu"
    assert result["intentie"] == "lookup"
    assert result["geboortejaar"] == 2015
    assert result["confidence"] == 0.9
    body = post.call_args.kwargs["json"]
    assert body["model"] == "mistral-small-latest"
    assert body["response_format"] == {"type": "json_object"}


def test_classify_message_normaliseert_ongeldige_waarden():
    payload = '{"domein": "CLUB", "confidence": 7, "geboortejaar": "2015"}'
    with patch("requests.post", return_value=_resp(payload)):
        result = intake.classify_message(
            api_key="k", base_url="u", model="m", message="vraag"
        )
    assert result["domein"] == "club"
    assert result["confidence"] == 1.0  # afgekapt
    assert result["geboortejaar"] is None  # string wordt niet als int geaccepteerd


def test_classify_message_does_not_accept_track_as_supported_discipline():
    with patch("requests.post", return_value=_resp('{"discipline": "baan"}')):
        result = intake.classify_message(api_key="k", base_url="u", model="m", message="baanvraag")
    assert result["discipline"] == "onbekend"


def test_classify_message_fallback_bij_netwerkfout():
    import requests

    with patch("requests.post", side_effect=requests.ConnectionError("weg")):
        result = intake.classify_message(api_key="k", base_url="u", model="m", message="vraag")
    assert result == dict(intake.FALLBACK)
    assert result["confidence"] == 0.0


def test_classify_message_fallback_bij_ongeldige_json():
    with patch("requests.post", return_value=_resp("geen json {")):
        result = intake.classify_message(api_key="k", base_url="u", model="m", message="vraag")
    assert result == dict(intake.FALLBACK)

def test_system_prompt_komt_uit_apart_bestand():
    # CODING_PRINCIPLES.md: prompts staan in aparte bestanden, niet als lange
    # strings in de code — de intake-prompt staat in app/prompts/intake-system.md
    prompt = intake._system_prompt()
    assert "intentie" in prompt
    assert "confidence" in prompt
    assert intake.PROMPT_PATH.name == "intake-system.md"
