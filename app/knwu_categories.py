"""Deterministische lookup van leeftijdscategorie en licentie.

Het model rekent een geboortejaar niet betrouwbaar om naar een categorie
(issue #44). De regels staan in knwu_categories.json met bron en versie,
zodat ze per seizoen bij te werken zijn; tests/test_knwu_categories.py
vergelijkt dat bestand met de tabel in de KNWU-bibliotheek (Titel 20).
Hetzelfde bestand bevat de vertaling van de oude categorie-indeling
(bron: website-tekst KNWU - leeftijdscategorieën, issue #61).
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

RULES_PATH = Path(__file__).parent / "knwu_categories.json"

Gender = Literal["jongens", "meisjes"]
Discipline = Literal["weg", "baan", "veld"]


@dataclass(frozen=True)
class SourceFact:
    name: str
    version: str | None
    article: str | None


@dataclass(frozen=True)
class RuleSources:
    age_categories: SourceFact
    gearing: SourceFact
    licences: SourceFact
    old_categories: SourceFact


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


def max_gear(
    category: str, discipline: Discipline, gender: Gender, rules: dict
) -> float | str | None:
    """Maximaal toegestaan verzet (art. 20.1.007) voor geslacht en leeftijdscategorie.

    `category` is bv. "U13" of "U17 Nieuweling" (uit age_category); `discipline`
    is "weg", "baan" of "veld". Geeft meters (float), "vrij" of None (NVT) terug.
    Raises ValueError for unsupported input; None means a validated NVT source value.
    """
    if gender not in ("jongens", "meisjes"):
        raise ValueError(f"Onbekend geslacht: {gender}; geef 'jongens' of 'meisjes' mee")
    if discipline not in ("weg", "baan", "veld"):
        raise ValueError(f"Onbekende discipline: {discipline}; geef 'weg', 'baan' of 'veld' mee")

    per_category = rules["verzetten"]["per_geslacht"].get(gender)
    if per_category is None:
        raise ValueError(
            f"Geen verzetdata voor geslacht: {gender}; vul verzetten.per_geslacht.{gender} "
            "aan in knwu_categories.json"
        )
    if category not in per_category:
        token = category.split()[0]
        matches = [name for name in per_category if name.split()[0] == token]
        if len(matches) != 1:
            raise ValueError(
                f"Onbekende leeftijdscategorie voor {gender}: {category}; "
                f"kies een van {', '.join(per_category)}"
            )
        category = matches[0]
    entry = per_category[category]
    if discipline not in entry:
        raise ValueError(
            f"Geen verzetdata voor {category}, {gender}, {discipline}; "
            "vul de waarde aan in knwu_categories.json (null voor NVT)"
        )
    return entry[discipline]


def old_category_groups(number: int, rules: dict) -> list[dict] | None:
    """Gecombineerde categorieën van oude categorie <number>; None als die niet bestaat."""
    return rules["oude_categorie_indeling"]["categorieen"].get(str(number))


def category_under(category: str) -> int:
    """Het U-nummer van een categorie, ook als de naam een nadere aanduiding bevat."""
    return int(category.split()[0][1:])


def old_category_number(gender: Gender, category: str, rules: dict) -> int | None:
    """Oud categorienummer voor een geslacht en nieuwe categorie, indien van toepassing."""
    under = category_under(category)
    for number_text, groups in rules["oude_categorie_indeling"]["categorieen"].items():
        if any(group.get(gender) == under for group in groups):
            return int(number_text)
    return None


def ages_for_category(category: str, rules: dict) -> tuple[int, ...]:
    """Leeftijden die in de regels naar deze categorie verwijzen."""
    return tuple(
        int(age)
        for age, name in rules["leeftijdscategorieen"]["per_leeftijd"].items()
        if name == category
    )


def sources(rules: dict) -> RuleSources:
    """Bronverwijzingen voor alle lookup-feiten."""
    return RuleSources(
        age_categories=SourceFact(
            rules["bron"], rules["versie"], rules["leeftijdscategorieen"]["artikel"]
        ),
        gearing=SourceFact(
            rules["verzetten"]["bron"],
            rules["verzetten"]["versie"],
            rules["verzetten"]["artikel"],
        ),
        licences=SourceFact(rules["bron"], rules["versie"], rules["licenties"]["artikel"]),
        old_categories=SourceFact(rules["oude_categorie_indeling"]["bron"], None, None),
    )


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
