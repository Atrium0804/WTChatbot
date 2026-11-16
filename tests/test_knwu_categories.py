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


def parse_gear_table(document: str) -> dict[str, dict[str, list[dict]]]:
    """Behoud alle bronrijen per jongens/meisjes-categorie uit art. 20.1.007."""
    section = document.split("20.1.007", 1)[1].split("20.1.008", 1)[0]
    table: dict[str, dict[str, list[dict]]] = {"jongens": {}, "meisjes": {}}
    row = (
        r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*"
        r"([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    )
    categories = r"U(\d+)(?:\s*\(([^)]*)\))?"
    for boys, girls, weg, baan, veld in re.findall(row, section, flags=re.MULTILINE):
        source_values = {
            "weg": parse_meter(weg),
            "baan": parse_meter(baan),
            "veld": "vrij" if veld.strip() == "vrij" else None,
        }
        for gender, cell in (("jongens", boys), ("meisjes", girls)):
            for under, label in re.findall(categories, cell):
                name = f"U{under}" + (" Nieuweling" if label and "Nieuweling" in label else "")
                table[gender].setdefault(name, []).append(source_values)
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

    def test_parser_reads_both_gear_columns_and_preserves_duplicate_source_row(self):
        gear_path = KNWU_DIR / self.rules["verzetten"]["bron"]
        source = parse_gear_table(strip_markers(gear_path.read_text(encoding="utf-8")))
        self.assertEqual(
            source["jongens"]["U11"],
            [{"weg": 5.9, "baan": 5.78, "veld": "vrij"}],
        )
        self.assertEqual(
            source["meisjes"]["U11"],
            [{"weg": 5.5, "baan": 5.46, "veld": "vrij"}],
        )
        self.assertEqual(
            source["meisjes"]["U9"],
            [
                {"weg": 5.5, "baan": None, "veld": None},
                {"weg": 5.5, "baan": 5.46, "veld": "vrij"},
            ],
        )

    def test_max_gear_matches(self):
        gear_path = KNWU_DIR / self.rules["verzetten"]["bron"]
        self.assertTrue(gear_path.exists(), f"bron {self.rules['verzetten']['bron']} niet gevonden in {KNWU_DIR}")
        gear_document = strip_markers(gear_path.read_text(encoding="utf-8"))
        source = parse_gear_table(gear_document)
        corrections = self.rules["verzetten"]["correcties"]
        self.assertEqual(len(corrections), 1)
        correction = corrections[0]
        self.assertEqual(
            (correction["geslacht"], correction["categorie"], correction["discipline"]),
            ("meisjes", "U9", "veld"),
        )
        self.assertEqual(
            (
                correction["waarde"],
                correction["bronwaarden"],
                correction["brondocument"],
                correction["bronpagina"],
                correction["artikel"],
            ),
            (
                "vrij",
                ["NVT", "vrij"],
                "archive/TITEL_20-Jeugdwielrennen_20260921_2026-09-21.pdf",
                8,
                "20.1.007",
            ),
        )

        duplicate_categories = {
            (gender, category): rows
            for gender, categories in source.items()
            for category, rows in categories.items()
            if len(rows) > 1
        }
        self.assertEqual(set(duplicate_categories), {("meisjes", "U9")})
        self.assertEqual(
            [
                "NVT" if value is None else value
                for value in (row["veld"] for row in duplicate_categories[("meisjes", "U9")])
            ],
            correction["bronwaarden"],
        )

        for gender, source_categories in source.items():
            expected_categories = self.rules["verzetten"]["per_geslacht"][gender]
            self.assertEqual(set(source_categories), set(expected_categories))
            for category, source_rows in source_categories.items():
                actual_values = source_rows[0].copy()
                if (gender, category) == ("meisjes", "U9"):
                    actual_values[correction["discipline"]] = correction["waarde"]
                for discipline, expected_value in expected_categories[category].items():
                    self.assertEqual(actual_values[discipline], expected_value, f"{gender} {category} {discipline}")


class TestMaxGearLookup(unittest.TestCase):
    def setUp(self):
        self.rules = knwu_categories.load_rules()

    def test_lookup_per_geslacht(self):
        self.assertEqual(knwu_categories.max_gear("U11", "weg", "jongens", self.rules), 5.90)
        self.assertEqual(knwu_categories.max_gear("U11", "weg", "meisjes", self.rules), 5.50)
        self.assertEqual(knwu_categories.max_gear("U9", "veld", "meisjes", self.rules), "vrij")

    def test_lookup_per_categorie_en_discipline(self):
        self.assertEqual(knwu_categories.max_gear("U13", "weg", "jongens", self.rules), 6.30)
        self.assertEqual(knwu_categories.max_gear("U9", "baan", "jongens", self.rules), 5.46)
        self.assertEqual(knwu_categories.max_gear("U9", "veld", "jongens", self.rules), "vrij")
        self.assertIsNone(knwu_categories.max_gear("U6", "veld", "jongens", self.rules))

    def test_lookup_accepteert_aliases(self):
        self.assertEqual(knwu_categories.max_gear("U17 Nieuweling", "weg", "jongens", self.rules), 7.68)
        self.assertEqual(knwu_categories.max_gear("U17", "weg", "jongens", self.rules), 7.68)

    def test_lookup_onbekende_categorie(self):
        with self.assertRaises(ValueError):
            knwu_categories.max_gear("U23", "weg", "jongens", self.rules)

    def test_onbekend_geslacht_is_geen_nvt(self):
        with self.assertRaises(ValueError):
            knwu_categories.max_gear("U8", "veld", "anders", self.rules)
        self.assertIsNone(knwu_categories.max_gear("U8", "veld", "meisjes", self.rules))
        with self.assertRaises(ValueError):
            knwu_categories.max_gear("U8", "baanwielrennen", "meisjes", self.rules)


if __name__ == "__main__":
    unittest.main()
