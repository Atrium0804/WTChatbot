"""Contextregels die de proxy aan een gebruikersbericht toevoegt.

De agents kennen de datum van vandaag niet en rekenen een geboortejaar niet
betrouwbaar om naar een categorie (issue #44). De proxy voegt daarom
deterministische contextregels toe onder het bericht van de gebruiker:
- bij elk bericht: het taalniveau van de gebruiker (B1 standaard, B2 als de
  app "Uitgebreid" meestuurt; issue #52);
- bij een nieuwe conversatie: de datum van vandaag;
- bij elk bericht met een geboortejaar uit de jeugdindeling: de
  leeftijdscategorie (weg en veld) en de licentie;
- bij elk bericht met een oude aanduiding ("categorie 3", "cat. 3",
  "nieuwelingen") of een aanduiding uit de KNWU-wedstrijdkalender
  ("MU12, VU13"): de nieuwe leeftijdscategorie (issue #61).
Eval-runner (eval/run_eval.py) gebruikt dezelfde functies, zodat de eval
de productie-input spiegelt.
"""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import knwu_categories

TIMEZONE = ZoneInfo("Europe/Amsterdam")
CONTEXT_HEADER = "Contextregels van de app (geen tekst van de gebruiker):"
MAX_BIRTH_YEARS = 3
BIRTH_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MONTHS = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def today_in_netherlands() -> date:
    return datetime.now(TIMEZONE).date()


def format_dutch_date(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}"


def date_line(today: date) -> str:
    return (
        f"Vandaag is het {format_dutch_date(today)}. Data vóór vandaag liggen in "
        "het verleden: noem bij een vraag naar de volgende of komende wedstrijd "
        "alleen data vanaf vandaag."
    )


def find_birth_years(message: str, today: date, rules: dict) -> list[int]:
    """Jaartallen in het bericht die een geboortejaar in de jeugdindeling zijn.

    Een jaartal telt mee als het dit kalenderjaar of in het veldritseizoen
    een leeftijdscategorie oplevert; zo triggert "NK 2026" niets.
    """
    _, season_end = knwu_categories.cyclocross_season(today)
    birth_years: list[int] = []
    for match in BIRTH_YEAR_PATTERN.findall(message):
        year = int(match)
        in_youth = knwu_categories.age_category(year, today.year, rules) or (
            knwu_categories.age_category(year, season_end, rules)
        )
        if in_youth and year not in birth_years:
            birth_years.append(year)
    return birth_years[:MAX_BIRTH_YEARS]


def category_line(birth_year: int, today: date, rules: dict) -> str:
    outside = "valt buiten de jeugdindeling"
    season_start, season_end = knwu_categories.cyclocross_season(today)
    road = knwu_categories.age_category(birth_year, today.year, rules) or outside
    cross = knwu_categories.age_category(birth_year, season_end, rules) or outside
    licence = knwu_categories.licence(birth_year, today.year, rules) or "geen jeugdlicentie"
    age_article = rules["leeftijdscategorieen"]["artikel"]
    licence_article = rules["licenties"]["artikel"]
    return (
        f"Geboortejaar {birth_year}, berekend door de app uit {rules['bron']} "
        f"(versie {rules['versie']}): leeftijdscategorie wegwielrennen {today.year}: {road}; "
        f"leeftijdscategorie veldrijden seizoen {season_start}-{season_end}: {cross} "
        f"(de categorie per 1 januari {season_end}) (artikel {age_article}); "
        f"licentie {today.year}: {licence} (artikel {licence_article}). "
        "Gebruik deze waarden en reken de categorie niet zelf uit."
    )


# "categorie 3", "cat. 3", "categorieën 3 en 4", "cat 1 t/m 3"; Romeinse cijfers
# ("Cat. II nationale wedstrijd") zijn een wedstrijdcategorie en vallen erbuiten.
OLD_CATEGORY_PATTERN = re.compile(
    r"\b(?:categorie(?:ën|en)?|cat\.?)\s*(\d+(?:\s*(?:,|/|&|-|\ben\b|t/m)\s*\d+)*)\b",
    re.IGNORECASE,
)
MAX_RANGE = 10
# "U17 Nieuweling" is al de nieuwe naam.
NIEUWELING_PATTERN = re.compile(r"(?<!u17[\s-])\bnieuweling", re.IGNORECASE)
# Schrijfwijze van de KNWU-wedstrijdkalender: "MU12, VU13" = JO12/MO13.
CALENDAR_PATTERN = re.compile(
    r"\bMU(\d{1,2})\s*(?:[,/&]|\ben\b)?\s*VU(\d{1,2})\b|\b([MV])U(\d{1,2})\b",
    re.IGNORECASE,
)


