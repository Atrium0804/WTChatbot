"""Routing traces: offline integration, privacy, bounded storage and local access."""

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "import-time.db")
os.environ["MISTRAL_API_KEY"] = ""
os.environ["MISTRAL_AGENT_ID"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import intake  # noqa: E402
import mistral_client  # noqa: E402
import tracing  # noqa: E402
from main import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_DEBUG_TRACES", True)
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "")
    monkeypatch.setattr(config, "EXPERT_AGENT_IDS", {"knwu": "knwu-id", "club": "club-id"})
    with TestClient(
        create_app(db_path=str(tmp_path / "test.db")),
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 50000),
    ) as client:
        yield client


def enable_mistral(monkeypatch, result=None):
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "secret-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(
        intake, "classify_message",
        lambda **kw: result if result is not None else dict(intake.FALLBACK),
    )
    monkeypatch.setattr(mistral_client, "stream_answer", lambda **kw: ("conv", "secret-answer"))


def post_and_wait(client, message, conversation_id=""):
    response = client.post("/chat", json={
        "message": message, "client_id": "test", "conversation_id": conversation_id,
    })
    if response.status_code == 202:
        job_id = response.json()["job_id"]
        for _ in range(500):
            status = client.get(f"/chat/status/{job_id}").json()
            if status["status"] in ("done", "error"):
                break
            time.sleep(0.01)
        else:
            pytest.fail("Chat job did not finish")
    else:
        assert response.status_code == 200
    traces = client.get("/debug/traces").json()["traces"]
    trace = next(trace for trace in traces if trace["trace_id"] == response.headers["X-Trace-ID"])
    return response, trace


