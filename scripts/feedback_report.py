"""Feedback-rapport voor triage — print feedback uit de SQLite-DB op scherm.

Haalt optioneel een snapshot van de NAS op (via ssh + sqlite3 .backup, want
scp/sftp ziet /volume1 op de Synology niet), checkt de integriteit
(PRAGMA quick_check), print counters + triage-lijst en ruimt het temp-bestand
weer op. Er wordt niets in de repo opgeslagen.

Usage:
    python scripts/feedback_report.py                          # lokale dev-DB (app/data/wtchat.db)
    python scripts/feedback_report.py --db pad/naar/wtchat.db  # expliciete lokale DB
    python scripts/feedback_report.py --fetch --nas-host <ssh-target> \
        [--nas-path /volume1/docker/wtchatbot/data/wtchat.db] [--nas-port 22]

Output: eerst counters (per rating, plus per week), daarna de negatieve
feedback (feedbackgeschiedenis met turns, laatste vraag/antwoord, toelichting),
oudste eerst.

Privacy: ruwe feedback nooit in git of in tickets (deze repo is publiek);
permanente vastlegging alleen geanonimiseerd in LEARNINGS.md.
Zie docs/how-to/raadpleeg-feedback-voor-triage.md.
"""

import argparse
import contextlib
import json
import os
import posixpath
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

import store  # noqa: E402  (app-module, pas na sys.path)

DEFAULT_DB = APP_DIR / "data" / "wtchat.db"
NAS_DEFAULT_PATH = "/volume1/docker/wtchatbot/data/wtchat.db"


def week_key(timestamp: str) -> str:
    """ISO-weekbucket (bijv. '2026-W47') uit een ISO-timestamp; 'onbekend' bij parse-fout."""
    try:
        iso = datetime.fromisoformat(timestamp)
    except ValueError:
        return "onbekend"
    cal = iso.isocalendar()
    return f"{cal[0]}-W{cal[1]:02d}"


def summarize(rows: list[dict]) -> tuple[Counter, Counter]:
    """Geef (totaal per rating, per week per rating) terug."""
    per_rating: Counter = Counter(r["rating"] for r in rows)
    per_week: Counter = Counter(
        f"{week_key(r['timestamp'])}|{r['rating']}" for r in rows
    )
    return per_rating, per_week


def negative_rows(rows: list[dict]) -> list[dict]:
    """Negatieve rows, oudste eerst (triage-volgorde volgens het leerplan)."""
    return sorted(
        (r for r in rows if r["rating"] == "negative"),
        key=lambda r: r["timestamp"] or "",
    )


def bronconflict_rows(rows: list[dict]) -> list[dict]:
    """Bronconflict-rows (#47): rating 'bronconflict' — géén negatieve feedback."""
    return [r for r in rows if r["rating"] == "bronconflict"]


def summarize_bronconflicten(rows: list[dict]) -> list[dict]:
    """Groepeer identieke bronconflicten (op marker-text): aantal + laatste melding.

    Sorteer: meeste meldingen eerst, daarna nieuwste melding eerst.
    """
    groups: dict[str, dict] = {}
    for r in bronconflict_rows(rows):
        text = (r.get("text") or "").strip()
        if not text:
            continue
        ts = r.get("timestamp") or ""
        g = groups.setdefault(text, {"text": text, "aantal": 0, "laatste": ""})
        g["aantal"] += 1
        if ts > g["laatste"]:
            g["laatste"] = ts
    return sorted(groups.values(), key=lambda g: (g["aantal"], g["laatste"]), reverse=True)


def parse_history(row: dict) -> list[dict]:
    """Parse de history-JSON-kolom (lijst turns {question, answer}, oudste eerst).

    Lege lijst bij NULL, een oude DB zonder history-kolom, of ongeldige JSON —
    het rapport moet ook oude snapshots (vóór ADR-0008) kunnen tonen.
    """
    raw = row.get("history")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict)]


