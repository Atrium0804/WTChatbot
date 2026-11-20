"""Tests voor de dunne Mistral-laag: SSE-streaming (#90/#93) en prompt caching — offline."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mistral_client  # noqa: E402


def sse(event: str, data: dict, *, flat: bool = False) -> str:
    payload = {"type": event, **data} if flat else {"event": event, "data": data}
    return "data: " + json.dumps(payload)


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


@pytest.mark.parametrize("flat", [False, True])
def test_stream_answer_error_event_raises_runtime_error(flat):
    lines = [sse("conversation.response.error", {"message": "kapot"}, flat=flat)]
    with patch("requests.post", return_value=FakeResp(lines)):
        with pytest.raises(RuntimeError, match="kapot"):
            mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")


def test_stream_answer_reads_flat_events_and_ignores_thinking():
    lines = [
        sse("conversation.response.started", {"conversation_id": "conv-live"}, flat=True),
        sse("message.output.delta", {
            "content": {"type": "thinking", "thinking": [{"type": "text", "text": "Niet tonen"}]},
        }, flat=True),
        sse("message.output.delta", {"content": "Het maximale "}, flat=True),
        sse("message.output.delta", {"content": "verzet."}, flat=True),
        sse("conversation.response.done", {"usage": {}}, flat=True),
    ]
    events = []
    with patch("requests.post", return_value=FakeResp(lines)):
        conv, text = mistral_client.stream_answer(
            api_key="k", agent_id="a", base_url="u", message="m",
            on_event=lambda event, data: events.append((event, data)),
        )
    assert conv == "conv-live"
    assert text == "Het maximale verzet."
    assert events[0] == ("conversation.response.started", {"conversation_id": "conv-live"})
    assert events[-1] == ("conversation.response.done", {"usage": {}})


@pytest.mark.parametrize("flat", [False, True])
def test_stream_answer_done_output_after_handoff(flat):
    lines = [
        sse("message.output.delta", {"content": "Ik verwijs je door."}, flat=flat),
        sse("agent.handoff.done", {"next_agent_name": "knwu-agent"}, flat=flat),
        sse("message.output.done", {"content": [
            {"type": "thinking", "thinking": [{"type": "text", "text": "Niet tonen"}]},
            {"type": "text", "text": "Het antwoord."},
        ]}, flat=flat),
    ]
    with patch("requests.post", return_value=FakeResp(lines)):
        _, text = mistral_client.stream_answer(api_key="k", agent_id="a", base_url="u", message="m")
    assert text == "Het antwoord."


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


@pytest.mark.parametrize("flat", [False, True])
def test_stream_answer_reports_function_calls_assembled_from_deltas(flat):
    lines = [
        sse("conversation.response.started", {"conversation_id": "conv-f"}, flat=flat),
        sse("function.call.delta", {"tool_call_id": "c1", "name": "bereken_verzet", "arguments": '{"chain'}, flat=flat),
        sse("function.call.delta", {"tool_call_id": "c1", "name": "", "arguments": 'ring": 50}'}, flat=flat),
        sse("function.call.delta", {"tool_call_id": "c2", "name": "bereken_verzet", "arguments": "{}"}, flat=flat),
        sse("conversation.response.done", {}, flat=flat),
    ]
    calls = []
    with patch("requests.post", return_value=FakeResp(lines)):
        conv, text = mistral_client.stream_answer(
            api_key="k", agent_id="a", base_url="u", message="m", on_function_call=calls.append
        )
    assert conv == "conv-f"
    assert text == ""
    assert calls == [
        mistral_client.FunctionCall("c1", "bereken_verzet", '{"chainring": 50}'),
        mistral_client.FunctionCall("c2", "bereken_verzet", "{}"),
    ]


def test_stream_answer_sends_function_results_as_inputs():
    results = [{"type": "function.result", "tool_call_id": "c1", "result": "{}"}]
    with patch("requests.post", return_value=FakeResp([])) as post:
        mistral_client.stream_answer(
            api_key="k", agent_id="a", base_url="u", message=results, conversation_id="conv-f"
        )
    assert post.call_args.kwargs["json"]["inputs"] == results


def test_answer_question_reports_function_call_outputs():
    payload = {
        "conversation_id": "c1",
        "outputs": [
            {"type": "function.call", "tool_call_id": "t1", "name": "bereken_verzet", "arguments": '{"a": 1}'},
            {"type": "function.call", "tool_call_id": "t2", "name": "bereken_verzet", "arguments": {"b": 2}},
        ],
    }
    calls = []
    with patch("requests.post", return_value=FakeResp([], payload=payload)):
        mistral_client.answer_question(
            api_key="k", agent_id="ag", base_url="u", message="m", on_function_call=calls.append
        )
    assert calls == [
        mistral_client.FunctionCall("t1", "bereken_verzet", '{"a": 1}'),
        mistral_client.FunctionCall("t2", "bereken_verzet", '{"b": 2}'),
    ]


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
