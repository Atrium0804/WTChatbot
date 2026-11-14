"""Tests voor de dunne Mistral-laag: SSE-streaming (#90/#93) en prompt caching — offline."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mistral_client  # noqa: E402


def sse(event: str, data: dict) -> str:
    return "data: " + json.dumps({"event": event, "data": data})


class FakeResp:
    def __init__(self, lines, status=200, payload=None):
        self._lines = lines
        self.status_code = status
        self.text = "error-body"
        self._payload = payload or {"conversation_id": "conv-1", "outputs": []}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def json(self):
        return self._payload


def test_stream_answer_parseert_events_en_tekst_na_laatste_handoff():
    lines = [
        sse("conversation.response.started", {"conversation_id": "conv-9"}),
        sse("message.output.delta", {"content": [{"type": "text", "text": "routertekst "}]}),
        sse("agent.handoff.done", {"next_agent_name": "knwu-agent"}),
        sse("message.output.delta", {"content": [{"type": "text", "text": "Echte "}, {"type": "text", "text": "antwoord"}]}),
        sse("conversation.response.done", {"usage": {}}),
    ]
    events: list[str] = []
    with patch("requests.post", return_value=FakeResp(lines)) as post:
        conv, text = mistral_client.stream_answer(
            api_key="k",
            agent_id="ag-router",
            base_url="https://example.test/v1/conversations",
            message="vraag",
            on_event=lambda e, d: events.append(e),
        )
    assert conv == "conv-9"
    assert text == "Echte antwoord"  # tekst vóór de laatste handoff telt niet mee
    assert events == [
        "conversation.response.started",
        "message.output.delta",
        "agent.handoff.done",
        "message.output.delta",
        "conversation.response.done",
    ]
    body = post.call_args.kwargs["json"]
    assert body["stream"] is True
    assert body["agent_id"] == "ag-router"
    assert post.call_args.kwargs["stream"] is True


def test_stream_answer_stuurt_prompt_cache_key_en_metadata():
    with patch("requests.post", return_value=FakeResp([sse("conversation.response.done", {})])) as post:
        mistral_client.stream_answer(
            api_key="k",
            agent_id="ag",
            base_url="u",
            message="m",
            metadata={"app_conversation_id": "abc"},
            prompt_cache_key="wtchatbot-v1",
        )
    body = post.call_args.kwargs["json"]
    assert body["prompt_cache_key"] == "wtchatbot-v1"
    assert body["metadata"] == {"app_conversation_id": "abc"}


def test_stream_answer_bij_bestaande_conversation_geen_agent_id():
    with patch("requests.post", return_value=FakeResp([])) as post:
        conv, _ = mistral_client.stream_answer(
            api_key="k", agent_id="ag", base_url="u", message="m", conversation_id="conv-7"
        )
    assert conv == "conv-7"
    assert post.call_args.args[0] == "u/conv-7"
    assert "agent_id" not in post.call_args.kwargs["json"]


def test_stream_answer_error_event_raises_runtime_error():
    lines = [sse("conversation.response.error", {"message": "kapot"})]
    with patch("requests.post", return_value=FakeResp(lines)):
        with pytest.raises(RuntimeError, match="kapot"):
            mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")


def test_stream_start_fout_is_stream_start_error():
    # vóór het eerste event: veilig om non-streaming te retryen (#93)
    with patch("requests.post", side_effect=requests.ConnectionError("weg")):
        with pytest.raises(mistral_client.StreamStartError):
            mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")
    with patch("requests.post", return_value=FakeResp([], status=401)):
        with pytest.raises(mistral_client.StreamStartError):
            mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")


def test_stream_answer_negeert_ongeldige_sse_regels():
    lines = ["data: {geen json", "", "data: " + json.dumps({"event": "conversation.response.done", "data": {}})]
    with patch("requests.post", return_value=FakeResp(lines)):
        conv, text = mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")
    assert text == ""


def test_answer_question_stuurt_prompt_cache_key():
    with patch("requests.post", return_value=FakeResp([], payload={"conversation_id": "c1", "outputs": []})) as post:
        conv, _ = mistral_client.answer_question(
            api_key="k", agent_id="ag", base_url="u", message="m", prompt_cache_key="wtchatbot-v1"
        )
    assert conv == "c1"
    assert post.call_args.kwargs["json"]["prompt_cache_key"] == "wtchatbot-v1"


def test_answer_question_zonder_cache_key_stuurt_niets():
    with patch("requests.post", return_value=FakeResp([], payload={"conversation_id": "c1", "outputs": []})) as post:
        mistral_client.answer_question(api_key="k", agent_id="ag", base_url="u", message="m")
    assert "prompt_cache_key" not in post.call_args.kwargs["json"]
