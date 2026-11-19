"""Offline tests voor de WTChatbot-proxy — geen live API-calls (CI-veilig).

Draai: .venv\Scripts\python -m pytest app/tests   (vanuit repo-root; de project-venv installeer je met app\requirements-dev.txt)
"""

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

# Zorg dat de module-level app bij import geen productie-DB raakt.
os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "import-time.db")
# Tests moeten offline/stub blijven, ook als .env een echte key bevat:
# Zet lege waarden vóór import — config.py doet load_dotenv() (override=False)
# en leest dan lege strings in plaats van de echte key.
os.environ["MISTRAL_API_KEY"] = ""
os.environ["MISTRAL_AGENT_ID"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
import store  # noqa: E402
from main import create_app  # noqa: E402


_open_clients: list[TestClient] = []


def open_client(app) -> TestClient:
    """TestClient met één blijvende event loop. Zonder context krijgt elk request
    een eigen loop, waardoor een background chat-job kan stranden; de fixture
    hieronder sluit de clients na elke test."""
    client = TestClient(app)
    client.__enter__()
    _open_clients.append(client)
    return client


@pytest.fixture(autouse=True)
def _close_open_clients():
    yield
    while _open_clients:
        _open_clients.pop().__exit__(None, None, None)


def make_client(tmp_path: Path) -> TestClient:
    return open_client(create_app(db_path=str(tmp_path / "test.db")))


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    """Poll /chat/status/<job> tot de job done/error is (#85)."""
    import time as _time
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        resp = client.get(f"/chat/status/{job_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("done", "error"):
            return body
        _time.sleep(0.01)
    raise AssertionError(f"job {job_id} werd niet done binnen {timeout}s")


def chat(client: TestClient, message: str, client_id: str = "test-client") -> dict:
    resp = client.post(
        "/chat", json={"message": message, "client_id": client_id}
    )
    assert resp.status_code in (200, 202), resp.text
    if resp.status_code == 202:
        # #85: Mistral-mode — poll de status tot done
        result = _wait_for_job(client, resp.json()["job_id"])
        assert result["status"] == "done", result
        return {"conversation_id": result["conversation_id"], "answer": result["answer"]}
    return resp.json()


def chat_raw(client: TestClient, payload: dict) -> dict:
    """POST /chat en give het finale body terug (handelt 202+poll af, #85)."""
    resp = client.post("/chat", json=payload)
    assert resp.status_code in (200, 202), resp.text
    if resp.status_code == 202:
        result = _wait_for_job(client, resp.json()["job_id"])
        assert result["status"] == "done", result
        return {"conversation_id": result["conversation_id"], "answer": result["answer"]}
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
    assert resp.status_code in (200, 202), resp.text
    if resp.status_code == 202:
        result = _wait_for_job(client, resp.json()["job_id"])
        assert result["status"] == "done", result
        return {"conversation_id": result["conversation_id"], "answer": result["answer"]}
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


def test_rate_limit_per_client_id(tmp_path, monkeypatch):
    # limiet expliciet, los van de default in config.py
    monkeypatch.setattr(config, "RATE_LIMIT_PER_HOUR", 3)
    client = make_client(tmp_path)
    for i in range(3):
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
    conv = chat(client, "Hoeveel kost de contributie voor jeugdleden?")
    resp = client.post(
        "/feedback",
        json={"conversation_id": conv["conversation_id"], "rating": "negative", "text": "klopt niet"},
    )
    assert resp.status_code == 200
    rows = store.all_feedback(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["rating"] == "negative"
    assert row["question"] == "Hoeveel kost de contributie voor jeugdleden?"
    assert "STUB" in row["answer"]
    assert row["text"] == "klopt niet"
    history = json.loads(row["history"])
    assert len(history) == 1
    assert history[0]["question"] == "Hoeveel kost de contributie voor jeugdleden?"
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


def test_extract_text_skips_text_before_handoff():
    """Tekst vóór een handoff (bv. de router die 'ik geef je door' meldt) is
    geen antwoord; alleen de agent na de laatste handoff spreekt de gebruiker
    aan. Shape uit een echte conversatie (2026-11-12)."""
    import mistral_client

    outputs = [
        {
            "type": "message.output",
            "agent_id": "ag_router",
            "content": "Deze vraag gaat over leeftijdscategorieën, wat valt onder "
            "KNWU-regels. Ik geef de vraag door aan de juiste agent.",
        },
        {
            "type": "agent.handoff",
            "previous_agent_name": "router-agent",
            "next_agent_name": "knwu-agent",
        },
        {
            "type": "message.output",
            "agent_id": "ag_knwu",
            "content": [{"type": "text", "text": "Wat is het geboortejaar van je zoon?"}],
        },
    ]
    assert mistral_client.extract_text(outputs) == "Wat is het geboortejaar van je zoon?"


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
    assert "background: var(--accent);" in body_css
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


def test_wielie_source_image_served_but_not_in_offline_shell(tmp_path):
    # wielie.jpg is alleen de bron voor de iconen; geen scherm toont hem.
    client = make_client(tmp_path)
    assert client.get("/wielie.jpg").status_code == 200
    assert '"/wielie.jpg"' not in client.get("/sw.js").text


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


def test_mistral_timeout_default_180():
    # review 2026-11-12: websearch/handoff-runs liepen op de 60s in een timeout
    import mistral_client

    assert mistral_client.DEFAULT_TIMEOUT == 180


def test_index_shows_thinking_message(tmp_path):
    client = make_client(tmp_path)
    assert "Wielie denkt na…" in client.get("/").text


def fake_mistral(monkeypatch) -> list[dict]:
    """Zet de app in Mistral-mode met gemockte intake + stream_answer (#91/#93);
    geef de stream-calls. De intake-fallback routeert naar de router."""
    import config
    import intake
    import mistral_client

    calls: list[dict] = []

    def classify_message(**kwargs):
        return dict(intake.FALLBACK)

    def stream_answer(**kwargs):
        calls.append(kwargs)
        return "mistral-conv-1", "antwoord"

    def answer_question(**kwargs):
        calls.append(kwargs)
        return "mistral-conv-1", "antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", classify_message)
    monkeypatch.setattr(mistral_client, "stream_answer", stream_answer)
    monkeypatch.setattr(mistral_client, "answer_question", answer_question)
    return calls


def test_chat_adds_date_and_metadata_on_new_conversation(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    body = chat(client, "Wanneer is de volgende wedstrijd?")
    sent = calls[0]
    assert sent["message"].startswith("Wanneer is de volgende wedstrijd?")
    assert "maandag 9 november 2026" in sent["message"]
    assert sent["conversation_id"] is None
    assert sent["metadata"] == {"app_conversation_id": body["conversation_id"]}


def test_chat_follow_up_adds_category_but_no_date(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    first = chat(client, "In welke leeftijdscategorie rijdt mijn zoon?")
    # #91: een kaal jaartal als vervolg is zélf een deterministische bypass
    # (direct app-antwoord, geen Mistral-call) — zie test_lookup_bypass_follow_up
    chat_in(client, first["conversation_id"], "2015", "test-client")
    # een vervolgvraag mét jaartal die méér vraagt dan het kale feit gaat wél
    # naar de agent, mét categorie-contextregel maar zonder datumregel
    chat_in(client, first["conversation_id"], "2015, en mag hij dan meedoen aan het NK?", "test-client")
    follow_up = calls[1]["message"]
    assert calls[1]["conversation_id"] == "mistral-conv-1"
    assert "november 2026" not in follow_up
    assert "wegwielrennen 2026: U12" in follow_up


def test_chat_sends_language_level_context(tmp_path, monkeypatch):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    body = chat_raw(client, {"message": "Hoeveel kost een licentie?", "client_id": "c", "language_level": "B2"})
    assert "vastgesteld taalniveau: B2" in calls[0]["message"]
    # ook op een vervolgbericht (zonder datumregel) staat de taalniveau-regel
    body2 = chat_raw(client, {
        "message": "en voor mijn dochter?",
        "conversation_id": body["conversation_id"],
        "client_id": "c",
        "language_level": "B2",
    })
    follow_up = calls[1]["message"]
    assert "vastgesteld taalniveau: B2" in follow_up
    assert "november 2026" not in follow_up


def test_chat_language_level_defaults_to_b1(tmp_path, monkeypatch):
    calls = fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    # geen language_level meegestuurd
    chat_raw(client, {"message": "vraag", "client_id": "c"})
    assert "vastgesteld taalniveau: B1" in calls[0]["message"]
    # ongeldige waarde: geen 400, maar B1
    chat_raw(client, {"message": "vraag", "client_id": "c", "language_level": "van alles"})
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


# --- Bronconflict-marker (#47) ---

MARKER = (
    "[BRONCONFLICT] TITEL_20 art. 20.0.004: U17 Nieuweling | "
    "https://kenniscentrum.knwu.nl/knwu-licenties/knwu-wedstrijdlicentie-u17: U16 en U17"
)
# wat er in de DB-rij `text` staat: de inhoud van de markerregel, zonder the tag zelf
MARKER_CONTENT = MARKER.removeprefix("[BRONCONFLICT]").strip()


def fake_mistral_answer(monkeypatch, answer: str) -> None:
    import config
    import intake
    import mistral_client

    def stream_answer(**kwargs):
        return "conv-1", answer

    def answer_question(**kwargs):
        return "conv-1", answer

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", lambda **kwargs: dict(intake.FALLBACK))
    monkeypatch.setattr(mistral_client, "stream_answer", stream_answer)
    monkeypatch.setattr(mistral_client, "answer_question", answer_question)


def test_save_feedback_bronconflict_stores_marker_text_only(tmp_path):
    db = str(tmp_path / "test.db")
    store.init_db(db)
    store.save_feedback(db, rating="bronconflict", conversation_id="c1", text=MARKER_CONTENT)
    rows = store.all_feedback(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["rating"] == "bronconflict"
    assert row["conversation_id"] == "c1"
    assert row["text"] == MARKER_CONTENT
    # privacy: géén vraag/antwoord/history bij een bronconflict
    assert row["question"] is None
    assert row["answer"] is None
    assert row["history"] is None


def test_chat_strips_bronconflict_marker_and_stores_row(tmp_path, monkeypatch):
    fake_mistral_answer(monkeypatch, f"U17 Nieuweling volgens Titel 20.\n\nBron: TITEL_20.pdf\n\n{MARKER}")
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    body = chat(client, "Welke leeftijdscategorie is een 15-jarige in 2026?")
    # de gebruiker ziet de markerregel niet
    assert "BRONCONFLICT" not in body["answer"]
    assert "U17 Nieuweling" in body["answer"]
    rows = store.all_feedback(db)
    assert len(rows) == 1
    assert rows[0]["rating"] == "bronconflict"
    assert rows[0]["text"] == MARKER_CONTENT
    assert rows[0]["conversation_id"] == body["conversation_id"]
    assert rows[0]["question"] is None
    assert rows[0]["answer"] is None


def test_chat_without_marker_stores_no_bronconflict_row(tmp_path, monkeypatch):
    fake_mistral_answer(monkeypatch, "Gewoon antwoord.\n\nBron: TITEL_20.pdf")
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    body = chat(client, "vraag")
    assert body["answer"] == "Gewoon antwoord.\n\nBron: TITEL_20.pdf"
    assert store.all_feedback(db) == []


def test_chat_multiple_markers_one_row_each(tmp_path, monkeypatch):
    fake_mistral_answer(
        monkeypatch,
        f"Antwoord.\n\n{MARKER}\n\n[BRONCONFLICT] Nationale_Besluiten art. 18.1: X | https://voorbeeld.nl: Y",
    )
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    body = chat(client, "vraag")
    assert "BRONCONFLICT" not in body["answer"]
    rows = store.all_feedback(db)
    assert len(rows) == 2
    assert all(r["rating"] == "bronconflict" for r in rows)
    assert rows[0]["text"] == MARKER_CONTENT
    assert rows[1]["text"] == "Nationale_Besluiten art. 18.1: X | https://voorbeeld.nl: Y"


def test_bronconflict_marker_not_in_feedback_history(tmp_path, monkeypatch):
    fake_mistral_answer(monkeypatch, f"Antwoord met conflict.\n\n{MARKER}")
    db = str(tmp_path / "test.db")
    client = make_client(tmp_path)
    conv = chat(client, "vraag")
    client.post(
        "/feedback",
        json={"conversation_id": conv["conversation_id"], "rating": "negative", "text": "toch fout"},
    )
    rows = store.all_feedback(db)
    assert len(rows) == 2
    conflict_row = next(r for r in rows if r["rating"] == "bronconflict")
    negative_row = next(r for r in rows if r["rating"] == "negative")
    assert conflict_row["text"] == MARKER_CONTENT  # alleen de marker, géén vraag/antwoord
    assert conflict_row["question"] is None and conflict_row["answer"] is None
    # de marker zit ook niet in de feedbackgeschiedenis
    assert "BRONCONFLICT" not in (negative_row["answer"] or "")
    history = json.loads(negative_row["history"])
    assert "BRONCONFLICT" not in history[0]["answer"]


# --- Non-blocking event loop (#80) ---


def test_chat_does_not_block_healthz_during_slow_mistral_call(tmp_path, monkeypatch):
    """#80: de blocking Mistral-call draait off-loop (run_in_threadpool). Tijdens
    een trage answer_question moet een gelijktijdige GET /healthz reageren vóórdat
    de Mistral-call klaar is. Bewust een ordering-assert (geen wall-clock):
    deterministisch, en faalt nog steeds tegen de blocking variant uit HEAD."""
    import httpx

    import config
    import intake
    import mistral_client

    release = threading.Event()
    mock_started = threading.Event()
    healthz_done: list[bool] = []
    mock_saw_healthz_done: list[bool] = []

    def slow_stream_answer(**kwargs):
        mock_started.set()
        # safety-timeout: bij een regressie (blocking call in de event loop) faalt
        # de assert onderaan in plaats van dat de test blijft hangen
        release.wait(timeout=5)
        mock_saw_healthz_done.append(bool(healthz_done))
        return "conv-slow", "traag antwoord"

    def instant_check_reachable(**kwargs):
        return True

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", lambda **kwargs: dict(intake.FALLBACK))
    monkeypatch.setattr(mistral_client, "stream_answer", slow_stream_answer)
    monkeypatch.setattr(mistral_client, "check_reachable", instant_check_reachable)

    app = create_app(db_path=str(tmp_path / "t.db"))

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            chat_task = asyncio.create_task(
                ac.post("/chat", json={"message": "trage vraag", "client_id": "c1"})
            )
            # wacht tot de gemockte Mistral-call echt begonnen is (in de buggy
            # variant blokkeert die call de loop en draait deze poll pas erna)
            for _ in range(500):
                if mock_started.is_set():
                    break
                await asyncio.sleep(0.01)
            health = await ac.get("/healthz")
            healthz_done.append(True)  # healthz reageerde vóór de Mistral-call klaar was
            release.set()
            chat_resp = await chat_task
            # poll de job-status tot done (#85)
            job_id = chat_resp.json()["job_id"]
            for _ in range(500):
                status_resp = await ac.get(f"/chat/status/{job_id}")
                if status_resp.json()["status"] in ("done", "error"):
                    break
                await asyncio.sleep(0.01)
            return health, chat_resp, status_resp

    health, chat_resp, status_resp = asyncio.run(run())

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "mistral_configured": True,
        "mistral_reachable": True,
    }
    assert chat_resp.status_code == 202  # #85: non-blocking, direct job-id
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "done"
    assert status_resp.json()["answer"] == "traag antwoord"
    # toen de trage Mistral-call klaar was, was /healthz allang gereageerd
    assert mock_saw_healthz_done == [True]


# --- Status-endpoint (#85) ---


def test_chat_returns_202_with_job_id_in_mistral_mode(tmp_path, monkeypatch):
    """#85: in Mistral-mode returnt /chat direct 202 + job_id."""
    fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "vraag", "client_id": "c"})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["job_id"]
    assert body["conversation_id"]


def test_status_endpoint_404_for_unknown_job(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/chat/status/" + "0" * 32)
    assert resp.status_code == 404


def test_status_endpoint_returns_done_with_answer(tmp_path, monkeypatch):
    """#85: na afronding van de job geeft de status-endpoint done + answer."""
    fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "vraag", "client_id": "c"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    result = _wait_for_job(client, job_id)
    assert result["status"] == "done"
    assert result["answer"] == "antwoord"
    assert result["conversation_id"]


def test_status_endpoint_returns_error_on_mistral_failure(tmp_path, monkeypatch):
    """#85: bij een fout in de background task geeft de status error."""
    import config
    import intake
    import mistral_client

    def failing_stream(**kwargs):
        raise RuntimeError("Mistral API timeout na 180s")

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", lambda **kwargs: dict(intake.FALLBACK))
    monkeypatch.setattr(mistral_client, "stream_answer", failing_stream)
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "vraag", "client_id": "c"})
    assert resp.status_code == 202
    result = _wait_for_job(client, resp.json()["job_id"])
    assert result["status"] == "error"
    assert "timeout" in result["error"].lower()


def test_category_followup_returns_answer_from_flat_mistral_stream(tmp_path, monkeypatch):
    from unittest.mock import Mock

    import intake
    import mistral_client

    lines = [
        "data: " + json.dumps(payload) for payload in [
            {"type": "conversation.response.started", "conversation_id": "conv-knwu"},
            {"type": "message.output.delta", "content": {
                "type": "thinking", "thinking": [{"type": "text", "text": "Niet tonen"}],
            }},
            {"type": "message.output.delta", "content": "Antwoord over het verzet."},
            {"type": "conversation.response.done", "usage": {}},
        ]
    ]
    response = Mock()
    response.iter_lines.return_value = iter(lines)
    post = Mock(return_value=response)
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(config, "EXPERT_AGENT_IDS", {"knwu": "knwu-id"})
    monkeypatch.setattr(
        intake, "classify_message",
        lambda **kwargs: {**dict(intake.FALLBACK), "domein": "knwu", "confidence": 0.95},
    )
    monkeypatch.setattr(mistral_client.requests, "post", post)
    client = make_client(tmp_path)
    first = client.post("/chat", json={"message": "wat is categorie 1", "client_id": "c"})
    assert first.status_code == 200
    post.assert_not_called()
    followup = client.post("/chat", json={
        "message": "Waarom is het verzet voor U8 beperkt?",
        "conversation_id": first.json()["conversation_id"],
        "client_id": "c",
    })
    assert followup.status_code == 202
    result = _wait_for_job(client, followup.json()["job_id"])
    assert result["status"] == "done", result
    assert result["answer"] == "Antwoord over het verzet."
    assert result["route"] == "direct-knwu"
    assert result["conversation_id"] == first.json()["conversation_id"]
    assert post.call_args.kwargs["json"]["agent_id"] == "knwu-id"


def test_stub_mode_still_returns_200_synchronously(tmp_path):
    """#85: zonder Mistral-config blijft /chat synchroon 200 (stub-mode)."""
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "vraag", "client_id": "c"})
    assert resp.status_code == 200
    assert "STUB" in resp.json()["answer"]


