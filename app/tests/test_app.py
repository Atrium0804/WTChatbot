"""Offline tests voor de WTChatbot-proxy — geen live API-calls (CI-veilig).

Draai: .venv\Scripts\python -m pytest app/tests   (vanuit repo-root; de project-venv installeer je met app\requirements-dev.txt)
"""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Zorg dat de module-level app bij import geen productie-DB raakt.
os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "import-time.db")
# Tests moeten offline/stub blijven, ook als .env een echte key bevat:
# Zet lege waarden vóór import — config.py doet load_dotenv() (override=False)
# en leest dan lege strings in plaats van de echte key.
os.environ["MISTRAL_API_KEY"] = ""
os.environ["MISTRAL_AGENT_ID"] = ""

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


def chat_in(
    client: TestClient, conversation_id: str, message: str, client_id: str
) -> dict:
    resp = client.post(
        "/chat",
        json={
            "message": message,
            "conversation_id": conversation_id,
            "client_id": client_id,
        },
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
    history = json.loads(row["history"])
    assert len(history) == 1
    assert history[0]["question"] == "Wat is het maximale verzet voor U15?"
    assert "STUB" in history[0]["answer"]


def test_feedback_negative_stores_history_capped_at_counter(tmp_path):
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    conv = chat(client, "vraag 0", client_id="c0")
    conv_id = conv["conversation_id"]
    # 12 turns totaal; rate limit is 10/uur per client-ID, dus elk een eigen ID
    for i in range(1, 12):
        chat_in(client, conv_id, f"vraag {i}", client_id=f"c{i}")
    resp = client.post(
        "/feedback",
        json={"conversation_id": conv_id, "rating": "negative", "text": "nog steeds fout"},
    )
    assert resp.status_code == 200
    row = store.all_feedback(db)[0]
    history = json.loads(row["history"])
    # counter (FEEDBACK_HISTORY_TURNS = 10): alleen de laatste 10 turns
    assert len(history) == 10
    assert history[0]["question"] == "vraag 2"
    assert history[-1]["question"] == "vraag 11"
    # losse question/answer-kolommen = laatste turn
    assert row["question"] == "vraag 11"
    assert "STUB" in row["answer"]


def test_feedback_history_answer_capped(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "stub_answer", lambda message: "x" * 5000)
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    conv = chat(client, "lange vraag")
    client.post(
        "/feedback",
        json={"conversation_id": conv["conversation_id"], "rating": "negative"},
    )
    row = store.all_feedback(db)[0]
    assert len(row["answer"]) == 2000
    history = json.loads(row["history"])
    assert len(history[0]["answer"]) == 2000


def test_init_db_migrates_old_schema_without_history(tmp_path):
    db = str(tmp_path / "old.db")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE feedback ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " timestamp TEXT NOT NULL,"
            " rating TEXT NOT NULL,"
            " conversation_id TEXT,"
            " question TEXT,"
            " answer TEXT,"
            " text TEXT)"
        )
        conn.execute(
            "INSERT INTO feedback (timestamp, rating) VALUES (?, ?)",
            ("2026-01-01T00:00:00+00:00", "positive"),
        )
    store.init_db(db)
    with sqlite3.connect(db) as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(feedback)")}
    assert "history" in columns
    store.save_feedback(
        db,
        rating="negative",
        conversation_id="c1",
        question="q",
        answer="a",
        text="t",
        history=[{"question": "q", "answer": "a"}],
    )
    rows = store.all_feedback(db)
    assert rows[0]["history"] is None  # oude row uit vòòr de migratie
    assert json.loads(rows[1]["history"]) == [{"question": "q", "answer": "a"}]


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
    assert rows[0]["history"] is None


def test_feedback_invalid_rating_400(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/feedback", json={"rating": "meh"})
    assert resp.status_code == 400


def test_purge_old_feedback(tmp_path):
    db = str(tmp_path / "test.db")
    store.init_db(db)
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()

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


# Realistische shape van POST /v1/conversations (captured 2026-11-04):
# outputs[]-entries hebben top-level "content", type "message.output";
# content-chunks hebben type "text" (of "thinking", die negeren we).
REAL_OUTPUTS = [
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": [{"type": "text", "text": "even nadenken"}]}
        ],
    },
    {
        "object": "entry",
        "type": "tool.execution",
        "name": "document_library",
        "arguments": "{\"query\": \"ZMC kosten\"}",
        "info": {"result": "..."},
    },
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Het antwoord is 6,70 meter.\n\nBron: TITEL_20.pdf, versie 2026-09-21"}
        ],
    },
]


def test_extract_text_real_conversations_shape():
    import mistral_client

    assert mistral_client.extract_text(REAL_OUTPUTS) == (
        "Het antwoord is 6,70 meter.\n\nBron: TITEL_20.pdf, versie 2026-09-21"
    )


