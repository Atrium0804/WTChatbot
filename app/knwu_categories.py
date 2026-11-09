"""Deterministische lookup van leeftijdscategorie en licentiecategorie.

Het model rekent een geboortejaar niet betrouwbaar om naar een categorie
(issue #44). De regels staan in knwu_categories.json met bron en versie,
zodat ze per seizoen bij te werken zijn; tests/test_knwu_categories.py
vergelijkt dat bestand met de tabel in de KNWU-bibliotheek (Titel 20).
"""

import json
from datetime import date
from pathlib import Path

RULES_PATH = Path(__file__).parent / "knwu_categories.json"


def load_rules(path: Path = RULES_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def age_in_year(birth_year: int, year: int) -> int:
    """Titel 20 art. 20.0.004 telt de leeftijd die je in dat jaar wórdt."""
    return year - birth_year


def age_category(birth_year: int, year: int, rules: dict) -> str | None:
    """Leeftijdscategorie in een kalenderjaar; None buiten de jeugdindeling."""
    per_age = rules["leeftijdscategorieen"]["per_leeftijd"]
    return per_age.get(str(age_in_year(birth_year, year)))


def licence_category(birth_year: int, year: int, rules: dict) -> str | None:
    """Licentiecategorie (bv. "KNWU Licentie U13") in een kalenderjaar."""
    age = age_in_year(birth_year, year)
    for licence in rules["licentiecategorieen"]["indeling"]:
        if licence["van"] <= age <= licence["tot_en_met"]:
            return licence["naam"]
    return None


def cyclocross_season(today: date) -> tuple[int, int]:
    """Lopend of eerstvolgend veldritseizoen als (startjaar, eindjaar).

    Januari t/m maart hoort bij het seizoen dat vorig jaar begon; vanaf april
    is het eerstvolgende seizoen dat in september van dit jaar begint.
    """
    if today.month <= 3:
        return today.year - 1, today.year
    return today.year, today.year + 1


def youth_age_range(rules: dict) -> tuple[int, int]:
    ages = [int(age) for age in rules["leeftijdscategorieen"]["per_leeftijd"]]
    return min(ages), max(ages)