# --- Deterministische bypass + intake-route + fasen (#88/#91/#93) ---


def test_lookup_bypass_in_mistral_mode_returns_200_direct(tmp_path, monkeypatch):
    """#91: pure lookup in Mistral-mode -> synchroon 200, 0 LLM-calls, geen job."""
    from datetime import date

    import config
    import intake
    import mistral_client

    calls: list[dict] = []
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(
        intake, "classify_message", lambda **kw: calls.append(("intake", kw)) or dict(intake.FALLBACK)
    )
    monkeypatch.setattr(
        mistral_client, "stream_answer", lambda **kw: calls.append(("stream", kw)) or ("conv", "x")
    )
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    resp = client.post(
        "/chat",
        json={
            "message": "In welke leeftijdscategorie rijdt een jongen geboren in 2015 bij wegwielrennen?",
            "client_id": "c",
        },
    )
    assert resp.status_code == 200  # geen 202/job: het antwoord verschijnt direct
    answer = resp.json()["answer"]
    assert "**Geboortejaar 2015**" in answer
    assert "### Wegwielrennen 2027 · Jongens" in answer
    assert "**Categorie:** U13" in answer
    assert "Meisjes" not in answer
    assert calls == []  # 0 LLM-calls


@pytest.fixture
def lookup_client(tmp_path):
    def make(today: date = date(2026, 11, 9)) -> TestClient:
        return open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: today))

    return make


