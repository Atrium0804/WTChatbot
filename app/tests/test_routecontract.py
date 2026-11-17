"""Routecontract (#107, #117): één tabel voor bypass of inhoudelijke route.

Elke regel in fixtures/routecontract.yaml is een gesprek; de test speelt het via
POST /chat af met een nep-Mistral en controleert de route van elke beurt.
Alleen de route wordt getoetst, niet de antwoordtekst.
"""

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest
import yaml

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "import-time.db")
os.environ["MISTRAL_API_KEY"] = ""
os.environ["MISTRAL_AGENT_ID"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
import intake  # noqa: E402
import mistral_client  # noqa: E402
from main import create_app  # noqa: E402

CONTRACT = yaml.safe_load((Path(__file__).parent / "fixtures" / "routecontract.yaml").read_text("utf-8"))
RULES = CONTRACT["regels"]


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/chat/status/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} werd niet done binnen {timeout}s")


def _install_fake_mistral(monkeypatch) -> tuple[list[dict], list[dict], dict]:
    """Mistral-mode met nep-intake en nep-agents; geef (intake-calls, agent-calls, intake-velden).

    De nep-intake geeft de velden die de beurt als `intake` meegeeft; zonder
    `intake` een neutraal resultaat (domein onbekend, confidence 0)."""
    intake_calls: list[dict] = []
    agent_calls: list[dict] = []
    turn_intake: dict = {}

    def classify_message(**kwargs):
        intake_calls.append(kwargs)
        return {**intake.FALLBACK, **turn_intake}

    def stream_answer(**kwargs):
        agent_calls.append(kwargs)
        return "mistral-conv-1", "antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", classify_message)
    monkeypatch.setattr(mistral_client, "stream_answer", stream_answer)
    monkeypatch.setattr(mistral_client, "answer_question", stream_answer)
    return intake_calls, agent_calls, turn_intake


@pytest.mark.parametrize("rule", RULES, ids=[rule["id"] for rule in RULES])
def test_routecontract(rule, tmp_path, monkeypatch):
    intake_calls, agent_calls, turn_intake = _install_fake_mistral(monkeypatch)
    today = rule.get("vandaag", CONTRACT["vandaag"])
    # Eén blijvende event loop: background jobs stranden niet als een request-loop sluit.
    client = TestClient(create_app(db_path=str(tmp_path / "t.db"), today=lambda: today))
    with client:
        _play_rule(client, rule, intake_calls, agent_calls, turn_intake)


def _play_rule(
    client: TestClient,
    rule: dict,
    intake_calls: list[dict],
    agent_calls: list[dict],
    turn_intake: dict,
) -> None:
    conversation_id = None
    for number, turn in enumerate(rule["beurten"], start=1):
        label = f"{rule['id']} beurt {number}: {turn['vraag']!r}"
        turn_intake.clear()
        turn_intake.update(turn.get("intake", {}))
        intake_before, agent_before = len(intake_calls), len(agent_calls)
        payload = {"message": turn["vraag"], "client_id": "test-client"}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        resp = client.post("/chat", json=payload)
        assert resp.status_code in (200, 202), f"{label}: {resp.text}"
        if resp.status_code == 200:
            route = "bypass"
            conversation_id = resp.json()["conversation_id"]
        else:
            status = _wait_for_job(client, resp.json()["job_id"])
            assert status["status"] == "done", f"{label}: {status}"
            route = "bypass" if status["route"] == "bypass" else "inhoudelijk"
            conversation_id = status["conversation_id"]
        assert route == turn["route"], f"{label}: verwachtte {turn['route']}, kreeg {route}"
        if turn["route"] != "bypass":
            continue
        assert len(agent_calls) == agent_before, f"{label}: bypass startte een agentgesprek"
        if "intake" not in turn:
            assert resp.status_code == 200, f"{label}: regex-bypass moet synchroon 200 geven"
            assert len(intake_calls) == intake_before, f"{label}: regex-bypass deed een LLM-call"
        else:
            assert len(intake_calls) - intake_before <= 1, f"{label}: meer dan één intake-call"
