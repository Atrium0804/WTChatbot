import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import feedback_report
import store


def make_db(tmp_path: Path) -> str:
    db = str(tmp_path / "wtchat.db")
    store.init_db(db)
    return db


def insert_row(db: str, timestamp: str, rating: str, **fields: str) -> None:
    with sqlite3.connect(db) as conn:
        cols = ", ".join(["timestamp", "rating", *fields.keys()])
        placeholders = ", ".join("?" for _ in range(2 + len(fields)))
        conn.execute(
            f"INSERT INTO feedback ({cols}) VALUES ({placeholders})",
            (timestamp, rating, *fields.values()),
        )


class SummarizeTests(unittest.TestCase):
    def test_counts_per_rating(self) -> None:
        rows = [
            {"timestamp": "2026-11-16T10:00:00+00:00", "rating": "positive"},
            {"timestamp": "2026-11-17T10:00:00+00:00", "rating": "negative"},
            {"timestamp": "2026-11-17T11:00:00+00:00", "rating": "positive"},
        ]
        per_rating, _ = feedback_report.summarize(rows)
        self.assertEqual(per_rating["positive"], 2)
        self.assertEqual(per_rating["negative"], 1)

    def test_weekly_buckets(self) -> None:
        rows = [
            {"timestamp": "2026-11-16T10:00:00+00:00", "rating": "positive"},  # 2026-W47
            {"timestamp": "2026-11-23T10:00:00+00:00", "rating": "negative"},  # 2026-W48
        ]
        _, per_week = feedback_report.summarize(rows)
        self.assertEqual(per_week["2026-W47|positive"], 1)
        self.assertEqual(per_week["2026-W48|negative"], 1)

    def test_week_key_invalid_timestamp(self) -> None:
        self.assertEqual(feedback_report.week_key("geen-datum"), "onbekend")


class NegativeRowsTests(unittest.TestCase):
    def test_oldest_first_and_only_negative(self) -> None:
        rows = [
            {"timestamp": "2026-11-20T10:00:00+00:00", "rating": "negative", "text": "later"},
            {"timestamp": "2026-11-10T10:00:00+00:00", "rating": "positive"},
            {"timestamp": "2026-11-15T10:00:00+00:00", "rating": "negative", "text": "eerder"},
        ]
        negatives = feedback_report.negative_rows(rows)
        self.assertEqual([r["text"] for r in negatives], ["eerder", "later"])


class RenderReportTests(unittest.TestCase):
    def test_counters_before_triage(self) -> None:
        rows = [
            {
                "timestamp": "2026-11-15T10:00:00+00:00",
                "rating": "negative",
                "conversation_id": "abc",
                "question": "Wat is het verzet?",
                "answer": "42x16",
                "text": "klopt niet",
            },
            {"timestamp": "2026-11-16T10:00:00+00:00", "rating": "positive"},
        ]
        report = feedback_report.render_report(rows, "test-db", "2026-11-20T12:00:00+00:00")
        self.assertLess(report.index("## Counters"), report.index("## Triage"))
        self.assertIn("| positive | 1 |", report)
        self.assertIn("| negative | 1 |", report)
        self.assertIn("Wat is het verzet?", report)
        self.assertIn("klopt niet", report)

    def test_no_negative_feedback(self) -> None:
        rows = [{"timestamp": "2026-11-16T10:00:00+00:00", "rating": "positive"}]
        report = feedback_report.render_report(rows, "test-db", "2026-11-20T12:00:00+00:00")
        self.assertIn("Geen negatieve feedback", report)


class LoadRowsTests(unittest.TestCase):
    def test_roundtrip_via_store(self) -> None:
        db = make_db(Path(self._tmp()))
        store.save_feedback(db, rating="positive")
        store.save_feedback(
            db,
            rating="negative",
            conversation_id="c1",
            question="vraag",
            answer="antwoord",
            text="toelichting",
        )
        rows = feedback_report.load_rows(db)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["text"], "toelichting")

    def test_missing_db_exits(self) -> None:
        with self.assertRaises(SystemExit):
            feedback_report.load_rows("/pad/bestaat/niet.db")

    def _tmp(self) -> str:
        return tempfile.mkdtemp()