def post_in(client: TestClient, conversation_id: str, message: str, **extra):
    payload = {"message": message, "conversation_id": conversation_id, "client_id": "test-client"}
    return client.post("/chat", json={**payload, **extra})


def season_headings(answer: str) -> list[str]:
    return [line for line in answer.splitlines() if line.startswith("### ")]


def test_lookup_bypass_follow_up_bare_year(lookup_client, monkeypatch):
    """#91 besluit 5 + #125: een kaal jaartal vult de openstaande vraag aan, met
    het geslacht uit die vraag."""
    calls = fake_mistral(monkeypatch)
    client = lookup_client()
    first = chat(client, "In welke leeftijdscategorie rijdt mijn zoon?")
    assert len(calls) == 1  # eerste vraag ging naar de agent
    resp = post_in(client, first["conversation_id"], "2015")
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "**Categorie:** U13" in answer
    assert season_headings(answer) == [
        "### Veldrijden 2026-2027 · Jongens",
        "### Wegwielrennen 2027 · Jongens",
    ]
    assert len(calls) == 1  # geen extra Mistral-call voor de lookup


def test_discipline_reply_filters_a_completed_overview_without_model_calls(lookup_client, monkeypatch):
    calls = fake_mistral(monkeypatch)
    client = lookup_client()
    first = chat(client, "wat is categorie 1")
    question = post_in(client, first["conversation_id"], "wlk verzet voor u8")
    assert question.status_code == 200
    assert "Veldrijden" in question.json()["answer"]
    assert "Oude cat." not in question.json()["answer"]  # nieuwe vraag erft niets

    resp = post_in(client, first["conversation_id"], "weg", language_level="B2")

    assert resp.status_code == 200, "De discipline-aanvulling moet lokaal bypassen, niet naar een agent."
    answer = resp.json()["answer"]
    assert season_headings(answer) == [
        "### Wegwielrennen 2027 · Jongens · geboortejaar 2020",
        "### Wegwielrennen 2027 · Meisjes · geboortejaar 2020",
    ]
    assert "5,50 meter" in answer
    assert "artikel 20.1.007" in answer
    assert calls == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Welke categorie is categorie 3 in de nieuwe indeling?", ("**Oude cat. 3 (JO11/MO12)**",)),
        ("Welke oude categorie is JO11/MO12?", ("**JO11/MO12**", "U11 (oude cat. 3)", "U12 (oude cat. 3)")),
        ("Welke oude categorie is U12?", ("**U12**", "U12 (oude cat. 4)", "U12 (oude cat. 3)")),
        ("JO11/MO12 in de oude indeling?", ("**JO11/MO12**", "U11 (oude cat. 3)")),
        ("Welke categorie voor geboortejaar 2015?", ("**Geboortejaar 2015**", "U13 (oude cat. 5)")),
        ("Wat is de leeftijdscategorie voor geboortejaar 2015?", ("**Geboortejaar 2015**", "U13")),
        ("Welke categorie, verzet en licentie voor geboortejaar 2014?", ("U14", "**Licentie:** U17")),
        ("Welk verzet voor categorie 3 op de weg?", ("U11", "U12", "5,90 meter")),
        ("Welk verzet voor categorie 2 op de weg?", ("U10", "5,50 meter", "U11")),
        ("Welk verzet voor geboortejaar 2015 op de weg?", ("U13", "6,30 meter")),
        ("Welk verzet voor geboortejaar 2020 in het veld?", ("U8", "NVT")),
    ],
)
def test_category_and_gearing_lookup_routes(lookup_client, monkeypatch, message, expected):
    calls = fake_mistral(monkeypatch)
    client = lookup_client()
    resp = client.post("/chat", json={"message": message, "client_id": "test-client"})
    assert resp.status_code == 200, "Een pure categorie- of verzetvraag moet lokaal worden beantwoord."
    for fragment in expected:
        assert fragment in resp.json()["answer"]
    answer_lines = resp.json()["answer"].splitlines()
    # een initiële verzetvraag voor de weg krijgt het hulpaanbod (#150), de rest de bibliotheekvraag
    offers_help = message.startswith("Welk verzet") and "op de weg" in message
    assert answer_lines[-1] == (
        "Heb je hulp nodig bij het controleren of aanpassen van het verzet van je fiets?"
        if offers_help
        else "Moet ik de KNWU-documenten doorzoeken voor een gedetailleerder antwoord?"
    )
    assert not any(line.startswith("Bron:") for line in answer_lines), "B1 heeft geen bronregel"
    assert calls == []

