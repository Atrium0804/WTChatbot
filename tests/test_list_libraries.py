import contextlib
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import list_libraries
import sync_libraries


def make_doc(name: str, size: int | None, created: datetime, status: str = "done", doc_id: str = "d1") -> SimpleNamespace:
    return SimpleNamespace(id=doc_id, name=name, size=size, created_at=created, process_status=status)


def make_config() -> sync_libraries.Config:
    return {
        "rag_folder": "knowledge-documents",
        "libraries": [{"name": "knwu", "description": "KNWU-bibliotheek"}],
    }


class CollectOverviewTests(unittest.TestCase):
    def test_paginates_all_document_pages(self) -> None:
        client = MagicMock()
        client.beta.libraries.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(id="lib-1", name="knwu")], next_page_token=None
        )
        client.beta.libraries.documents.list.side_effect = [
            SimpleNamespace(
                data=[make_doc("a.pdf", 100, datetime(2026, 9, 18, tzinfo=timezone.utc))],
                pagination=SimpleNamespace(has_more=True),
            ),
            SimpleNamespace(
                data=[make_doc("b.pdf", 200, datetime(2026, 9, 19, tzinfo=timezone.utc))],
                pagination=SimpleNamespace(has_more=False),
            ),
        ]

        overview = list_libraries.collect_overview(client, make_config())

        self.assertEqual([d["name"] for d in overview["libraries"][0]["documents"]], ["a.pdf", "b.pdf"])
        self.assertEqual(client.beta.libraries.documents.list.call_count, 2)
        self.assertEqual(overview["unconfigured_remote"], [])

    def test_missing_remote_library_is_reported_without_listing(self) -> None:
        client = MagicMock()
        client.beta.libraries.list.return_value = SimpleNamespace(data=[], next_page_token=None)

        overview = list_libraries.collect_overview(client, make_config())

        self.assertFalse(overview["libraries"][0]["exists"])
        self.assertEqual(overview["libraries"][0]["documents"], [])
        client.beta.libraries.documents.list.assert_not_called()


class OutputTests(unittest.TestCase):
    def make_overview(self) -> list_libraries.Overview:
        client = MagicMock()
        client.beta.libraries.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(id="lib-1", name="knwu", nb_documents=1, total_size=9786169),
                SimpleNamespace(id="lib-9", name="extra-remote", nb_documents=7, total_size=123),
            ],
            next_page_token=None,
        )
        client.beta.libraries.documents.list.return_value = SimpleNamespace(
            data=[
                make_doc(
                    "doc.pdf",
                    9786169,
                    datetime(2026, 10, 29, 14, 25, tzinfo=timezone.utc),
                    status="in_progress",
                )
            ],
            pagination=SimpleNamespace(has_more=False),
        )
        return list_libraries.collect_overview(client, make_config())

    def test_table_output_and_unconfigured_warning(self) -> None:
        overview = self.make_overview()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            list_libraries.print_table(overview)

        text = out.getvalue()
        self.assertIn("knwu", text)
        self.assertIn("doc.pdf", text)
        self.assertIn("9,3 MB", text)
        self.assertIn("2026-10-29T14:25:00+00:00", text)
        self.assertIn("in_progress", text)
        self.assertIn("totaal: 1 documenten (9,3 MB) in 1 van 1 geconfigureerde libraries", text)
        self.assertIn("'extra-remote' (7 documenten)", err.getvalue())

    def test_json_output_keeps_raw_values(self) -> None:
        overview = self.make_overview()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            list_libraries.print_json(overview)

        data = json.loads(out.getvalue())
        doc = data["libraries"][0]["documents"][0]
        self.assertEqual(doc["size"], 9786169)
        self.assertEqual(doc["created_at"], "2026-10-29T14:25:00+00:00")
        self.assertEqual(data["unconfigured_remote"][0]["name"], "extra-remote")
        self.assertEqual(data["unconfigured_remote"][0]["nb_documents"], 7)
        self.assertEqual(
            data["totals"],
            {"documents": 1, "size_bytes": 9786169, "libraries_existing": 1, "libraries_configured": 1},
        )


if __name__ == "__main__":
    unittest.main()