def old_category_numbers(message: str) -> list[int]:
    """Nummers achter "categorie"/"cat." in volgorde; "1 t/m 3" en "1-3" worden 1, 2, 3."""
    numbers: list[int] = []
    for group in OLD_CATEGORY_PATTERN.findall(message):
        tokens = re.findall(r"\d+|t/m|-", group)
        for index, token in enumerate(tokens):
            if not token.isdigit():
                continue
            is_range_end = index >= 2 and tokens[index - 1] in ("t/m", "-")
            start = int(tokens[index - 2]) + 1 if is_range_end else int(token)
            if int(token) - start > MAX_RANGE:
                start = int(token)
            for number in range(start, int(token) + 1):
                if number not in numbers:
                    numbers.append(number)
    return numbers


def old_category_line(number: int, rules: dict) -> str | None:
    if number == 0:
        first = knwu_categories.old_category_groups(1, rules)
        notation = " en ".join(
            knwu_categories.combined_notation(g.get("jongens"), g.get("meisjes")) for g in first
        )
        return (
            'Oude aanduiding "categorie 0" bestaat niet; de oude indeling begint bij '
            f"categorie 1 ({notation})."
        )
    groups = knwu_categories.old_category_groups(number, rules)
    if not groups:
        return None
    notation = " en ".join(
        knwu_categories.combined_notation(g.get("jongens"), g.get("meisjes")) for g in groups
    )
    return (
        f'Oude aanduiding "categorie {number}" = categorie {number} ({notation}): '
        f"{_boys_and_girls(groups, rules)}."
    )


def _boys_and_girls(groups: list[dict], rules: dict) -> str:
    """Bijvoorbeeld "jongens U8 en U9, meisjes U9 en U10"."""
    parts = []
    for sex in ("jongens", "meisjes"):
        names = [knwu_categories.category_name(g[sex], rules) for g in groups if g.get(sex)]
        if names:
            parts.append(f"{sex} {' en '.join(names)}")
    return ", ".join(parts)


def calendar_line(boys: int | None, girls: int | None, rules: dict) -> str | None:
    """"MU12, VU13" -> JO12/MO13; None als een aanduiding buiten de jeugdindeling valt."""
    group = {"jongens": boys, "meisjes": girls}
    if any(age and not knwu_categories.category_name(age, rules) for age in group.values()):
        return None
    label = ", ".join(
        part for part in (f"MU{boys}" if boys else "", f"VU{girls}" if girls else "") if part
    )
    return (
        f'Kalenderaanduiding "{label}" = {knwu_categories.combined_notation(boys, girls)}: '
        f"{_boys_and_girls([group], rules)}."
    )


def old_designation_lines(message: str, rules: dict) -> list[str]:
    """Contextregels voor oude en kalender-aanduidingen; leeg als er geen in staat."""
    lines = [old_category_line(number, rules) for number in old_category_numbers(message)]
    if NIEUWELING_PATTERN.search(message):
        name = rules["oude_categorie_indeling"]["nieuwelingen"]
        lines.append(f'Oude aanduiding "nieuwelingen" = {name}.')
    for boys, girls, sex, age in CALENDAR_PATTERN.findall(message):
        if sex:
            boys, girls = (age, "") if sex.upper() == "M" else ("", age)
        lines.append(calendar_line(int(boys) if boys else None, int(girls) if girls else None, rules))
    unique: list[str] = []
    for line in lines:
        if line and line not in unique:
            unique.append(line)
    return unique


LANGUAGE_LEVELS = ("B1", "B2")


def normalize_language_level(level: str) -> str:
    """Alleen B1/B2 gaan door; alles anders (incl. leeg) is de standaard B1."""
    return level if level in LANGUAGE_LEVELS else "B1"


def language_line(level: str) -> str:
    return f"Voor deze gebruiker is vastgesteld taalniveau: {normalize_language_level(level)}"


def build_context_lines(
    message: str,
    today: date,
    rules: dict,
    new_conversation: bool,
    language_level: str = "B1",
) -> list[str]:
    lines = [language_line(language_level)]
    if new_conversation:
        lines.append(date_line(today))
    for birth_year in find_birth_years(message, today, rules):
        lines.append(category_line(birth_year, today, rules))
    lines.extend(old_designation_lines(message, rules))
    return lines


def add_context(message: str, lines: list[str]) -> str:
    """Zet de contextregels onder het bericht, zodat de router eerst de vraag leest."""
    if not lines:
        return message
    bullets = "\n".join(f"- {line}" for line in lines)
    return f"{message}\n\n{CONTEXT_HEADER}\n{bullets}"