def test_gearing_question_is_completed_by_a_bare_year_without_discipline(lookup_client, monkeypatch):
    """#125: `Welk verzet?` -> `2012` geeft het volledige overzicht; discipline is
    optioneel. Een latere discipline of nieuw jaar werkt op dat profiel."""
    calls = fake_mistral(monkeypatch)
    client = lookup_client()
    first = chat(client, "Welk verzet?")
    assert len(calls) == 1

    year = post_in(client, first["conversation_id"], "2012")
    assert year.status_code == 200
    assert {line.split(" · ")[0] for line in season_headings(year.json()["answer"])} == {
        "### Veldrijden 2026-2027",
        "### Wegwielrennen 2027",
    }
    road = post_in(client, first["conversation_id"], "weg")
    assert road.status_code == 200
    assert "7,68 meter" in road.json()["answer"]
    assert "Veldrijden" not in road.json()["answer"]
    next_year = post_in(client, first["conversation_id"], "2014")
    assert next_year.status_code == 200
    assert "**Geboortejaar 2014**" in next_year.json()["answer"]
    assert "**Categorie:** U14" in next_year.json()["answer"]
    assert "Veldrijden" not in next_year.json()["answer"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "previous_question",
    ["Waarom is het verzet voor U8 op de weg beperkt?", "Wanneer is de volgende clubtraining?"],
)
def test_short_reply_does_not_reuse_explanation_or_unrelated_context(
    tmp_path, monkeypatch, previous_question
):
    calls = fake_mistral(monkeypatch)
    client = make_client(tmp_path)
    first = chat(client, previous_question)
    resp = client.post(
        "/chat",
        json={"message": "weg", "conversation_id": first["conversation_id"], "client_id": "test-client"},
    )
    assert resp.status_code == 202
    assert _wait_for_job(client, resp.json()["job_id"])["status"] == "done"
    assert len(calls) == 2
    assert calls[-1]["message"].startswith("weg\n")
    assert previous_question not in calls[-1]["message"]


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("U13", "6,30 meter"),
        ("nieuwelingen", "7,68 meter"),
        ("geboortejaar 2015", "5,90 meter"),
    ],
)
def test_gearing_lookup_after_category_or_birth_year_clarification(
    tmp_path, monkeypatch, reply, expected
):
    from datetime import date

    calls = fake_mistral(monkeypatch)
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    first = chat(client, "Welk verzet op de weg?")
    resp = client.post(
        "/chat",
        json={"message": reply, "conversation_id": first["conversation_id"], "client_id": "test-client"},
    )
    assert resp.status_code == 200
    assert expected in resp.json()["answer"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("JO11/MO12", ("Jongens · geboortejaar 2017", "Meisjes · geboortejaar 2016", "5,90 meter")),
        ("MU12, VU13", ("**Categorie:** U12", "**Categorie:** U13", "5,90 meter")),
    ],
)
def test_gearing_lookup_after_combined_category_clarification(
    tmp_path, monkeypatch, reply, expected
):
    from datetime import date

    fake_mistral(monkeypatch)
    client = open_client(create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9)))
    first = chat(client, "Welk verzet op de weg?")
    resp = chat_in(client, first["conversation_id"], reply, "test-client")
    for fragment in expected:
        assert fragment in resp["answer"]


