import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import import_website_texts


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def run(source: Path, dest: Path, apply: bool) -> list[import_website_texts.ImportAction]:
    with redirect_stdout(io.StringIO()):
        return import_website_texts.run_import(source, dest, apply=apply)


class StripPageSuffixTests(unittest.TestCase):
    def test_strips_cms_page_number(self) -> None:
        self.assertEqual(import_website_texts.strip_page_suffix("Trainingen - 1014.md"), "Trainingen.md")

    def test_keeps_inner_dashes(self) -> None:
        self.assertEqual(
            import_website_texts.strip_page_suffix("KNWU - Licenties - 1018.md"), "KNWU - Licenties.md"
        )

    def test_name_without_suffix_is_unchanged(self) -> None:
        self.assertEqual(import_website_texts.strip_page_suffix("Afspraken.md"), "Afspraken.md")


class RunImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.source = root / "website_teksten md"
        self.dest = root / "club"
        write(self.source / "Trainingen - 1014.md", "# Trainingen\n")
        write(self.source / "Lid worden - 1013.md", "# Lid worden\n")
        write(self.source / "notities.txt", "geen markdown")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_dry_run_writes_nothing(self) -> None:
        actions = run(self.source, self.dest, apply=False)

        self.assertEqual([a["status"] for a in actions], ["new", "new"])
        self.assertFalse(self.dest.exists())

    def test_apply_copies_markdown_with_stripped_names(self) -> None:
        run(self.source, self.dest, apply=True)

        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["Lid worden.md", "Trainingen.md"])
        self.assertEqual((self.dest / "Trainingen.md").read_text(encoding="utf-8"), "# Trainingen\n")

    def test_second_run_is_idempotent(self) -> None:
        run(self.source, self.dest, apply=True)
        mtime = (self.dest / "Trainingen.md").stat().st_mtime_ns

        actions = run(self.source, self.dest, apply=True)

        self.assertEqual([a["status"] for a in actions], ["unchanged", "unchanged"])
        self.assertEqual((self.dest / "Trainingen.md").stat().st_mtime_ns, mtime)

    def test_crlf_only_difference_counts_as_unchanged(self) -> None:
        self.dest.mkdir(parents=True)
        (self.dest / "Trainingen.md").write_bytes(b"# Trainingen\r\n")

        actions = run(self.source, self.dest, apply=False)

        statuses = {a["dest"].name: a["status"] for a in actions}
        self.assertEqual(statuses["Trainingen.md"], "unchanged")

    def test_changed_source_overwrites_and_keeps_other_club_documents(self) -> None:
        write(self.dest / "Trainingen.md", "# Oud\n")
        write(self.dest / "ZMC - reglement.md", "# ZMC\n")

        actions = run(self.source, self.dest, apply=True)

        statuses = {a["dest"].name: a["status"] for a in actions}
        self.assertEqual(statuses, {"Lid worden.md": "new", "Trainingen.md": "changed"})
        self.assertEqual((self.dest / "Trainingen.md").read_text(encoding="utf-8"), "# Trainingen\n")
        self.assertTrue((self.dest / "ZMC - reglement.md").exists())

    def test_missing_source_fails_with_hint(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            run(self.source / "bestaat-niet", self.dest, apply=False)

        self.assertIn("--source", str(ctx.exception))

    def test_name_collision_after_stripping_fails(self) -> None:
        write(self.source / "Trainingen - 2000.md", "# Andere trainingen\n")

        with self.assertRaises(SystemExit) as ctx:
            run(self.source, self.dest, apply=True)

        self.assertIn("Trainingen.md", str(ctx.exception))
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
