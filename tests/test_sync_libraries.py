import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync_libraries


def make_doc(name: str, size: int | None, doc_id: str = "doc-1") -> SimpleNamespace:
    return SimpleNamespace(id=doc_id, name=name, size=size)


def make_lib(name: str, description: str = "", lib_id: str = "lib-1") -> SimpleNamespace:
    return SimpleNamespace(id=lib_id, name=name, description=description)


def make_local_files(folder: Path, files: dict[str, int]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for name, size in files.items():
        path = folder / name
        path.write_bytes(b"x" * size)
        result[name] = path
    return result


def empty_report() -> sync_libraries.SyncReport:
    return {
        "created_libraries": [],
        "updated_libraries": [],
        "uploads": [],
        "deletes": [],
        "unchanged": 0,
        "errors": [],
    }


class PlanDocumentSyncTests(unittest.TestCase):
    def test_uploads_missing_and_deletes_orphaned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = make_local_files(Path(tmp), {"a.pdf": 100, "b.pdf": 200})
            remote = [make_doc("a.pdf", 100), make_doc("c.pdf", 50, "doc-2")]

            plan = sync_libraries.plan_document_sync(local, remote)

            self.assertEqual([name for name, _ in plan["uploads"]], ["b.pdf"])
            self.assertEqual([d.name for d in plan["deletes"]], ["c.pdf"])
            self.assertEqual(plan["unchanged"], 1)

    def test_replaces_all_remote_duplicates_on_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = make_local_files(Path(tmp), {"a.pdf": 100})
            remote = [make_doc("a.pdf", 999, "doc-1"), make_doc("a.pdf", 999, "doc-2")]

            plan = sync_libraries.plan_document_sync(local, remote)

            self.assertEqual([name for name, _ in plan["uploads"]], ["a.pdf"])
            self.assertEqual([d.id for d in plan["deletes"]], ["doc-1", "doc-2"])
            self.assertEqual(plan["unchanged"], 0)


class SyncLibrariesTests(unittest.TestCase):
    def test_creates_missing_and_updates_changed_description(self) -> None:
        client = MagicMock()
        client.beta.libraries.create.return_value = make_lib("knwu", "KNWU desc", "lib-new")
        existing = [make_lib("regio", "old desc", "lib-regio")]
        configured = [
            {"name": "knwu", "description": "KNWU desc"},
            {"name": "regio", "description": "new desc"},
        ]
        report = empty_report()

        result = sync_libraries.sync_libraries(client, configured, existing, apply=True, report=report)

        client.beta.libraries.create.assert_called_once_with(name="knwu", description="KNWU desc")
        client.beta.libraries.update.assert_called_once_with(library_id="lib-regio", description="new desc")
        self.assertEqual(report["created_libraries"], ["knwu"])
        self.assertEqual(report["updated_libraries"], ["regio"])
        self.assertEqual(result["knwu"].id, "lib-new")
        self.assertEqual(result["regio"].id, "lib-regio")


class RunSyncTests(unittest.TestCase):
    def make_client(self) -> MagicMock:
        client = MagicMock()
        client.beta.libraries.list.return_value = SimpleNamespace(data=[], next_page_token=None)
        client.beta.libraries.create.return_value = make_lib("knwu", "desc", "lib-new")
        client.beta.libraries.documents.list.return_value = SimpleNamespace(
            data=[], pagination=SimpleNamespace(has_more=False)
        )
        return client

    def make_config(self, rag_folder: Path) -> sync_libraries.Config:
        return {
            "rag_folder": str(rag_folder),
            "libraries": [{"name": "knwu", "description": "desc"}],
        }

    def test_dry_run_makes_no_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rag = Path(tmp) / "knowledge-documents"
            (rag / "knwu").mkdir(parents=True)
            make_local_files(rag / "knwu", {"a.pdf": 10})
            client = self.make_client()

            exit_code = sync_libraries.run_sync(client, self.make_config(rag), apply=False)

            self.assertEqual(exit_code, 0)
            client.beta.libraries.create.assert_not_called()
            client.beta.libraries.update.assert_not_called()
            client.beta.libraries.documents.upload.assert_not_called()
            client.beta.libraries.documents.delete.assert_not_called()

    def test_relative_rag_folder_resolves_against_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rag = root / "knowledge-documents"
            (rag / "knwu").mkdir(parents=True)
            make_local_files(rag / "knwu", {"a.pdf": 10})
            config_path = root / "scripts" / "libraries_config.json"
            config_path.parent.mkdir()
            config = {
                "rag_folder": "../knowledge-documents",
                "libraries": [{"name": "knwu", "description": "desc"}],
            }
            client = MagicMock()
            client.beta.libraries.list.return_value = SimpleNamespace(data=[], next_page_token=None)

            exit_code = sync_libraries.run_sync(client, config, apply=False, config_path=config_path)

            self.assertEqual(exit_code, 0)

    def test_apply_creates_library_and_uploads_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rag = Path(tmp) / "knowledge-documents"
            (rag / "knwu").mkdir(parents=True)
            make_local_files(rag / "knwu", {"a.pdf": 10})
            client = self.make_client()

            exit_code = sync_libraries.run_sync(client, self.make_config(rag), apply=True)

            self.assertEqual(exit_code, 0)
            client.beta.libraries.create.assert_called_once_with(name="knwu", description="desc")
            client.beta.libraries.documents.list.assert_called_once_with(
                library_id="lib-new", page=0, page_size=100
            )
            self.assertEqual(client.beta.libraries.documents.upload.call_count, 1)
            upload_kwargs = client.beta.libraries.documents.upload.call_args.kwargs
            self.assertEqual(upload_kwargs["library_id"], "lib-new")
            self.assertEqual(upload_kwargs["file"]["file_name"], "a.pdf")


if __name__ == "__main__":
    unittest.main()