def test_lookup_bypass_b2_heeft_bron_regel(lookup_client, monkeypatch):
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    client = lookup_client()
    resp = client.post(
        "/chat",
        json={
            "message": "Welke licentie heeft mijn zoon nodig? Hij is geboren in 2012.",
            "client_id": "c",
            "language_level": "B2",
        },
    )
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "**Licentie:** U17" in answer
    assert "artikel 20.0.002" in answer
    assert answer.splitlines()[-1].startswith("Bron:")


def install_lookup_mistral(monkeypatch, classify) -> list[tuple[str, dict]]:
    """Mistral-mode met de gegeven nep-intake; geef alle modelcalls (intake en agent)."""
    import intake
    import mistral_client

    model_calls: list[tuple[str, dict]] = []

    def recorded_classify(**kwargs):
        model_calls.append(("intake", kwargs))
        return classify(**kwargs)

    def stream(**kwargs):
        model_calls.append(("agent", kwargs))
        return "mistral-conv-1", "antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", recorded_classify)
    monkeypatch.setattr(mistral_client, "stream_answer", stream)
    monkeypatch.setattr(mistral_client, "answer_question", stream)
    return model_calls


def overview_rows(answer: str) -> list[tuple[str, str, str]]:
    """(discipline, geslacht, categorie) per seizoensblok van een overzicht."""
    rows: list[tuple[str, str, str]] = []
    heading: list[str] = []
    for line in answer.splitlines():
        if line.startswith("### "):
            heading = line.removeprefix("### ").split(" · ")
        elif line.startswith("- **Categorie:** ") and heading:
            category = line.removeprefix("- **Categorie:** ").split(" (")[0]
            rows.append((heading[0].split()[0], heading[1], category))
    return rows


