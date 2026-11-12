"""SQLite-opslag voor feedback.

Privacy-beslissing (map #2): content (vraag/antwoord) wordt ALLEEN opgeslagen
bij een duim-omlaag; bij een duim-omhoog alleen een teller (rating + timestamp).
Bij een duim-omlaag slaan we además de laatste turn (question/answer) ook de
feedbackgeschiedenis op: de `history`-kolom bevat een JSON-array met de
laatste turns (vraag/antwoord), zie ADR-0008.
Bronconflicten (#47): rating "bronconflict" slaat ALLEEN de markerregel op
(rating + timestamp + conversation_id + text) — géén question/answer/history,
zelfde privacy-precedent als out-of-scope-signalering.
Retentie: FEEDBACK_RETENTION_DAYS (30), daarna automatische purge.
Geen IP-adressen — die slaan we überhaupt niet op.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    rating TEXT NOT NULL,
    conversation_id TEXT,
    question TEXT,
    answer TEXT,
    text TEXT,
    history TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Voeg ontbrekende kolommen toe aan een bestaande DB.

    CREATE TABLE IF NOT EXISTS past een bestaand schema niet aan, dus een
    upgrade van een oude DB (bijv. op de NAS) vereist een expliciete ALTER.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(feedback)")}
    if "history" not in columns:
        conn.execute("ALTER TABLE feedback ADD COLUMN history TEXT")


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        migrate(conn)


def save_feedback(
    db_path: str,
    *,
    rating: str,
    conversation_id: str = "",
    question: str = "",
    answer: str = "",
    text: str = "",
    history: list[dict] | None = None,
) -> None:
    """Sla feedback op. `history` is een lijst turns ({question, answer}), oudste
    eerst; wordt als JSON in de history-kolom bewaard (alleen bij negative).

    rating "bronconflict" (#47): alleen de markerregel in `text`, plus
    conversation_id — géén question/answer/history (privacy)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        if rating == "negative":
            history_json = json.dumps(history, ensure_ascii=False) if history else None
            conn.execute(
                "INSERT INTO feedback (timestamp, rating, conversation_id, question, answer, text, history)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, rating, conversation_id, question, answer, text, history_json),
            )
        elif rating == "bronconflict":
            # bronconflict: alleen de markerregel, zónder vraagtekst (#47)
            conn.execute(
                "INSERT INTO feedback (timestamp, rating, conversation_id, text) VALUES (?, ?, ?, ?)",
                (timestamp, rating, conversation_id, text),
            )
        else:
            # duim-omhoog: kale teller, géén content
            conn.execute(
                "INSERT INTO feedback (timestamp, rating) VALUES (?, ?)",
                (timestamp, rating),
            )


def purge_old(db_path: str, retention_days: int) -> int:
    """Verwijder feedback ouder dan retentie; geef aantal verwijderde regels."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM feedback WHERE timestamp < ?", (cutoff,))
        return cur.rowcount


def all_feedback(db_path: str) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
    return [dict(row) for row in rows]