def render_report(rows: list[dict], source: str, generated_at: str) -> str:
    per_rating, per_week = summarize(rows)
    lines = [
        "# Feedback-rapport",
        "",
        f"Gegenereerd: {generated_at} — bron: {source}",
        "",
        "## Counters",
        "",
        "| rating | aantal |",
        "| --- | ---: |",
    ]
    total = 0
    for rating in sorted(per_rating):
        lines.append(f"| {rating} | {per_rating[rating]} |")
        total += per_rating[rating]
    lines.append(f"| **totaal** | **{total}** |")

    weeks = sorted({key.split("|")[0] for key in per_week})
    if weeks:
        lines += ["", "Per week (UTC):", "", "| week | positive | negative |", "| --- | ---: | ---: |"]
        for week in weeks:
            lines.append(
                f"| {week} | {per_week.get(week + '|positive', 0)} | {per_week.get(week + '|negative', 0)} |"
            )

    negatives = negative_rows(rows)
    lines += ["", "## Triage — negatieve feedback (oudste eerst)", ""]
    if not negatives:
        lines.append("Geen negatieve feedback binnen de retentieperiode (30 dagen).")
    for i, row in enumerate(negatives, start=1):
        lines += [
            f"### {i} — {row['timestamp']}",
            f"- Conversation: `{row['conversation_id'] or '-'}`"
            + (
                f" (agent-trace: `python scripts/trace_conversation.py {row['conversation_id']}`)"
                if row["conversation_id"]
                else ""
            ),
        ]
        history = parse_history(row)
        
        # Toon de complete conversatiegeschiedenis als die beschikbaar is
        if history:
            lines.append("")
            lines.append("  **Complete conversatie (oudste turn eerst):**")
            for j, turn in enumerate(history, start=1):
                marker = " *(laatste)*" if j == len(history) else ""
                question = turn.get('question') or '-' 
                answer = turn.get('answer') or '-' 
                lines.append("")
                lines.append(f"  ---")
                lines.append(f"  **Turn {j}{marker}**")
                lines.append(f"  **Vraag:** {question}")
                lines.append("")
                # Use code fence for bot answer
                lines.append(f"```")
                for answer_line in answer.split('\n'):
                    lines.append(f"{answer_line}")
                lines.append(f"```")
        else:
            # Oude feedback zonder history - toon wat we hebben
            lines.append("")
            lines.append(f"  ⚠️  *Onvolledige conversatie: history ontbreekt (oude feedback)*")
            lines.append(f"  Gebruik `python scripts/trace_conversation.py {row['conversation_id']}` voor de complete conversatie.")
            lines.append("")
            lines.append("  **Laatste bekende turn:**")
            lines.append(f"  **Vraag:** {row['question'] or '-'}")
            lines.append("")
            # Use code fence for bot answer
            lines.append(f"```")
            for answer_line in (row['answer'] or '-').split('\n'):
                lines.append(f"{answer_line}")
            lines.append(f"```")
        
        lines.append("")
        if row['text'] and row['text'].strip():
            lines.append(f">[!note]")
            for toelichting_line in row['text'].split('\n'):
                lines.append(f"> {toelichting_line}")
        lines.append("")

    # sectie bronconflicten (#47): gegroepeerd, tellers los van negatieve feedback
    conflicten = summarize_bronconflicten(rows)
    lines += ["", "## Bronconflicten", ""]
    if not conflicten:
        lines.append("Geen bronconflicten gemeld binnen de retentieperiode (30 dagen).")
    else:
        lines += [
            "Identieke conflicten gegroepeerd (marker zonder vraagtekst, zie #47).",
            "",
            "| bronconflict | aantal | laatste melding |",
            "| --- | ---: | --- |",
        ]
        for g in conflicten:
            # de marker bevat zelf '|' — escape in de tabelcel
            escaped = g["text"].replace("|", "\\|")
            lines.append(f"| {escaped} | {g['aantal']} | {g['laatste']} |")

    lines.append(
        "_Retentie: rows ouder dan 30 dagen zijn automatisch gepurge'd uit de DB. "
        "Ruwe feedback niet kopiëren naar git/tickets — alleen geanonimiseerd vastleggen in LEARNINGS.md._"
    )
    return "\n".join(lines) + "\n"