def test_extract_text_string_content():
    import mistral_client

    outputs = [{"type": "message.output", "content": "platte tekst"}]
    assert mistral_client.extract_text(outputs) == "platte tekst"


def test_manifest_served_as_manifest_json(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")
    data = resp.json()
    assert data["name"] == "WTC Chatbot"
    assert data["short_name"] == "Wielie"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/" and data["scope"] == "/"
    sizes = {i["sizes"] for i in data["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in data["icons"])


def test_service_worker_served_as_javascript(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    body = resp.text
    assert 'addEventListener("fetch"' in body
    # privacy: API-endpoints mogen nooit gecached worden
    for path in ("/chat", "/feedback", "/healthz"):
        assert path in body


def test_debug_script_served_before_chat_initialization(tmp_path):
    client = make_client(tmp_path)
    html = client.get("/?debug=1").text
    assert html.index('<script src="/debug.js"></script>') < html.index(
        'document.dispatchEvent(new Event("chat:init-start"))'
    )
    resp = client.get("/debug.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert '"/debug.js"' in client.get("/sw.js").text


def test_icons_served_as_png(tmp_path):
    client = make_client(tmp_path)
    for name in (
        "icon-192.png",
        "icon-512.png",
        "icon-maskable-512.png",
        "apple-touch-icon.png",
        "favicon-32.png",
    ):
        resp = client.get(f"/icons/{name}")
        assert resp.status_code == 200, name
        assert resp.headers["content-type"] == "image/png", name


def test_index_has_pwa_head_tags(tmp_path):
    client = make_client(tmp_path)
    html = client.get("/").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'name="apple-mobile-web-app-capable"' in html
    assert '<meta name="apple-mobile-web-app-status-bar-style" content="default">' in html
    assert 'name="theme-color"' not in html
    assert "viewport-fit=cover" in html
    assert 'navigator.serviceWorker.register("/sw.js")' in html


def test_index_has_safe_area_insets(tmp_path):
    client = make_client(tmp_path)
    html = client.get("/").text
    header_css = html[html.index("header {"):html.index("header h1")]
    footer_css = html[html.index("footer {"):html.index("#composer")]
    assert "padding-top: calc(0.6rem + env(safe-area-inset-top, 0px))" in header_css
    assert "padding-right: calc(1rem + env(safe-area-inset-right, 0px))" in header_css
    assert "padding-left: calc(1rem + env(safe-area-inset-left, 0px))" in header_css
    assert "padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0px))" in footer_css
    assert "padding-right: calc(0.5rem + env(safe-area-inset-right, 0px))" in footer_css
    assert "padding-left: calc(0.5rem + env(safe-area-inset-left, 0px))" in footer_css


def test_text_inputs_are_at_least_16px_to_prevent_ios_zoom(tmp_path):
    # iOS Safari zoomt in bij focus op invoervelden < 16px; in de PWA blijft die
    # zoom hangen: header onder de statusbalk, Verstuur-knop buiten beeld (#54).
    client = make_client(tmp_path)
    html = client.get("/").text
    question_css = html[html.index("#question {"):html.index("#send {")]
    feedback_css = html[html.index(".feedback textarea {"):html.index(".feedback .thanks")]
    assert "font-size: 16px;" in question_css
    assert "font-size: 16px;" in feedback_css


def test_shell_backgrounds_use_club_blue(tmp_path):
    client = make_client(tmp_path)
    html = client.get("/").text
    body_css = html[html.index("  body {"):html.index("  header {")]
    assert "background: var(--accent) url(" in body_css
    manifest = client.get("/manifest.webmanifest").json()
    assert manifest["background_color"] == "#033ec2"


def test_no_theme_color_because_ios_blurs_top_edge(tmp_path):
    # iOS 27 vervaagt in de geinstalleerde PWA de bovenste ~36 css-px zodra er een
    # theme-color is, via de meta-tag of het manifest. Op het toestel vastgesteld (#54).
    client = make_client(tmp_path)
    assert 'name="theme-color"' not in client.get("/").text
    assert "theme_color" not in client.get("/manifest.webmanifest").json()


def test_viewport_script_is_served_and_included_in_offline_shell(tmp_path):
    client = make_client(tmp_path)
    assert '<script src="/viewport.js"></script>' in client.get("/").text
    response = client.get("/viewport.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert '"/viewport.js"' in client.get("/sw.js").text


def test_lab_has_separate_pwa_identity(tmp_path):
    # Herbouwexperiment #54: aparte installatie naast het huidige scherm.
    client = make_client(tmp_path)
    html = client.get("/lab/index.html")
    assert html.status_code == 200
    assert html.headers["cache-control"] == "no-cache"
    assert '<link rel="manifest" href="/lab/manifest.webmanifest">' in html.text
    assert '<meta name="apple-mobile-web-app-title" content="Wielie Lab">' in html.text
    lab = client.get("/lab/manifest.webmanifest").json()
    root = client.get("/manifest.webmanifest").json()
    assert lab["id"] == "/lab/"
    assert lab["scope"] == "/lab/"
    assert lab["start_url"] == "/lab/index.html"
    assert lab["name"] != root["name"] and lab["short_name"] != root["short_name"]


def test_root_service_worker_leaves_lab_alone(tmp_path):
    client = make_client(tmp_path)
    body = client.get("/sw.js").text
    assert 'url.pathname.indexOf("/lab/") === 0' in body


def test_csp_allows_service_worker_and_manifest(tmp_path):
    client = make_client(tmp_path)
    csp = client.get("/").headers["content-security-policy"]
    assert "worker-src 'self'" in csp
    assert "manifest-src 'self'" in csp


def test_cache_control_headers(tmp_path):
    client = make_client(tmp_path)
    # html, sw.js en manifest altijd revalideren
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/sw.js").headers["cache-control"] == "no-cache"
    assert client.get("/manifest.webmanifest").headers["cache-control"] == "no-cache"
    # statische assets kort cachen
    assert client.get("/icons/icon-192.png").headers["cache-control"] == "public, max-age=3600"
    assert client.get("/Achtergrond%2016-9.jpg").headers["cache-control"] == "public, max-age=3600"
    # API-antwoorden krijgen géén Cache-Control
    resp = client.post("/chat", json={"message": "hoi", "client_id": "cc-test"})
    assert "cache-control" not in resp.headers


def test_mistral_timeout_default_60():
    import mistral_client

    assert mistral_client.DEFAULT_TIMEOUT == 60


def test_index_shows_thinking_message(tmp_path):
    client = make_client(tmp_path)
    assert "Wielie denkt na…" in client.get("/").text


def fake_mistral(monkeypatch) -> list[dict]:
    """Zet de app in Mistral-mode met een gemockte answer_question; geef de calls."""
    import config
    import mistral_client

    calls: list[dict] = []

    def answer_question(**kwargs):
        calls.append(kwargs)
        return "mistral-conv-1", "antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(mistral_client, "answer_question", answer_question)
    return calls


def test_chat_adds_date_and_metadata_on_new_conversation(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = TestClient(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    body = chat(client, "Wanneer is de volgende wedstrijd?")
    sent = calls[0]
    assert sent["message"].startswith("Wanneer is de volgende wedstrijd?")
    assert "maandag 9 november 2026" in sent["message"]
    assert sent["conversation_id"] is None
    assert sent["metadata"] == {"app_conversation_id": body["conversation_id"]}


def test_chat_follow_up_adds_category_but_no_date(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = TestClient(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    first = chat(client, "In welke leeftijdscategorie rijdt mijn zoon?")
    chat_in(client, first["conversation_id"], "2015", "test-client")
    follow_up = calls[1]["message"]
    assert calls[1]["conversation_id"] == "mistral-conv-1"
    assert "november 2026" not in follow_up
    assert "wegwielrennen 2026: U12" in follow_up


def test_chat_sends_language_level_context(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = TestClient(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    resp = client.post(
        "/chat", json={"message": "Hoeveel kost een licentie?", "client_id": "c", "language_level": "B2"}
    )
    assert resp.status_code == 200, resp.text
    assert "vastgesteld taalniveau: B2" in calls[0]["message"]
    # ook op een vervolgbericht (zonder datumregel) staat de taalniveau-regel
    resp2 = client.post(
        "/chat",
        json={
            "message": "en voor mijn dochter?",
            "conversation_id": resp.json()["conversation_id"],
            "client_id": "c",
            "language_level": "B2",
        },
    )
    assert resp2.status_code == 200, resp2.text
    follow_up = calls[1]["message"]
    assert "vastgesteld taalniveau: B2" in follow_up
    assert "november 2026" not in follow_up


def test_chat_language_level_defaults_to_b1(tmp_path, monkeypatch):
    calls = fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    # geen language_level meegestuurd
    resp = client.post("/chat", json={"message": "vraag", "client_id": "c"})
    assert resp.status_code == 200, resp.text
    assert "vastgesteld taalniveau: B1" in calls[0]["message"]
    # ongeldige waarde: geen 400, maar B1
    resp = client.post(
        "/chat", json={"message": "vraag", "client_id": "c", "language_level": "van alles"}
    )
    assert resp.status_code == 200, resp.text
    assert "vastgesteld taalniveau: B1" in calls[1]["message"]


def test_chat_feedback_history_keeps_raw_question(tmp_path, monkeypatch):
    fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    body = chat(client, "Mijn zoon is van 2015")
    client.post(
        "/feedback",
        json={"conversation_id": body["conversation_id"], "rating": "negative", "text": ""},
    )
    rows = store.all_feedback(str(tmp_path / "test.db"))
    assert rows[-1]["question"] == "Mijn zoon is van 2015"
