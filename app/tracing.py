"""Content-free routing traces for terminal logging and the opt-in local panel."""

import hashlib
import json
import logging
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from ipaddress import ip_address

from fastapi import Request

logger = logging.getLogger("uvicorn.error.trace")

AGENTS = {"router-agent", "knwu-agent", "regio-agent", "club-agent", "archief-agent"}
FIELDS = {"route", "reason", "agent", "previous_agent", "tool", "confidence", "duration_ms"}


def local_debug_allowed(request: Request, enabled: bool) -> bool:
    """Require opt-in, a loopback peer/host, and a direct (non-proxied) request."""
    if not enabled or request.client is None:
        return False
    if any(
        name.lower() in ("forwarded", "x-real-ip") or name.lower().startswith("x-forwarded-")
        for name in request.headers
    ):
        return False
    try:
        peer_is_local = ip_address(request.client.host).is_loopback
    except ValueError:
        return False
    return peer_is_local and request.url.hostname in ("localhost", "127.0.0.1", "::1")


class Trace:
    def __init__(self, conversation_id: str) -> None:
        self.id = uuid.uuid4().hex
        self.conversation = hashlib.sha256(conversation_id.encode()).hexdigest()[:12]
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._start = time.monotonic()
        self._events: deque[dict] = deque(maxlen=100)
        self._event_count = 0
        self._route: str | float | None = None
        self._status = "working"
        self._lock = threading.Lock()

    def record(self, event: str, **fields: str | float | None) -> None:
        """Only callers' fixed diagnostic fields belong here, never API payloads."""
        if fields.keys() - FIELDS:
            raise ValueError("Unsupported trace fields; do not record request/API payloads")
        with self._lock:
            if event == "route":
                self._route = fields.get("route")
            if event in ("done", "error", "cancelled"):
                self._status = event
            entry = {
                "event": event,
                "elapsed_ms": round((time.monotonic() - self._start) * 1000, 1),
                **fields,
            }
            self._events.append(entry)
            self._event_count += 1
            logger.info(
                "chat_trace %s",
                json.dumps({"trace_id": self.id, "conversation": self.conversation, **entry}),
            )

    def stream_event(self, event: str, data: dict, current_agent: str) -> None:
        """Select metadata only; never retain deltas, tool arguments or results."""
        if event == "agent.handoff.done":
            agent = data.get("next_agent_name")
            self.record(
                "handoff",
                previous_agent=current_agent if current_agent in AGENTS else "unknown",
                agent=agent if isinstance(agent, str) and agent in AGENTS else "unknown",
            )
        elif event in ("tool.execution.started", "tool.execution.done"):
            tool = data.get("name")
            self.record(
                "tool_started" if event.endswith("started") else "tool_done",
                agent=current_agent if current_agent in AGENTS else "unknown",
                tool=tool if tool in ("document_library", "web_search", "web_search_premium") else "unknown",
            )

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "trace_id": self.id,
                "conversation": self.conversation,
                "started_at": self.started_at,
                "route": self._route,
                "status": self._status,
                "events": list(self._events),
                "dropped_events": self._event_count - len(self._events),
            }


class TraceStore:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled
        self._traces: deque[Trace] = deque(maxlen=100)

    def start(self, conversation_id: str) -> Trace:
        trace = Trace(conversation_id)
        if self._enabled:
            self._traces.append(trace)
        trace.record("started")
        return trace

    def snapshot(self) -> list[dict]:
        return [trace.snapshot() for trace in reversed(self._traces)]
