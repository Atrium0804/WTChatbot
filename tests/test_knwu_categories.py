"""Drift-check: app/knwu_categories.json moet overeenkomen met Titel 20 in de
KNWU-bibliotheek (knowledge-documents/knwu/). Faalt deze test na een
library-update, werk dan het JSON-bestand bij (bron, versie, indeling).
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "app" / "knwu_categories.json"
KNWU_DIR = ROOT / "knowledge-documents" / "knwu"
sys.path.insert(0, str(ROOT / "app"))

import knwu_categories  # noqa: E402


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


def parse_licences(document: str) -> list[dict]:
    """[{"naam": "KNWU Licentie U13", "van": 5, "tot_en_met": 12}, ...] uit art. 20.0.002."""
    pattern = r"^\|\s*(KNWU Licentie U\d+)\s*\|\s*(\d+) t/m (\d+) jaar"
    return [
        {"naam": name, "van": int(start), "tot_en_met": int(end)}
        for name, start, end in re.findall(pattern, document, flags=re.MULTILINE)
    ]


def parse_meter(text: str) -> float | None:
    """'5,50 meter' -> 5.5; 'NVT' -> None."""
    match = re.match(r"(\d+),(\d+)\s*meter", text.strip())
    if match:
        return float(f"{match.group(1)}.{match.group(2)}")
    return None


def parse_gear_table(document: str) -> dict[str, dict]:
    """{"U6": {"weg": 5.5, "baan": None, "veld": None}, ...} uit de tabel van art. 20.1.007."""
    section = document.split("20.1.007", 1)[1].split("20.1.008", 1)[0]
    table: dict[str, dict] = {}
    row = r"^\|\s*U(\d+)(?:\s*\(([^)]*)\))?\s*\|[^|]*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    for under, label, weg, baan, veld in re.findall(row, section, flags=re.MULTILINE):
        name = f"U{under}" + (" Nieuweling" if label and "Nieuweling" in label else "")
        veld_value = veld.strip()
        table[name] = {
            "weg": parse_meter(weg),
            "baan": parse_meter(baan),
            "veld": "vrij" if veld_value == "vrij" else None,
        }
    return table


class TestKnwuCategoriesMatchTitel20(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        # Titel 20 staat per hoofdstuk in de bibliotheek; art. 20.0.002 en 20.0.004
        # staan in het hoofdstuk ALGEMENE BEPALINGEN.
        self.document_path = KNWU_DIR / self.rules["bron"]
        self.assertTrue(self.document_path.exists(), f"bron {self.rules['bron']} niet gevonden in {KNWU_DIR}")
        self.document = strip_markers(self.document_path.read_text(encoding="utf-8"))

    def test_source_is_current_library_version(self):
        versies = {p.name.split(" - ")[0] for p in KNWU_DIR.glob("TITEL_20*.md")}
        self.assertEqual(versies, {self.document_path.name.split(" - ")[0]}, f"verwacht één Titel 20-versie in {KNWU_DIR}")

    def test_age_categories_match(self):
        self.assertEqual(
            self.rules["leeftijdscategorieen"]["per_leeftijd"], parse_age_categories(self.document)
        )

    def test_licences_match(self):
        self.assertEqual(
            self.rules["licenties"]["indeling"], parse_licences(self.document)
        )

    def test_parser_reads_age_table_row(self):
        row = "| U17 Nieuweling | Het jaar waarin je 15 of 16 wordt |"
        self.assertEqual(parse_age_categories(row), {"15": "U17 Nieuweling", "16": "U17 Nieuweling"})

    def test_max_gear_matches(self):
        gear_path = KNWU_DIR / self.rules["verzetten"]["bron"]
        self.assertTrue(gear_path.exists(), f"bron {self.rules['verzetten']['bron']} niet gevonden in {KNWU_DIR}")
        gear_document = strip_markers(gear_path.read_text(encoding="utf-8"))
        self.assertEqual(self.rules["verzetten"]["per_categorie"], parse_gear_table(gear_document))


class TestMaxGearLookup(unittest.TestCase):
    def setUp(self):
        self.rules = knwu_categories.load_rules()

    def test_lookup_per_categorie_en_discipline(self):
        self.assertEqual(knwu_categories.max_gear("U13", "weg", self.rules), 6.30)
        self.assertEqual(knwu_categories.max_gear("U9", "baan", self.rules), 5.46)
        self.assertEqual(knwu_categories.max_gear("U9", "veld", self.rules), "vrij")
        self.assertIsNone(knwu_categories.max_gear("U6", "veld", self.rules))

    def test_lookup_accepteert_aliases(self):
        self.assertEqual(knwu_categories.max_gear("U17 Nieuweling", "weg", self.rules), 7.68)
        self.assertEqual(knwu_categories.max_gear("U17", "weg", self.rules), 7.68)

    def test_lookup_onbekende_categorie(self):
        self.assertIsNone(knwu_categories.max_gear("U23", "weg", self.rules))


if __name__ == "__main__":
    unittest.main()
