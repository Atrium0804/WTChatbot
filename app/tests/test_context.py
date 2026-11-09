"""Tests voor de contextregels en de categorie-lookup (issue #44) — offline."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context  # noqa: E402
import knwu_categories  # noqa: E402

RULES = knwu_categories.load_rules()
NOVEMBER_2026 = date(2026, 11, 9)
FEBRUARY_2027 = date(2027, 2, 1)


def test_age_category_uses_age_turned_in_year():
    # Titel 20 art. 20.0.004: U12 = het jaar waarin je 11 wordt
    assert knwu_categories.age_category(2015, 2026, RULES) == "U12"
    assert knwu_categories.age_category(2020, 2026, RULES) == "U7"
    assert knwu_categories.age_category(2010, 2026, RULES) == "U17 Nieuweling"


def test_age_category_outside_youth_is_none():
    assert knwu_categories.age_category(2022, 2026, RULES) is None
    assert knwu_categories.age_category(2009, 2026, RULES) is None


def test_licence_category_boundaries():
    assert knwu_categories.licence_category(2014, 2026, RULES) == "KNWU Licentie U13"
    assert knwu_categories.licence_category(2013, 2026, RULES) == "KNWU Licentie U17"
    assert knwu_categories.licence_category(2012, 2026, RULES) == "KNWU Licentie U17"
    assert knwu_categories.licence_category(2009, 2026, RULES) is None


def test_cyclocross_season():
    assert knwu_categories.cyclocross_season(NOVEMBER_2026) == (2026, 2027)
    assert knwu_categories.cyclocross_season(FEBRUARY_2027) == (2026, 2027)
    assert knwu_categories.cyclocross_season(date(2027, 6, 1)) == (2027, 2028)


def test_date_line_in_dutch():
    assert "maandag 9 november 2026" in context.date_line(NOVEMBER_2026)


def test_find_birth_years_only_youth_years():
    assert context.find_birth_years("2015", NOVEMBER_2026, RULES) == [2015]
    # 2026 is geen geboortejaar in de jeugdindeling (NK 2026)
    assert context.find_birth_years("Wanneer is het NK 2026?", NOVEMBER_2026, RULES) == []
    assert context.find_birth_years("geboren 2012 en 2012", NOVEMBER_2026, RULES) == [2012]


def test_find_birth_years_includes_next_cyclocross_season():
    # in 2026 nog 4 jaar, maar per 1 januari 2027 U6 in het veldritseizoen 2026-2027
    assert context.find_birth_years("geboren in 2022", NOVEMBER_2026, RULES) == [2022]


def test_category_line_road_differs_from_cyclocross_in_autumn():
    line = context.category_line(2015, NOVEMBER_2026, RULES)
    assert "wegwielrennen 2026: U12" in line
    assert "veldrijden seizoen 2026-2027: U13" in line
    assert "KNWU Licentie U13" in line
    assert "artikel 20.0.004" in line and "versie 2026-09-21" in line


def test_build_context_lines_date_only_on_new_conversation():
    first = context.build_context_lines("Wanneer is de volgende wedstrijd?", NOVEMBER_2026, RULES, True)
    follow_up = context.build_context_lines("En in Hilversum?", NOVEMBER_2026, RULES, False)
    assert len(first) == 1 and "9 november 2026" in first[0]
    assert follow_up == []


def test_add_context_puts_question_first():
    message = context.add_context("Welke licentie?", ["regel"])
    assert message.startswith("Welke licentie?")
    assert message.endswith(f"{context.CONTEXT_HEADER}\n- regel")
    assert context.add_context("Welke licentie?", []) == "Welke licentie?"