def test_current_intake_completion_bypasses_and_commits_the_profile(lookup_client, monkeypatch):
    import intake

    model_calls = install_lookup_mistral(
        monkeypatch, lambda **kw: {**intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2012}
    )
    client = lookup_client()
    resp = client.post("/chat", json={"message": "Welk verzet? 2012", "client_id": "c"})
    assert resp.status_code == 202
    result = _wait_for_job(client, resp.json()["job_id"])
    assert result["route"] == "bypass"
    assert "**Geboortejaar 2012**" in result["answer"]
    assert [kind for kind, _ in model_calls] == ["intake"]

    followup = post_in(client, result["conversation_id"], "alleen meisjes")

    assert followup.status_code == 200
    assert "**Geboortejaar 2012**" in followup.json()["answer"]
    assert {gender for _, gender, _ in overview_rows(followup.json()["answer"])} == {"Meisjes"}
    assert [kind for kind, _ in model_calls] == ["intake"]


def test_positive_reply_to_the_verzet_offer_starts_the_verzet_agent_with_the_bypass_facts(
    lookup_client, monkeypatch
):
    import intake
    import lookups

    model_calls = install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    monkeypatch.setattr(config, "EXPERT_AGENT_IDS", {"verzet": "verzet-id"})
    client = lookup_client()
    first = client.post(
        "/chat", json={"message": "Welk verzet mag mijn zoon uit 2014?", "client_id": "c"}
    )
    assert first.status_code == 200
    assert first.json()["answer"].splitlines()[-1] == lookups.VERZET_OFFER

    reply = post_in(client, first.json()["conversation_id"], "ja graag")

    assert reply.status_code == 202
    result = _wait_for_job(client, reply.json()["job_id"])
    assert result["route"] == "direct-verzet"
    assert [kind for kind, _ in model_calls] == ["agent"]
    request = model_calls[0][1]
    assert request["agent_id"] == "verzet-id"
    for fact in ("2014", "jongens", "U14", "6,30 meter", "20.1.007"):
        assert fact in str(request["message"])


def test_other_reply_to_the_verzet_offer_follows_the_normal_route(lookup_client, monkeypatch):
    import intake

    model_calls = install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    monkeypatch.setattr(config, "EXPERT_AGENT_IDS", {"verzet": "verzet-id"})
    client = lookup_client()
    first = client.post(
        "/chat", json={"message": "Welk verzet mag mijn zoon uit 2014?", "client_id": "c"}
    )

    reply = post_in(client, first.json()["conversation_id"], "nee, maar wat is de NK-datum?")

    result = _wait_for_job(client, reply.json()["job_id"])
    assert result["route"] == "router"
    assert [kind for kind, _ in model_calls] == ["intake", "agent"]
    assert model_calls[1][1]["agent_id"] == "router-id"


def test_intake_cannot_invent_a_birth_year_but_the_pending_question_remains(lookup_client, monkeypatch):
    import intake

    model_calls = install_lookup_mistral(
        monkeypatch,
        lambda **kw: {**intake.FALLBACK, "intentie": "lookup", "domein": "knwu", "geboortejaar": 2012},
    )
    client = lookup_client()
    first = client.post("/chat", json={"message": "Welke licentie heb ik nodig?", "client_id": "c"})
    result = _wait_for_job(client, first.json()["job_id"])
    assert result["route"] == "router"
    assert [kind for kind, _ in model_calls] == ["intake", "agent"]

    reply = post_in(client, result["conversation_id"], "2012")

    assert reply.status_code == 200
    assert "**Geboortejaar 2012**" in reply.json()["answer"]
    assert len(model_calls) == 2


@pytest.mark.parametrize(
    ("today", "messages", "heading", "expected_rows"),
    [
        pytest.param(
            date(2026, 6, 1),
            ["Welke categorie voor jongen uit 2015, U12, weg?", "en voor 2017?"],
            "**Geboortejaar 2017**",
            {("Wegwielrennen", "Jongens", "U10")},
            id="new-primary-replaces-category-keeps-filters",
        ),
        pytest.param(
            date(2026, 6, 1),
            ["Welke categorie voor jongen uit 2015, U12, weg?", "Welke categorie voor geboortejaar 2017?"],
            "**Geboortejaar 2017**",
            {
                ("Wegwielrennen", "Jongens", "U10"),
                ("Wegwielrennen", "Meisjes", "U10"),
                ("Veldrijden", "Jongens", "U11"),
                ("Veldrijden", "Meisjes", "U11"),
            },
            id="standalone-question-inherits-nothing",
        ),
        pytest.param(
            date(2026, 11, 9),
            ["Welke categorie voor JO11?", "alleen meisjes"],
            "**U11**",
            {("Veldrijden", "Meisjes", "U11"), ("Wegwielrennen", "Meisjes", "U11")},
            id="gender-replaces-single-prefix",
        ),
        pytest.param(
            date(2026, 11, 9),
            ["Welke categorie voor JO11/MO12?", "alleen meisjes"],
            "**JO11/MO12**",
            {("Veldrijden", "Meisjes", "U12"), ("Wegwielrennen", "Meisjes", "U12")},
            id="gender-filters-paired-category",
        ),
        pytest.param(
            date(2026, 11, 9),
            ["oude cat. 1", "alleen meisjes"],
            "**Oude cat. 1 (JO9/MO10)**",
            {
                ("Veldrijden", "Meisjes", "U9"),
                ("Veldrijden", "Meisjes", "U10"),
                ("Wegwielrennen", "Meisjes", "U9"),
                ("Wegwielrennen", "Meisjes", "U10"),
            },
            id="gender-filters-old-category-mapping",
        ),
    ],
)
def test_lookup_followups_use_the_conversation_profile_without_model_calls(
    lookup_client, monkeypatch, today, messages, heading, expected_rows
):
    import intake

    model_calls = install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    client = lookup_client(today)
    conversation_id = "profiel"
    for message in messages:
        resp = post_in(client, conversation_id, message)
        assert resp.status_code == 200, message
    answer = resp.json()["answer"]
    assert answer.startswith(heading)
    assert set(overview_rows(answer)) == expected_rows
    assert model_calls == []


