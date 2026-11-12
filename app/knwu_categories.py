"""Deterministische lookup van leeftijdscategorie en licentie.

Het model rekent een geboortejaar niet betrouwbaar om naar een categorie
(issue #44). De regels staan in knwu_categories.json met bron en versie,
zodat ze per seizoen bij te werken zijn; tests/test_knwu_categories.py
vergelijkt dat bestand met de tabel in de KNWU-bibliotheek (Titel 20).
Hetzelfde bestand bevat de vertaling van de oude categorie-indeling
(bron: website-tekst KNWU - leeftijdscategorieën, issue #61).
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


def licence(birth_year: int, year: int, rules: dict) -> str | None:
    """Licentie (bv. "KNWU Licentie U13") in een kalenderjaar; None buiten de jeugdlicenties."""
    age = age_in_year(birth_year, year)
    for entry in rules["licenties"]["indeling"]:
        if entry["van"] <= age <= entry["tot_en_met"]:
            return entry["naam"]
    return None


def category_name(under: int, rules: dict) -> str | None:
    """Volledige naam van leeftijdscategorie U<under> (bv. 17 -> "U17 Nieuweling")."""
    for name in rules["leeftijdscategorieen"]["per_leeftijd"].values():
        if name.split()[0] == f"U{under}":
            return name
    return None


def old_category_groups(number: int, rules: dict) -> list[dict] | None:
    """Gecombineerde categorieën van oude categorie <number>; None als die niet bestaat."""
    return rules["oude_categorie_indeling"]["categorieen"].get(str(number))


def combined_notation(boys: int | None, girls: int | None) -> str:
    """Schrijfwijze van een gecombineerde categorie, bv. (11, 12) -> "JO11/MO12"."""
    parts = [f"JO{boys}" if boys else "", f"MO{girls}" if girls else ""]
    return "/".join(part for part in parts if part)


def cyclocross_season(today: date) -> tuple[int, int]:
    """Lopend of eerstvolgend veldritseizoen als (startjaar, eindjaar).

    Januari t/m maart hoort bij het seizoen dat vorig jaar begon; vanaf april
    is het eerstvolgende seizoen dat in september van dit jaar begint.
    """
    if today.month <= 3:
        return today.year - 1, today.year
    return today.year, today.year + 1
