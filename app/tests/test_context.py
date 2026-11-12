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


def test_licence_boundaries():
    assert knwu_categories.licence(2014, 2026, RULES) == "KNWU Licentie U13"
    assert knwu_categories.licence(2013, 2026, RULES) == "KNWU Licentie U17"
    assert knwu_categories.licence(2012, 2026, RULES) == "KNWU Licentie U17"
    assert knwu_categories.licence(2009, 2026, RULES) is None


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


def test_find_birth_years_bare_year_outside_youth():
    # reviewronde 1: kaal jaartal als antwoord op de geboortejaar-vraag valt buiten
    # de jeugdindeling, maar moet wél een contextregel krijgen (anders verzint het
    # model een categorie, gezien: JO11 voor 2025)
    assert context.find_birth_years("2025", NOVEMBER_2026, RULES) == [2025]
    assert context.find_birth_years("2025!", NOVEMBER_2026, RULES) == [2025]


def test_find_birth_years_explicit_birth_year_outside_youth():
    assert context.find_birth_years("geboren in 2025", NOVEMBER_2026, RULES) == [2025]
    # een jaartal ver van het sleutelwoord (bv. NK 2026) telt niet als geboortejaar
    assert context.find_birth_years(
        "Hij is geboren in 2015; wanneer is het NK 2026?", NOVEMBER_2026, RULES
    ) == [2015]


def test_category_line_outside_youth():
    line = context.category_line(2025, NOVEMBER_2026, RULES)
    assert "wegwielrennen 2026: valt buiten de jeugdindeling" in line
    assert "veldrijden seizoen 2026-2027: valt buiten de jeugdindeling" in line
    assert "geen jeugdlicentie" in line


def test_build_context_lines_bare_year_outside_youth():
    lines = context.build_context_lines("2025", NOVEMBER_2026, RULES, False)
    assert lines == [
        context.language_line("B1"),
        context.category_line(2025, NOVEMBER_2026, RULES),
    ]


def test_category_line_road_differs_from_cyclocross_in_autumn():
    line = context.category_line(2015, NOVEMBER_2026, RULES)
    assert "wegwielrennen 2026: U12" in line
    assert "veldrijden seizoen 2026-2027: U13" in line
    assert "KNWU Licentie U13" in line
    assert "artikel 20.0.004" in line and "versie 2026-09-21" in line


def test_build_context_lines_date_only_on_new_conversation():
    first = context.build_context_lines("Wanneer is de volgende wedstrijd?", NOVEMBER_2026, RULES, True)
    follow_up = context.build_context_lines("En in Hilversum?", NOVEMBER_2026, RULES, False)
    # taalniveau-regel staat op élk bericht (issue #52), de datum alleen bij een nieuwe conversatie
    assert len(first) == 2
    assert first[0] == "Voor deze gebruiker is vastgesteld taalniveau: B1"
    assert "9 november 2026" in first[1]
    assert follow_up == ["Voor deze gebruiker is vastgesteld taalniveau: B1"]


def test_language_line_normalizes_to_b1_or_b2():
    assert context.language_line("B1") == "Voor deze gebruiker is vastgesteld taalniveau: B1"
    assert context.language_line("B2") == "Voor deze gebruiker is vastgesteld taalniveau: B2"
    # leeg, ongeldig of kleine letters -> standaard B1
    assert context.language_line("") == "Voor deze gebruiker is vastgesteld taalniveau: B1"
    assert context.language_line("b2") == "Voor deze gebruiker is vastgesteld taalniveau: B1"
    assert context.language_line("van alles") == "Voor deze gebruiker is vastgesteld taalniveau: B1"


def test_build_context_lines_language_level_on_every_message():
    first = context.build_context_lines(
        "vraag", NOVEMBER_2026, RULES, True, language_level="B2"
    )
    follow_up = context.build_context_lines(
        "vervolgvraag", NOVEMBER_2026, RULES, False, language_level="B2"
    )
    assert first[0] == "Voor deze gebruiker is vastgesteld taalniveau: B2"
    assert follow_up == ["Voor deze gebruiker is vastgesteld taalniveau: B2"]
    # ongeldige waarde wordt B1
    assert context.build_context_lines("vraag", NOVEMBER_2026, RULES, False, language_level="gek")[0] == (
        "Voor deze gebruiker is vastgesteld taalniveau: B1"
    )


def test_add_context_puts_question_first():
    message = context.add_context("Welke licentie?", ["regel"])
    assert message.startswith("Welke licentie?")
    assert message.endswith(f"{context.CONTEXT_HEADER}\n- regel")
    assert context.add_context("Welke licentie?", []) == "Welke licentie?"


# --- oude categorie-indeling en kalenderaanduiding (issue #61) ---


def test_old_category_line_combined_category():
    assert context.old_designation_lines("Wanneer rijdt categorie 3?", RULES) == [
        'Oude aanduiding "categorie 3" = categorie 3 (JO11/MO12): jongens U11, meisjes U12.'
    ]


