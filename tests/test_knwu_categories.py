"""Drift-check: app/knwu_categories.json moet overeenkomen met Titel 20 in de
KNWU-bibliotheek (knowledge-documents/knwu/). Faalt deze test na een
library-update, werk dan het JSON-bestand bij (bron, versie, indeling).
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "app" / "knwu_categories.json"
KNWU_DIR = ROOT / "knowledge-documents" / "knwu"


def strip_markers(text: str) -> str:
    return text.replace("[GEWIJZIGD]", "").replace("[/GEWIJZIGD]", "")


def parse_age_categories(document: str) -> dict[str, str]:
    """{"5": "U6", ...} uit de tabel van art. 20.0.004 ("Het jaar waarin je N wordt")."""
    per_age: dict[str, str] = {}
    pattern = r"^\|\s*(U\d+[^|]*?)\s*\|\s*Het jaar waarin je (\d+)(?: of (\d+))? wordt\s*\|"
    for name, age, second_age in re.findall(pattern, document, flags=re.MULTILINE):
        for value in (age, second_age):
            if value:
                per_age[value] = name.strip()
    return per_age


def parse_licence_categories(document: str) -> list[dict]:
    """[{"naam": "KNWU Licentie U13", "van": 5, "tot_en_met": 12}, ...] uit art. 20.0.002."""
    pattern = r"^\|\s*(KNWU Licentie U\d+)\s*\|\s*(\d+) t/m (\d+) jaar"
    return [
        {"naam": name, "van": int(start), "tot_en_met": int(end)}
        for name, start, end in re.findall(pattern, document, flags=re.MULTILINE)
    ]


class TestKnwuCategoriesMatchTitel20(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        documents = sorted(KNWU_DIR.glob("TITEL_20*.md"))
        self.assertEqual(len(documents), 1, f"verwacht precies één Titel 20 in {KNWU_DIR}")
        self.document_path = documents[0]
        self.document = strip_markers(self.document_path.read_text(encoding="utf-8"))

    def test_source_is_current_library_version(self):
        self.assertEqual(Path(self.rules["bron"]).stem, self.document_path.stem)

    def test_age_categories_match(self):
        self.assertEqual(
            self.rules["leeftijdscategorieen"]["per_leeftijd"], parse_age_categories(self.document)
        )

    def test_licence_categories_match(self):
        self.assertEqual(
            self.rules["licentiecategorieen"]["indeling"], parse_licence_categories(self.document)
        )

    def test_parser_reads_age_table_row(self):
        row = "| U17 Nieuweling | Het jaar waarin je 15 of 16 wordt |"
        self.assertEqual(parse_age_categories(row), {"15": "U17 Nieuweling", "16": "U17 Nieuweling"})


if __name__ == "__main__":
    unittest.main()