def test_regex_bypass_is_logged_without_intake_or_content(client, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error.trace")
    message = "In welke leeftijdscategorie rijdt een jongen geboren in 2015?"
    response, trace = post_and_wait(client, message)
    assert response.status_code == 200
    assert [event["event"] for event in trace["events"]] == ["started", "route", "done"]
    assert trace["route"] == "bypass"
    assert trace["events"][1]["reason"] == "regex_lookup"
    assert trace["status"] == "done"
    entries = [
        json.loads(record.getMessage().removeprefix("chat_trace "))
        for record in caplog.records if record.name == "uvicorn.error.trace"
    ]
    assert len(entries) == 3
    assert all(entry["trace_id"] == trace["trace_id"] for entry in entries)
    serialized = json.dumps(trace) + caplog.text
    assert message not in serialized
    assert "geboortejaar" not in serialized
    assert response.json()["conversation_id"] not in serialized
    assert trace["events"][-1]["elapsed_ms"] >= trace["events"][0]["elapsed_ms"]


def test_stub_is_explicit_and_conversation_grouping_is_stable(client):
    response, first = post_and_wait(client, "Hoi")
    assert first["route"] == "stub"
    response = client.post("/chat", json={
        "message": "Hoi", "conversation_id": response.json()["conversation_id"],
    })
    second = client.get("/debug/traces").json()["traces"][0]
    assert second["trace_id"] != first["trace_id"]
    assert second["conversation"] == first["conversation"]


def test_intake_lookup_records_one_intake_but_no_agent(client, monkeypatch):
    enable_mistral(monkeypatch, {**intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2012})
    _, trace = post_and_wait(client, "Welk verzet? 2012")
    assert trace["route"] == "bypass"
    assert [event["event"] for event in trace["events"]] == ["started", "intake", "route", "done"]
    assert trace["events"][2]["reason"] == "intake_lookup"
    assert trace["events"][1]["duration_ms"] >= 0
    assert "geboortejaar" not in json.dumps(trace)


@pytest.mark.parametrize(
    ("result", "route", "reason"),
    [
        ({"domein": "club", "confidence": 0.95}, "direct-club", "confident_domain"),
        ({"domein": "knwu", "confidence": 0.4}, "router", "low_confidence"),
        ({"domein": "archief", "confidence": 0.99}, "router", "expert_not_configured"),
    ],
)
def test_route_choices_are_visible(client, monkeypatch, result, route, reason):
    enable_mistral(monkeypatch, result)
    _, trace = post_and_wait(client, "Wat zijn de regels voor deze wedstrijd?")
    entry = next(event for event in trace["events"] if event["event"] == "route")
    assert entry["route"] == route
    assert entry["reason"] == reason


def test_intake_429_fallback_is_traced_without_error_body(client, monkeypatch, caplog):
    original_classify = intake.classify_message
    enable_mistral(monkeypatch)
    monkeypatch.setattr(intake, "classify_message", original_classify)
    response = requests.Response()
    response.status_code = 429
    error = requests.HTTPError("secret-error-body", response=response)

    def fail(**kwargs):
        raise RuntimeError("secret-wrapper") from error

    monkeypatch.setattr(mistral_client, "chat_completion", fail)
    caplog.set_level(logging.INFO, logger="uvicorn.error.trace")
    _, trace = post_and_wait(client, "Waarom mag dit niet bij een wedstrijd?")
    assert trace["route"] == "router"
    assert any(event.get("reason") == "http_429" for event in trace["events"])
    assert "secret" not in json.dumps(trace) + caplog.text


def test_stream_handoffs_tools_and_errors_omit_payloads(client, monkeypatch, caplog):
    enable_mistral(monkeypatch)

    def stream(**kwargs):
        on_event = kwargs["on_event"]
        on_event("agent.handoff.done", {"next_agent_name": "knwu-agent", "secret": "secret-handoff"})
        on_event("tool.execution.started", {"name": "document_library", "arguments": "secret-query"})
        on_event("tool.execution.done", {"name": "document_library", "result": "secret-document"})
        on_event("message.output.delta", {"content": "secret-output"})
        on_event("message.output.done", {"agent_id": "knwu-id", "content": "secret-output"})
        raise RuntimeError("secret-failure")

    monkeypatch.setattr(mistral_client, "stream_answer", stream)
    caplog.set_level(logging.INFO, logger="uvicorn.error.trace")
    _, trace = post_and_wait(client, "secret-question about wedstrijd")
    assert trace["status"] == "error"
    events = trace["events"]
    assert any(event["event"] == "handoff" and event["agent"] == "knwu-agent" for event in events)
    assert any(event["event"] == "tool_started" and event["tool"] == "document_library" for event in events)
    assert any(event["event"] == "tool_done" for event in events)
    assert any(event["event"] == "agent_output" and event["agent"] == "knwu-agent" for event in events)
    assert events[-1]["reason"] == "RuntimeError"
    assert "secret" not in json.dumps(trace) + caplog.text


def test_stream_start_fallback_is_visible(client, monkeypatch):
    enable_mistral(monkeypatch)

    def fail(**kwargs):
        raise mistral_client.StreamStartError("private-error")

    monkeypatch.setattr(mistral_client, "stream_answer", fail)
    monkeypatch.setattr(mistral_client, "answer_question", lambda **kw: ("conv", "answer"))
    _, trace = post_and_wait(client, "Waarom geldt deze wedstrijdregel?")
    assert trace["status"] == "done"
    assert any(event["event"] == "stream_fallback" for event in trace["events"])


def test_continuing_conversation_does_not_claim_requested_expert_is_active(client, monkeypatch):
    enable_mistral(monkeypatch, {"domein": "club", "confidence": 0.99})

    def stream(**kwargs):
        kwargs["on_event"]("tool.execution.started", {"name": "document_library"})
        kwargs["on_event"]("message.output.done", {"agent_id": "knwu-id"})
        return "mistral-conv", "answer"

    monkeypatch.setattr(mistral_client, "stream_answer", stream)
    response, _ = post_and_wait(client, "Waarom geldt deze clubregel?")
    _, trace = post_and_wait(
        client, "Waarom geldt deze wedstrijdregel?", response.json()["conversation_id"],
    )
    request = next(event for event in trace["events"] if event["event"] == "agent_request")
    tool = next(event for event in trace["events"] if event["event"] == "tool_started")
    output = next(event for event in trace["events"] if event["event"] == "agent_output")
    assert request["agent"] == "club-agent"
    assert request["reason"] == "continue_conversation"
    assert tool["agent"] == "unknown"
    assert output["agent"] == "knwu-agent"


@pytest.mark.parametrize("path", ["/debug", "/debug/traces"])
def test_debug_is_disabled_by_default(tmp_path, monkeypatch, path):
    monkeypatch.setattr(config, "LOCAL_DEBUG_TRACES", False)
    with TestClient(
        create_app(db_path=str(tmp_path / "disabled.db")),
        base_url="http://127.0.0.1", client=("127.0.0.1", 1234),
    ) as local:
        assert local.get(path).status_code == 404


@pytest.mark.parametrize(
    ("peer", "base_url", "headers", "expected"),
    [
        ("127.0.0.1", "http://localhost", {}, 200),
        ("::1", "http://[::1]", {}, 200),
        ("192.168.1.4", "http://localhost", {}, 404),
        ("127.0.0.1", "https://wielie.famstieltjes.nl", {}, 404),
        ("127.0.0.1", "http://localhost", {"X-Forwarded-For": "127.0.0.1"}, 404),
        ("127.0.0.1", "http://localhost", {"X-Forwarded-Host": "localhost"}, 404),
        ("127.0.0.1", "http://localhost", {"Forwarded": "for=127.0.0.1"}, 404),
        ("127.0.0.1", "http://localhost", {"X-Real-IP": "127.0.0.1"}, 404),
    ],
)
def test_debug_requires_direct_loopback_access(tmp_path, monkeypatch, peer, base_url, headers, expected):
    monkeypatch.setattr(config, "LOCAL_DEBUG_TRACES", True)
    with TestClient(
        create_app(db_path=str(tmp_path / "access.db")),
        base_url=base_url, client=(peer, 1234),
    ) as local:
        for path in ("/debug", "/debug/traces"):
            response = local.get(path, headers=headers)
            assert response.status_code == expected
            assert response.headers["Cache-Control"] == "no-store"
        assert local.get("/debug.html").status_code == 404


def test_debug_has_no_cache_or_framing_and_worker_bypasses_it(client):
    response = client.get("/debug")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert '"/debug"' in client.get("/sw.js").text


def test_trace_buffers_are_bounded_and_keep_route_summary():
    store = tracing.TraceStore(enabled=True)
    for _ in range(101):
        last = store.start("conversation")
    assert len(store.snapshot()) == 100
    last.record("route", route="bypass")
    for _ in range(101):
        last.record("tool_started", tool="document_library")
    snapshot = store.snapshot()[0]
    assert len(snapshot["events"]) == 100
    assert snapshot["dropped_events"] == 3
    assert snapshot["route"] == "bypass"
    disabled = tracing.TraceStore(enabled=False)
    disabled.start("conversation").record("done")
    assert disabled.snapshot() == []
    with pytest.raises(ValueError):
        last.record("invalid", message="must not enter traces")


def test_unknown_agent_and_tool_names_are_not_retained():
    trace = tracing.Trace("conversation")
    trace.stream_event("agent.handoff.done", {"next_agent_name": "secret-agent"}, "")
    trace.stream_event("tool.execution.started", {"name": "secret-tool", "query": "secret"}, "")
    assert "secret" not in json.dumps(trace.snapshot())
