"""Offline tests voor de WTChatbot-proxy — geen live API-calls (CI-veilig).

Draai: pytest app/tests   (vanuit repo-root, met requirements-dev.txt geinstalleerd)
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Zorg dat de module-level app bij import geen productie-DB raakt.
os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "import-time.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import store  # noqa: E402
from main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(db_path=str(tmp_path / "test.db")))


def chat(client: TestClient, message: str, client_id: str = "test-client") -> dict:
    resp = client.post(
        "/chat", json={"message": message, "client_id": client_id}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_chat_stub_answer(tmp_path):
    client = make_client(tmp_path)
    body = chat(client, "Hoeveel contributie kost jeugd?")
    assert body["conversation_id"]
    assert "STUB" in body["answer"]
    assert "Bron:" in body["answer"]


def test_chat_empty_message_400(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "   ", "client_id": "c"})
    assert resp.status_code == 400


def test_chat_too_long_413(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "x" * 1001, "client_id": "c"})
    assert resp.status_code == 413


def test_rate_limit_per_client_id(tmp_path):
    client = make_client(tmp_path)
    for i in range(10):
        resp = client.post("/chat", json={"message": f"vraag {i}", "client_id": "deze"})
        assert resp.status_code == 200, resp.text
    resp = client.post("/chat", json={"message": "eentje te veel", "client_id": "deze"})
    assert resp.status_code == 429
    # andere client-ID heeft een eigen bucket
    resp = client.post("/chat", json={"message": "nieuw", "client_id": "ander"})
    assert resp.status_code == 200


def test_feedback_negative_stores_content(tmp_path):
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    conv = chat(client, "Wat is het maximale verzet voor U15?")  # expres foute vraag
    resp = client.post(
        "/feedback",
        json={"conversation_id": conv["conversation_id"], "rating": "negative", "text": "klopt niet"},
    )
    assert resp.status_code == 200
    rows = store.all_feedback(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["rating"] == "negative"
    assert row["question"] == "Wat is het maximale verzet voor U15?"
    assert "STUB" in row["answer"]
    assert row["text"] == "klopt niet"


def test_feedback_positive_stores_counter_only(tmp_path):
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    conv = chat(client, "Hoe laat is de training?")
    client.post(
        "/feedback",
        json={"conversation_id": conv["conversation_id"], "rating": "positive"},
    )
    rows = store.all_feedback(db)
    assert len(rows) == 1
    assert rows[0]["rating"] == "positive"
    assert rows[0]["question"] is None
    assert rows[0]["answer"] is None
    assert rows[0]["conversation_id"] is None


def test_feedback_invalid_rating_400(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/feedback", json={"rating": "meh"})
    assert resp.status_code == 400


def test_purge_old_feedback(tmp_path):
    db = str(tmp_path / "test.db")
    store.init_db(db)
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    import sqlite3

    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO feedback (timestamp, rating) VALUES (?, ?)", (old, "positive")
        )
        conn.execute(
            "INSERT INTO feedback (timestamp, rating) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), "positive"),
        )
    removed = store.purge_old(db, retention_days=30)
    assert removed == 1
    assert len(store.all_feedback(db)) == 1


def test_security_headers_no_x_frame_options(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in csp
    assert "x-frame-options" not in {k.lower() for k in resp.headers.keys()}


def test_healthz_stub_mode(tmp_path):
    client = make_client(tmp_path)
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["mistral_configured"] is False