def test_old_category_1_has_two_age_groups():
    assert context.old_designation_lines("categorie 1", RULES) == [
        'Oude aanduiding "categorie 1" = categorie 1 (JO8/MO9 en JO9/MO10): '
        "jongens U8 en U9, meisjes U9 en U10."
    ]


def test_old_category_7_has_only_boys():
    assert context.old_designation_lines("cat 7", RULES) == [
        'Oude aanduiding "categorie 7" = categorie 7 (JO15): jongens U15.'
    ]


def test_old_category_spellings():
    expected = [context.old_category_line(3, RULES)]
    for message in ("categorie 3", "Categorie 3", "cat 3", "cat. 3", "Cat.3", "CAT 3"):
        assert context.old_designation_lines(message, RULES) == expected, message


def test_old_category_all_numbers_translate():
    notations = {
        2: "JO10/MO11", 3: "JO11/MO12", 4: "JO12/MO13", 5: "JO13/MO14", 6: "JO14/MO15", 7: "JO15",
    }
    for number, notation in notations.items():
        assert f"categorie {number} ({notation})" in context.old_category_line(number, RULES)


def test_old_category_lists_and_ranges():
    assert context.old_category_numbers("categorieën 3 en 4") == [3, 4]
    assert context.old_category_numbers("cat. 3/4") == [3, 4]
    assert context.old_category_numbers("categorie 2, 3 en 5") == [2, 3, 5]
    assert context.old_category_numbers("categorie 1 t/m 3") == [1, 2, 3]
    assert context.old_category_numbers("cat 5-7") == [5, 6, 7]


def test_old_category_0_does_not_exist():
    assert context.old_designation_lines("Is er een categorie 0?", RULES) == [
        'Oude aanduiding "categorie 0" bestaat niet; de oude indeling begint bij '
        "categorie 1 (JO8/MO9 en JO9/MO10)."
    ]


def test_old_category_outside_range_gives_no_line():
    assert context.old_designation_lines("categorie 8", RULES) == []
    assert context.old_designation_lines("categorie 2015", RULES) == []


def test_nieuwelingen_is_u17_nieuweling():
    expected = ['Oude aanduiding "nieuwelingen" = U17 Nieuweling.']
    assert context.old_designation_lines("Hoe lang rijden de nieuwelingen?", RULES) == expected
    assert context.old_designation_lines("Mijn zoon is nieuweling", RULES) == expected


def test_calendar_pair():
    assert context.old_designation_lines("Wedstrijd MU12, VU13 om 10:00", RULES) == [
        'Kalenderaanduiding "MU12, VU13" = JO12/MO13: jongens U12, meisjes U13.'
    ]
    assert context.old_designation_lines("MU12/VU13", RULES) == context.old_designation_lines(
        "MU12, VU13", RULES
    )


def test_calendar_single():
    assert context.old_designation_lines("Wanneer start MU12?", RULES) == [
        'Kalenderaanduiding "MU12" = JO12: jongens U12.'
    ]
    assert context.old_designation_lines("VU10", RULES) == [
        'Kalenderaanduiding "VU10" = MO10: meisjes U10.'
    ]
    assert context.old_designation_lines("MU17", RULES) == [
        'Kalenderaanduiding "MU17" = JO17: jongens U17 Nieuweling.'
    ]


def test_calendar_outside_youth_gives_no_line():
    assert context.old_designation_lines("MU23 en VU23", RULES) == []


def test_no_old_designation_in_new_or_unrelated_text():
    for message in (
        "Wanneer is de volgende wedstrijd?",
        "Wat is een Cat. II nationale wedstrijd?",
        "In welke categorie rijdt mijn dochter?",
        "Mag een U13 al op de baan?",
        "Wat mag een U17 Nieuweling verzetten?",
        "Hoeveel U17-nieuwelingen starten er?",
        "Welke leeftijdscategorie 3 jaar later?",
        "JO11/MO12",
        "geboren in 2015",
    ):
        assert context.old_designation_lines(message, RULES) == [], message


def test_build_context_lines_unchanged_without_old_designation():
    message = "Welke versnelling mag een meisje geboren in 2015?"
    lines = context.build_context_lines(message, NOVEMBER_2026, RULES, False)
    assert lines == [
        context.language_line("B1"),
        context.category_line(2015, NOVEMBER_2026, RULES),
    ]


def test_build_context_lines_adds_old_designation_after_birth_year():
    lines = context.build_context_lines(
        "Mijn zoon (2015) rijdt in categorie 3", NOVEMBER_2026, RULES, False
    )
    assert lines[1] == context.category_line(2015, NOVEMBER_2026, RULES)
    assert lines[2] == context.old_category_line(3, RULES)
    assert len(lines) == 3


def test_old_designation_lines_deduplicate():
    assert len(context.old_designation_lines("categorie 3, cat. 3 en categorie 3", RULES)) == 1