def check_integrity(db_path: str | Path) -> None:
    """Stop bij een corrupte kopie (PRAGMA quick_check moet 'ok' geven)."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"snapshot is geen geldige SQLite-DB ({exc})") from exc
    finally:
        conn.close()
    if result != "ok":
        raise ValueError(f"snapshot is niet integer ({result})")


def load_rows(db_path: str | Path) -> list[dict]:
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"error: DB niet gevonden: {path}")
    conn = store.connect(str(path))
    try:
        rows = conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@contextlib.contextmanager
def fetch_snapshot(nas_host: str, nas_path: str, nas_port: int = 22) -> Iterator[Path]:
    """Haal een consistente snapshot van de NAS-DB op via ssh; check integriteit; ruim op.

    Via het shell-kanaal (scp/sftp ziet /volume1 op de Synology niet): de NAS
    maakt met sqlite3 een .backup-snapshot naast de DB, we cat-en die in dezelfde
    ssh-call en verwijderen de remote snapshot direct weer. Lokaal staat de kopie
    in een tempfile dat na gebruik wordt opgeruimd. Vereist: sqlite3 op de NAS. De poort gaat mee als ssh -p (standaard 22).
    """
    fd, tmp = tempfile.mkstemp(prefix="wtchat-snapshot-", suffix=".db")
    os.close(fd)
    tmp_path = Path(tmp)
    snap_remote = f"{posixpath.dirname(nas_path)}/.feedback-snapshot.db"
    remote_cmd = (
        f'sqlite3 {nas_path} ".backup {snap_remote}" && cat {snap_remote}; '
        f"rc=$?; rm -f {snap_remote}; exit $rc"
    )
    try:
        with open(tmp_path, "wb") as out:
            proc = subprocess.run(
                ["ssh", "-p", str(nas_port), nas_host, remote_cmd],
                stdout=out,
                stderr=subprocess.PIPE,
            )
        if proc.returncode != 0:
            raise SystemExit(
                f"error: ophalen van {nas_host}:{nas_port}:{nas_path} mislukt: "
                f"{proc.stderr.decode(errors='replace').strip()}"
            )
        check_integrity(tmp_path)
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print een feedback-rapport (counters + triage) uit de WTChatbot-SQLite-DB."
    )
    parser.add_argument("--db", help="pad naar een lokale wtchat.db (default: app/data/wtchat.db)")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="haal eerst een snapshot van de NAS op via scp (tempfile, wordt opgeruimd)",
    )
    parser.add_argument("--nas-host", help="ssh-target van de NAS (bij --fetch verplicht)")
    parser.add_argument("--nas-path", default=NAS_DEFAULT_PATH, help="DB-pad op de NAS")
    parser.add_argument("--nas-port", type=int, default=22, help="ssh-poort van de NAS (default: 22)")
    args = parser.parse_args(argv)

    # Windows-console (cp1252) kan niet alle tekens uit feedback tonen — niet crashen
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    generated_at = datetime.now(timezone.utc).isoformat()
    if args.fetch:
        if not args.nas_host:
            parser.error("--fetch vereist --nas-host")
        with fetch_snapshot(args.nas_host, args.nas_path, args.nas_port) as snap:
            rows = load_rows(snap)
            print(render_report(rows, f"{args.nas_host}:{args.nas_port}:{args.nas_path} (snapshot)", generated_at))
    else:
        db = args.db or str(DEFAULT_DB)
        rows = load_rows(db)
        print(render_report(rows, db, generated_at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
