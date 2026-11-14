"""Tests voor de light-model intake en de route-beslissing (#91) — offline."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import intake  # noqa: E402
import knwu_categories  # noqa: E402

RULES = knwu_categories.load_rules()
NOVEMBER_2026 = date(2026, 11, 9)
EXPERTS = {"knwu": "ag_knwu", "regio": "ag_regio", "club": "ag_club", "archief": ""}


# --- decide_route ---


def test_route_bypass_bij_pure_lookup():
    route = intake.decide_route(
        message="In welke leeftijdscategorie rijdt een jongen geboren in 2015?",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result=dict(intake.FALLBACK),
        expert_agent_ids=EXPERTS,
        threshold=0.8,
    )
    assert route["route"] == "bypass"
    assert route["lookup"]["kind"] == "categorie"


def test_route_direct_bij_hoge_confidence_en_expert_bekend():
    route = intake.decide_route(
        message="Wat kost de contributie bij WTC Woerden?",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result={"domein": "club", "confidence": 0.95, "intentie": "regelgeving"},
        expert_agent_ids=EXPERTS,
        threshold=0.8,
    )
    assert route["route"] == "direct"
    assert route["agent_id"] == "ag_club"
    assert route["domein"] == "club"


def test_route_router_bij_lage_confidence():
    route = intake.decide_route(
        message="Hoe zit het met die wedstrijd?",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result={"domein": "regio", "confidence": 0.5, "intentie": "onbekend"},
        expert_agent_ids=EXPERTS,
        threshold=0.8,
    )
    assert route["route"] == "router"


def test_route_router_bij_ontbrekende_expert_id():
    # archief heeft geen id geconfigureerd -> geen direct-to-expert mogelijk
    route = intake.decide_route(
        message="Wat is er veranderd in Titel 20?",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result={"domein": "archief", "confidence": 0.99, "intentie": "regelgeving"},
        expert_agent_ids=EXPERTS,
        threshold=0.8,
    )
    assert route["route"] == "router"


def test_route_router_bij_intake_fout():
    route = intake.decide_route(
        message="Iets vaags",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result=dict(intake.FALLBACK),
        expert_agent_ids=EXPERTS,
        threshold=0.8,
    )
    assert route["route"] == "router"


def test_drempel_is_configureerbaar():
    route = intake.decide_route(
        message="Wat kost de contributie?",
        today=NOVEMBER_2026,
        rules=RULES,
        intake_result={"domein": "club", "confidence": 0.7, "intentie": "regelgeving"},
        expert_agent_ids=EXPERTS,
        threshold=0.6,
    )
    assert route["route"] == "direct"


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
