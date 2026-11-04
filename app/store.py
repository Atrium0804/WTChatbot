"""SQLite-opslag voor feedback.

Privacy-beslissing (map #2): content (vraag/antwoord) wordt ALLEEN opgeslagen
bij een duim-omlaag; bij een duim-omhoog alleen een teller (rating + timestamp).
Retentie: FEEDBACK_RETENTION_DAYS (30), daarna automatische purge.
Geen IP-adressen — die slaan we überhaupt niet op.
"""

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
    text TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_feedback(
    db_path: str,
    *,
    rating: str,
    conversation_id: str = "",
    question: str = "",
    answer: str = "",
    text: str = "",
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        if rating == "negative":
            conn.execute(
                "INSERT INTO feedback (timestamp, rating, conversation_id, question, answer, text)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, rating, conversation_id, question, answer, text),
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