class CheckIntegrityTests(unittest.TestCase):
    def test_ok_db_passes(self) -> None:
        db = make_db(Path(tempfile.mkdtemp()))
        feedback_report.check_integrity(db)  # mag niet raises

    def test_corrupt_db_raises(self) -> None:
        bad = Path(tempfile.mkdtemp()) / "bad.db"
        bad.write_bytes(b"dit is geen sqlite-database" * 100)
        with self.assertRaises(ValueError):
            feedback_report.check_integrity(bad)


class FetchSnapshotTests(unittest.TestCase):
    def test_ssh_backup_cat_temp_removed_after_and_checked(self) -> None:
        source_dir = Path(tempfile.mkdtemp())
        source_db = make_db(source_dir)
        store.save_feedback(source_db, rating="negative", text="x")
        used_cmd: list[str] = []

        def fake_run(cmd: list[str], stdout: object = None, **kwargs: object) -> object:
            used_cmd.extend(cmd)
            stdout.write(Path(source_db).read_bytes())  # type: ignore[attr-defined]
            return type("Proc", (), {"returncode": 0, "stderr": b""})()

        with patch("subprocess.run", side_effect=fake_run):
            with feedback_report.fetch_snapshot("nas.local", "/volume1/docker/wtchatbot/data/wtchat.db") as snap:
                self.assertTrue(snap.exists())
                rows = feedback_report.load_rows(snap)
                self.assertEqual(len(rows), 1)
                inside = snap
            self.assertFalse(inside.exists())
        # geen scp (sftp ziet /volume1 niet), maar ssh met server-side .backup + cat + rm
        self.assertEqual(used_cmd[0], "ssh")
        self.assertIn(".backup", used_cmd[-1])
        self.assertIn("cat", used_cmd[-1])
        self.assertIn("rm -f", used_cmd[-1])
        self.assertIn(".feedback-snapshot.db", used_cmd[-1])

    def test_corrupt_snapshot_raises_and_cleans_up(self) -> None:
        def fake_run(cmd: list[str], stdout: object = None, **kwargs: object) -> object:
            stdout.write(b"rommel" * 500)  # type: ignore[attr-defined]
            return type("Proc", (), {"returncode": 0, "stderr": b""})()

        tmpdir = Path(tempfile.gettempdir())
        before = set(tmpdir.glob("wtchat-snapshot-*"))
        with patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(ValueError):
                with feedback_report.fetch_snapshot("nas.local", "/pad/wtchat.db"):
                    self.fail("corrupte snapshot moet ValueError geven")
        # tempfile is opgeruimd in finally
        self.assertEqual(before, set(tmpdir.glob("wtchat-snapshot-*")))

    def test_ssh_failure_exits(self) -> None:
        def fake_run(cmd: list[str], stdout: object = None, **kwargs: object) -> object:
            return type("Proc", (), {"returncode": 255, "stderr": b"connection refused"})()

        with patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(SystemExit) as ctx:
                with feedback_report.fetch_snapshot("nas.local", "/pad/wtchat.db"):
                    pass
        self.assertIn("connection refused", str(ctx.exception))


class MainTests(unittest.TestCase):
    def test_main_with_db_prints_report(self) -> None:
        db = make_db(Path(tempfile.mkdtemp()))
        insert_row(
            db,
            "2026-11-15T10:00:00+00:00",
            "negative",
            conversation_id="c9",
            question="Hoe laat training?",
            answer="18:00",
            text="verkeerde dag",
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = feedback_report.main(["--db", db])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("# Feedback-rapport", text)
        self.assertIn("| negative | 1 |", text)
        self.assertIn("verkeerde dag", text)

    def test_main_fetch_requires_nas_host(self) -> None:
        with self.assertRaises(SystemExit):
            feedback_report.main(["--fetch"])


if __name__ == "__main__":
    unittest.main()
