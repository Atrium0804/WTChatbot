"""Contextregels die de proxy aan een gebruikersbericht toevoegt.

De agents kennen de datum van vandaag niet en rekenen een geboortejaar niet
betrouwbaar om naar een categorie (issue #44). De proxy voegt daarom
deterministische contextregels toe onder het bericht van de gebruiker:
- bij elk bericht: het taalniveau van de gebruiker (B1 standaard, B2 als de
  app "Uitgebreid" meestuurt; issue #52);
- bij een nieuwe conversatie: de datum van vandaag;
- bij elk bericht met een geboortejaar uit de jeugdindeling: de
  leeftijdscategorie (weg en veld) en de licentie.
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
    return lines


def add_context(message: str, lines: list[str]) -> str:
    """Zet de contextregels onder het bericht, zodat de router eerst de vraag leest."""
    if not lines:
        return message
    bullets = "\n".join(f"- {line}" for line in lines)
    return f"{message}\n\n{CONTEXT_HEADER}\n{bullets}"