@pytest.mark.parametrize(
    "messages",
    [
        ["Welke categorie voor geboortejaar 2015 bij wegwielrennen?", "Waarom?", "alleen meisjes"],
        ["Welke categorie voor JO11?", "Welke categorie voor JO11 meisjes?", "alleen veldrijden"],
        ["Welke categorie voor JO11?", "Wanneer is de volgende clubtraining?", "en voor 2017?"],
    ],
    ids=["same-topic-why", "contradiction-in-one-message", "topic-change"],
)
def test_substantive_or_rejected_turn_ends_profile_reuse(lookup_client, monkeypatch, messages):
    import intake

    model_calls = install_lookup_mistral(
        monkeypatch, lambda **kw: {**intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2015}
    )
    client = lookup_client()
    first, middle, fragment = messages
    assert post_in(client, "reset", first).status_code == 200
    middle_result = _wait_for_job(client, post_in(client, "reset", middle).json()["job_id"])
    assert middle_result["route"] == "router"

    resp = post_in(client, "reset", fragment)

    assert resp.status_code == 202
    assert _wait_for_job(client, resp.json()["job_id"])["route"] == "router"
    assert model_calls[-1][0] == "agent"
    assert model_calls[-1][1]["message"].startswith(fragment)


def test_lookup_state_is_isolated_per_conversation(lookup_client, monkeypatch):
    import intake

    install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    client = lookup_client()
    assert post_in(client, "a", "Welke categorie voor JO11?").status_code == 200

    other = post_in(client, "b", "alleen meisjes")
    same = post_in(client, "a", "alleen meisjes")

    assert other.status_code == 202
    assert same.status_code == 200


QUESTION_ABOUT_CLUB_RACE = (
    "Aan welke voorwaarden moet mijn dochter voldoen om mee te doen aan een clubwedstrijd?"
)


def test_bare_year_after_restart_is_a_first_turn_again(lookup_client, monkeypatch):
    """#143 S11: een herstart wist lookup-toestand en agentgesprek; een kaal
    jaartal is dan weer een eigen lookup."""
    import intake

    install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    before_restart = lookup_client()
    question = post_in(before_restart, "conv", QUESTION_ABOUT_CLUB_RACE)
    assert _wait_for_job(before_restart, question.json()["job_id"])["status"] == "done"

    after_restart = lookup_client()

    assert post_in(after_restart, "conv", "2014").status_code == 200


def test_bare_year_sent_while_the_agent_answers_goes_to_the_agent(lookup_client, monkeypatch):
    """#143 S12: de beurt telt al bij acceptatie, niet pas als het agentantwoord er is."""
    import intake
    import mistral_client

    install_lookup_mistral(monkeypatch, lambda **kw: dict(intake.FALLBACK))
    agent_started = threading.Event()
    release_agent = threading.Event()

    def slow_stream(**kwargs):
        agent_started.set()
        if not release_agent.wait(timeout=5):
            raise AssertionError("agentantwoord werd niet vrijgegeven")
        return "mistral-conv-1", "antwoord"

    monkeypatch.setattr(mistral_client, "stream_answer", slow_stream)
    client = lookup_client()
    question = post_in(client, "conv", QUESTION_ABOUT_CLUB_RACE)
    assert agent_started.wait(timeout=5)

    year = post_in(client, "conv", "2014")
    release_agent.set()

    assert year.status_code == 202
    assert _wait_for_job(client, question.json()["job_id"])["status"] == "done"
    assert _wait_for_job(client, year.json()["job_id"])["route"] == "router"


@pytest.mark.parametrize("older_outcome", ["success", "failure"])
@pytest.mark.parametrize(
    ("newer_message", "newer_keeps_profile"),
    [("Welke categorie voor JO11?", True), ("Waarom?", False)],
    ids=["newer-completed", "newer-cleared"],
)
def test_older_intake_job_cannot_overwrite_newer_lookup_state(
    tmp_path, monkeypatch, older_outcome, newer_message, newer_keeps_profile
):
    """#136: een oudere intake-job die pas na een nieuwere beurt klaar is,
    publiceert geen lookup-toestand meer; zijn eigen antwoord/status blijft."""
    import httpx

    import intake

    older_message = "Welk verzet? 2012"
    older_started = threading.Event()
    release_older = threading.Event()

    def classify(**kwargs):
        if kwargs["message"] != older_message:
            return dict(intake.FALLBACK)
        older_started.set()
        if not release_older.wait(timeout=5):
            raise AssertionError("oudere intake werd niet vrijgegeven")
        if older_outcome == "failure":
            raise RuntimeError("intake viel om")
        return {**intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2012}

    install_lookup_mistral(monkeypatch, classify)
    app = create_app(db_path=str(tmp_path / "t.db"), today=lambda: date(2026, 11, 9))

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:

            async def post(message: str):
                return await ac.post(
                    "/chat", json={"message": message, "conversation_id": "conv", "client_id": "c"}
                )

            async def finished(job_id: str) -> dict:
                for _ in range(500):
                    body = (await ac.get(f"/chat/status/{job_id}")).json()
                    if body["status"] in ("done", "error"):
                        return body
                    await asyncio.sleep(0.01)
                raise AssertionError(f"job {job_id} werd niet klaar")

            older = await post(older_message)
            assert older.status_code == 202
            assert await asyncio.to_thread(older_started.wait, 5)
            newer = await post(newer_message)
            if newer.status_code == 202:
                assert (await finished(newer.json()["job_id"]))["status"] == "done"
            release_older.set()
            older_result = await finished(older.json()["job_id"])
            followup = await post("alleen meisjes")
            if followup.status_code == 202:
                return older_result, 202, await finished(followup.json()["job_id"])
            return older_result, followup.status_code, followup.json()

    older_result, followup_status, followup = asyncio.run(run())

    if older_outcome == "success":
        assert older_result["status"] == "done"
        assert older_result["route"] == "bypass"
        assert "**Geboortejaar 2012**" in older_result["answer"]
    else:
        assert older_result["status"] == "error"
    if newer_keeps_profile:
        assert followup_status == 200
        assert set(overview_rows(followup["answer"])) == {
            ("Veldrijden", "Meisjes", "U11"),
            ("Wegwielrennen", "Meisjes", "U11"),
        }
    else:
        assert followup_status == 202
        assert followup["route"] == "router"


def test_direct_to_expert_route_uses_expert_env_id(tmp_path, monkeypatch):
    """#88/#91: intake met hoge confidence start direct bij de expert, niet bij de router."""
    import config
    import intake
    import mistral_client

    stream_calls: list[dict] = []

    def classify(**kwargs):
        return {
            "intentie": "regelgeving",
            "domein": "club",
            "discipline": "onbekend",
            "geboortejaar": None,
            "leeftijd": None,
            "confidence": 0.95,
        }

    def stream(**kwargs):
        stream_calls.append(kwargs)
        return "conv-c", "clubantwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(
        config, "EXPERT_AGENT_IDS", {"knwu": "ag_knwu", "regio": "", "club": "ag_club", "archief": ""}
    )
    monkeypatch.setattr(intake, "classify_message", classify)
    monkeypatch.setattr(mistral_client, "stream_answer", stream)
    client = make_client(tmp_path)
    body = chat(client, "Wat kost de contributie bij WTC Woerden?")
    assert body["answer"] == "clubantwoord"
    assert stream_calls[0]["agent_id"] == "ag_club"  # direct-to-expert, router overgeslagen
    assert stream_calls[0]["prompt_cache_key"] == config.PROMPT_CACHE_KEY


def test_router_route_when_confidence_low(tmp_path, monkeypatch):
    import config
    import intake
    import mistral_client

    stream_calls: list[dict] = []

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(config, "EXPERT_AGENT_IDS", {"knwu": "ag_knwu", "regio": "", "club": "", "archief": ""})
    monkeypatch.setattr(
        intake,
        "classify_message",
        lambda **kw: {**dict(intake.FALLBACK), "domein": "knwu", "confidence": 0.4},
    )
    monkeypatch.setattr(
        mistral_client, "stream_answer", lambda **kw: stream_calls.append(kw) or ("conv-r", "routerantwoord")
    )
    client = make_client(tmp_path)
    resp = client.post("/chat", json={"message": "Iets vaags over een wedstrijd", "client_id": "c"})
    result = _wait_for_job(client, resp.json()["job_id"])
    assert result["status"] == "done"
    assert result["route"] == "router"
    assert stream_calls[0]["agent_id"] == "router-id"


def test_job_phases_follow_sse_events(tmp_path, monkeypatch):
    """#93: de background-job zet SSE-events om in job["phase"]; /chat/status toont ze.
    Eén gedeelde event loop (zoals de trage-call-test): onder TestClient wordt een
    nog-lopende background task bij einde van het request gecanceld."""
    import asyncio as _asyncio
    import time as _time

    import httpx

    import config
    import intake
    import mistral_client
    import phases

    def classify(**kwargs):
        return dict(intake.FALLBACK)

    def stream(**kwargs):
        on_event = kwargs["on_event"]
        for event, data in [
            ("agent.handoff.done", {"next_agent_name": "knwu-agent"}),
            ("tool.execution.started", {"name": "document_library"}),
            ("tool.execution.started", {"name": "web_search"}),
            ("message.output.delta", {"content": "Antwoord"}),
        ]:
            on_event(event, data)
            _time.sleep(0.05)  # poll-interval (10ms) moet de fasen kunnen zien
        return "conv-x", "Antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", classify)
    monkeypatch.setattr(mistral_client, "stream_answer", stream)
    app = create_app(db_path=str(tmp_path / "t.db"))

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"message": "vraag", "client_id": "c"})
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]
            seen: list[str] = []
            for _ in range(500):
                body = (await ac.get(f"/chat/status/{job_id}")).json()
                if body["phase"] not in seen:
                    seen.append(body["phase"])
                if body["status"] in ("done", "error"):
                    return body, seen
                await _asyncio.sleep(0.01)
            raise AssertionError("job werd niet done binnen 5s")

    result, seen = _asyncio.run(run())
    assert result["status"] == "done"
    assert seen == [
        phases.PHASE_LEES,
        phases.PHASE_KNWU,
        phases.PHASE_WEB,
        phases.PHASE_OPSTELLEN,
        phases.PHASE_KLAAR,
    ]
    assert result["route"] == "router"


def test_stream_start_error_falls_back_to_non_streaming(tmp_path, monkeypatch):
    """#93: als de SSE-call niet start, valt de job terug op de non-streaming call."""
    import config
    import intake
    import mistral_client

    fallback_calls: list[dict] = []

    def broken_stream(**kwargs):
        raise mistral_client.StreamStartError("Mistral API niet bereikbaar")

    def answer_question(**kwargs):
        fallback_calls.append(kwargs)
        return "conv-fb", "fallback antwoord"

    monkeypatch.setattr(config, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(config, "MISTRAL_AGENT_ID", "router-id")
    monkeypatch.setattr(intake, "classify_message", lambda **kw: dict(intake.FALLBACK))
    monkeypatch.setattr(mistral_client, "stream_answer", broken_stream)
    monkeypatch.setattr(mistral_client, "answer_question", answer_question)
    client = make_client(tmp_path)
    body = chat(client, "vraag")
    assert body["answer"] == "fallback antwoord"
    assert len(fallback_calls) == 1
    assert fallback_calls[0]["prompt_cache_key"] == config.PROMPT_CACHE_KEY
