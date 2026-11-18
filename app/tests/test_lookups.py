"""Tests voor de deterministische lookup-laag (#91/#94) — offline, puur functies."""

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knwu_categories  # noqa: E402
import lookups  # noqa: E402

RULES = knwu_categories.load_rules()
NOVEMBER_2026 = date(2026, 11, 9)


def test_recognize_birth_year_renders_combined_gender_specific_overview():
    decision = lookups.recognize_turn("2015", None, NOVEMBER_2026, RULES)

    assert decision.kind == "ready_for_bypass"
    assert decision.next_state.kind == "completed"
    answer = lookups.render_answer(decision, "B1")

    assert "**Geboortejaar 2015**" in answer
    assert "### Veldrijden 2026-2027 · Jongens" in answer
    assert "### Wegwielrennen 2027 · Meisjes" in answer
    assert "5,90 meter" in answer
    assert not any(line.startswith("Bron:") for line in answer.splitlines())


def test_paired_category_keeps_its_gender_specific_members_per_season():
    today = date(2026, 6, 1)
    decision = lookups.recognize_turn(
        "Welke categorie voor JO11/MO12?", None, today, RULES
    )

    assert decision.kind == "ready_for_bypass"
    answer = lookups.render_answer(decision, "B2")

    assert "**JO11/MO12**" in answer
    assert "### Wegwielrennen 2026 · Jongens · geboortejaar 2016" in answer
    assert "### Wegwielrennen 2026 · Meisjes · geboortejaar 2015" in answer
    assert "### Veldrijden 2026-2027 · Jongens · geboortejaar 2017" in answer
    assert "### Veldrijden 2026-2027 · Meisjes · geboortejaar 2016" in answer
    assert "artikel 20.0.004" in answer
    assert "artikel 20.1.007" in answer


@pytest.mark.parametrize(
    ("question", "expected_category"),
    [
        ("Welke categorie voor JO11?", "U11"),
        ("Welke categorie voor JO11/MO12?", "U12"),
    ],
)
def test_gender_followup_replaces_single_prefix_or_filters_a_pair(question, expected_category):
    first = lookups.recognize_turn(question, None, date(2026, 6, 1), RULES)
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "alleen meisjes", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert {row.gender for row in followup.ready.rows} == {"meisjes"}
    assert {row.category for row in followup.ready.rows} == {expected_category}


def test_new_primary_year_fragment_replaces_category_but_keeps_filters():
    first = lookups.recognize_turn(
        "Welke categorie voor een jongen geboren in 2015 bij wegwielrennen?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "en voor 2017?", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert {row.birth_year for row in followup.ready.rows} == {2017}
    assert {row.gender for row in followup.ready.rows} == {"jongens"}
    assert {row.season.discipline for row in followup.ready.rows} == {"weg"}


def test_data_only_message_starts_a_profile_that_a_new_year_replaces():
    first = lookups.recognize_turn("jongen uit 2015, U12, weg", None, date(2026, 6, 1), RULES)

    assert first.kind == "ready_for_bypass"
    assert [
        (row.season.discipline, row.gender, row.category, row.birth_year)
        for row in first.ready.rows
    ] == [("weg", "jongens", "U12", 2015)]

    followup = lookups.recognize_turn("en voor 2017?", first.next_state, date(2026, 6, 1), RULES)

    assert followup.kind == "ready_for_bypass"
    assert {(row.gender, row.season.discipline, row.birth_year) for row in followup.ready.rows} == {
        ("jongens", "weg", 2017)
    }


def test_data_only_reply_completes_a_pending_lookup_and_keeps_its_filters():
    pending = lookups.recognize_turn("Welk verzet op de weg?", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    reply = lookups.recognize_turn("jongen uit 2015", pending.next_state, NOVEMBER_2026, RULES)

    assert reply.kind == "ready_for_bypass"
    assert {(row.gender, row.season.discipline, row.birth_year) for row in reply.ready.rows} == {
        ("jongens", "weg", 2015)
    }


def test_bare_year_in_a_data_only_message_is_a_birth_year():
    decision = lookups.recognize_turn("2015, meisjes", None, NOVEMBER_2026, RULES)

    assert decision.kind == "ready_for_bypass"
    assert decision.ready.heading == "Geboortejaar 2015"
    assert {row.gender for row in decision.ready.rows} == {"meisjes"}


@pytest.mark.parametrize(
    "message",
    ["jongen, weg", "jongen uit 2015 heeft een nieuwe fiets", "2015, 2017"],
)
def test_data_only_message_needs_a_primary_input_and_only_known_data(message):
    assert lookups.recognize_turn(message, None, NOVEMBER_2026, RULES).kind == "not_eligible_for_bypass"


def test_complete_question_starts_without_inherited_filters():
    first = lookups.recognize_turn(
        "Welke categorie voor een jongen geboren in 2015 bij wegwielrennen?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    new_question = lookups.recognize_turn(
        "Welke categorie voor geboortejaar 2017?",
        first.next_state,
        date(2026, 6, 1),
        RULES,
    )

    assert new_question.kind == "ready_for_bypass"
    assert {row.gender for row in new_question.ready.rows} == {"jongens", "meisjes"}
    assert {row.season.discipline for row in new_question.ready.rows} == {"weg", "veld"}


def test_unrelated_turn_clears_a_pending_profile():
    pending = lookups.recognize_turn("Welk verzet?", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    unrelated = lookups.recognize_turn(
        "Hoi", pending.next_state, NOVEMBER_2026, RULES
    )

    assert unrelated.kind == "not_eligible_for_bypass"
    assert unrelated.next_state.kind == "none"


def test_discipline_followup_replaces_only_the_discipline_filter():
    first = lookups.recognize_turn(
        "Welke categorie voor een jongen geboren in 2015 bij wegwielrennen?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "alleen veldrijden", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert {row.gender for row in followup.ready.rows} == {"jongens"}
    assert {row.season.discipline for row in followup.ready.rows} == {"veld"}


def test_old_category_gender_followup_filters_its_mapped_pairs():
    first = lookups.recognize_turn(
        "Welke categorie voor oude categorie 1?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "alleen meisjes", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert {row.gender for row in followup.ready.rows} == {"meisjes"}
    assert {row.category for row in followup.ready.rows} == {"U9", "U10"}


def test_short_old_category_fragment_replaces_primary_and_keeps_other_filters():
    first = lookups.recognize_turn(
        "Welke categorie voor een jongen geboren in 2015 bij wegwielrennen?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "cat. 3", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert "**Oude cat. 3 (JO11/MO12)**" in lookups.render_answer(followup, "B1")
    assert {row.gender for row in followup.ready.rows} == {"jongens"}
    assert {row.season.discipline for row in followup.ready.rows} == {"weg"}


def test_calendar_category_fragment_keeps_existing_gender_and_discipline_filters():
    first = lookups.recognize_turn(
        "Welke categorie voor een jongen geboren in 2015 bij wegwielrennen?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert first.kind == "ready_for_bypass"

    followup = lookups.recognize_turn(
        "MU11, VU12", first.next_state, date(2026, 6, 1), RULES
    )

    assert followup.kind == "ready_for_bypass"
    assert {row.gender for row in followup.ready.rows} == {"jongens"}
    assert {row.season.discipline for row in followup.ready.rows} == {"weg"}
    assert {row.category for row in followup.ready.rows} == {"U11"}


def test_missing_lookup_primary_input_can_be_completed_by_a_birth_year():
    pending = lookups.recognize_turn("Welk verzet?", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"
    assert pending.next_state.kind == "pending"

    completed = lookups.recognize_turn("2012", pending.next_state, NOVEMBER_2026, RULES)

    assert completed.kind == "ready_for_bypass"
    assert {row.season.discipline for row in completed.ready.rows} == {"weg", "veld"}
    assert {row.gender for row in completed.ready.rows} == {"jongens", "meisjes"}


@pytest.mark.parametrize(
    ("reply", "expected_category"),
    [
        ("geboortejaar 2015", "U13"),
        ("geboren in 2015", "U13"),
        ("nieuwelingen", "U17 Nieuweling"),
    ],
)
def test_pending_lookup_accepts_short_keyword_replies(reply, expected_category):
    pending = lookups.recognize_turn("Welk verzet op de weg?", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    completed = lookups.recognize_turn(reply, pending.next_state, NOVEMBER_2026, RULES)

    assert completed.kind == "ready_for_bypass"
    assert {row.category for row in completed.ready.rows} == {expected_category}
    assert {row.season.discipline for row in completed.ready.rows} == {"weg"}


def test_abbreviated_question_word_is_a_complete_gearing_question():
    decision = lookups.recognize_turn("wlk verzet voor u8", None, NOVEMBER_2026, RULES)

    assert decision.kind == "ready_for_bypass"
    assert {row.category for row in decision.ready.rows} == {"U8"}


def test_intake_completes_only_the_explicit_unqualified_year_from_the_request():
    pending = lookups.recognize_turn("Welk verzet? 2012", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    completed = lookups.complete_with_intake(
        pending, {"geboortejaar": 2012}, NOVEMBER_2026, RULES
    )

    assert completed.kind == "ready_for_bypass"
    assert {row.season.discipline for row in completed.ready.rows} == {"weg", "veld"}
    assert {row.gender for row in completed.ready.rows} == {"jongens", "meisjes"}


def test_intake_completion_matches_direct_lookup_outside_the_youth_classification():
    pending = lookups.recognize_turn("Welk verzet? 2005", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    completed = lookups.complete_with_intake(
        pending, {"geboortejaar": 2005}, NOVEMBER_2026, RULES
    )
    direct = lookups.recognize_turn("2005", None, NOVEMBER_2026, RULES)

    assert completed.kind == "ready_for_bypass"
    assert direct.kind == "ready_for_bypass"
    assert lookups.render_answer(completed, "B1") == lookups.render_answer(direct, "B1")
    assert "Geboortejaar 2005 valt buiten de jeugdindeling." in lookups.render_answer(
        completed, "B1"
    )


def test_intake_cannot_replace_the_unqualified_year_with_another_year():
    pending = lookups.recognize_turn("Welk verzet? 2012", None, NOVEMBER_2026, RULES)
    assert pending.kind == "needs_input_for_bypass"

    completed = lookups.complete_with_intake(
        pending, {"geboortejaar": 2013}, NOVEMBER_2026, RULES
    )

    assert completed.kind == "needs_input_for_bypass"


def test_intake_cannot_infer_a_birth_year_from_age_or_unstated_input():
    pending = lookups.recognize_turn("Welk verzet?", None, NOVEMBER_2026, RULES)

    completed = lookups.complete_with_intake(
        pending,
        {"geboortejaar": 2012, "leeftijd": 14},
        NOVEMBER_2026,
        RULES,
    )

    assert completed.kind == "needs_input_for_bypass"


def test_intake_completion_rejects_non_pending_decisions():
    ready = lookups.recognize_turn("2015", None, NOVEMBER_2026, RULES)
    assert ready.kind == "ready_for_bypass"

    with pytest.raises(TypeError, match="NeedsInputForBypass"):
        lookups.complete_with_intake(ready, {}, NOVEMBER_2026, RULES)


def test_old_category_one_keeps_both_pairs_and_corrected_girls_field_gearing():
    decision = lookups.recognize_turn(
        "Welke categorie en verzet voor oude categorie 1?",
        None,
        date(2026, 6, 1),
        RULES,
    )

    assert decision.kind == "ready_for_bypass"
    assert decision.ready.heading == "Oude cat. 1 (JO9/MO10)"
    assert {
        (row.gender, row.category)
        for row in decision.ready.rows
    } == {
        ("jongens", "U8"),
        ("jongens", "U9"),
        ("meisjes", "U9"),
        ("meisjes", "U10"),
    }
    assert any(
        row.gender == "meisjes"
        and row.category == "U9"
        and row.season.discipline == "veld"
        and row.gear == "vrij"
        for row in decision.ready.rows
    )


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 2, 15), [("veld", 2025, 2026), ("weg", 2026, 2026)]),
        (date(2026, 3, 1), [("weg", 2026, 2026), ("veld", 2026, 2027)]),
        (date(2026, 9, 30), [("weg", 2026, 2026), ("veld", 2026, 2027)]),
        (date(2026, 10, 1), [("veld", 2026, 2027), ("weg", 2027, 2027)]),
    ],
)
def test_candidate_seasons_follow_the_calendar_boundaries(today, expected):
    decision = lookups.recognize_turn("2014", None, today, RULES)

    assert decision.kind == "ready_for_bypass"
    actual = []
    for row in decision.ready.rows:
        season_key = (row.season.discipline, row.season.start_year, row.season.end_year)
        if season_key not in actual:
            actual.append(season_key)
    assert actual == expected


def test_cross_season_answer_shows_calendar_year_licence_switch_on_one_line():
    decision = lookups.recognize_turn("2014", None, date(2026, 3, 1), RULES)

    assert decision.kind == "ready_for_bypass"
    row = next(
        row
        for row in decision.ready.rows
        if row.season.discipline == "veld" and row.gender == "jongens"
    )
    assert [(fact.name, fact.period) for fact in row.licences] == [
        ("KNWU Licentie U13", "t/m dec 2026"),
        ("KNWU Licentie U17", "vanaf jan 2027"),
    ]
    answer = lookups.render_answer(decision, "B1")
    assert "U13 (t/m dec 2026), U17 (vanaf jan 2027)" in answer


def test_birth_year_and_paired_category_filter_the_same_gender_category_pair():
    decision = lookups.recognize_turn(
        "Welke categorie voor geboortejaar 2015 en JO11/MO12?",
        None,
        date(2026, 6, 1),
        RULES,
    )

    assert decision.kind == "ready_for_bypass"
    assert [
        (row.season.discipline, row.gender, row.category, row.birth_year)
        for row in decision.ready.rows
    ] == [("weg", "meisjes", "U12", 2015)]


@pytest.mark.parametrize(
    "message",
    [
        "Welke categorie voor een 12-jarige?",
        "Welke categorie voor JO11 meisjes?",
        "Welke categorie voor JO11 en U12?",
        "Welke categorie voor geboortejaar 2015 in 2025?",
        "Welke categorie in 2015?",
        "Welke categorie voor mijn twee zoons geboren in 2015?",
        "Waarom rijdt mijn zoon in U12?",
        "Wat is categorie 8 in de nieuwe indeling?",
        "Mijn verzet is kapot.",
        "Welk verzet voor U11 bij mountainbiken?",
        "Welk verzet voor U11 bij BMX?",
        "Welk verzet voor U11 als ik hoger start bij combinatiewedstrijden?",
        "Welke categorie voor mijn zoon geboren in 2015, en hoe vraag ik zijn licentie aan?",
        "In welke leeftijdscategorie rijdt een jongen geboren in 2015 bij wegwielrennen in 2026?",
    ],
)
def test_unsupported_or_conflicting_input_is_not_bypass_eligible(message):
    decision = lookups.recognize_turn(message, None, NOVEMBER_2026, RULES)

    assert decision.kind == "not_eligible_for_bypass"
    assert decision.next_state.kind == "none"


@pytest.mark.parametrize(
    ("birth_year", "today", "expected_age"),
    [
        (2021, date(2026, 2, 1), 5),
        (2010, date(2026, 2, 1), 16),
    ],
)
def test_season_rows_include_the_supported_age_boundaries(birth_year, today, expected_age):
    decision = lookups.recognize_turn(str(birth_year), None, today, RULES)

    assert decision.kind == "ready_for_bypass"
    assert all(row.season.reference_year - row.birth_year == expected_age for row in decision.ready.rows)
    assert decision.ready.outside_youth_birth_year is None


def test_birth_year_beyond_supported_age_range_uses_only_safe_standalone_answer():
    decision = lookups.recognize_turn("2009", None, date(2026, 2, 1), RULES)

    assert decision.kind == "ready_for_bypass"
    assert decision.ready.rows == ()
    assert decision.ready.outside_youth_birth_year == 2009
    assert "valt buiten de jeugdindeling" in lookups.render_answer(decision, "B1")


def test_no_candidate_season_does_not_mislabel_a_current_youth_year_as_outside():
    decision = lookups.recognize_turn("2010", None, date(2026, 10, 1), RULES)

    assert decision.kind == "not_eligible_for_bypass"


def test_u16_normalizes_to_the_newling_category_for_both_seasons():
    decision = lookups.recognize_turn(
        "Welk verzet voor U16 op de weg?",
        None,
        date(2026, 6, 1),
        RULES,
    )

    assert decision.kind == "ready_for_bypass"
    assert {row.category for row in decision.ready.rows} == {"U17 Nieuweling"}
    assert {row.gender for row in decision.ready.rows} == {"jongens", "meisjes"}


def test_standalone_knwu_17_plus_licence_remains_reachable():
    decision = lookups.recognize_turn(
        "Welke KNWU Licentie 17+ is nodig?",
        None,
        NOVEMBER_2026,
        RULES,
    )

    assert decision.kind == "ready_for_bypass"
    answer = lookups.render_answer(decision, "B2")
    assert "**KNWU Licentie 17+**" in answer
    assert "artikel 20.0.002" in answer
    assert answer.splitlines()[-1].startswith("Bron:")
    b1_answer = lookups.render_answer(decision, "B1")
    assert not any(line.startswith("Bron:") for line in b1_answer.splitlines())


@pytest.mark.parametrize("language_level", ["B1", "B2"])
def test_combined_overview_uses_flat_markdown_and_level_appropriate_source_line(language_level):
    decision = lookups.recognize_turn(
        "Welk verzet voor U11?",
        None,
        date(2026, 6, 1),
        RULES,
    )
    assert decision.kind == "ready_for_bypass"

    answer = lookups.render_answer(decision, language_level)
    lines = answer.splitlines()
    source_lines = [index for index, line in enumerate(lines) if line.startswith("Bron:")]

    assert "5,90 meter" in answer
    assert "5,50 meter" in answer
    assert re.search(r"^[ \t]+[-*]\s", answer, re.MULTILINE) is None
    if language_level == "B2":
        assert len(source_lines) == 1
        assert source_lines[0] == len(lines) - 1
        assert "artikel 20.1.007" in answer
        assert "artikel 20.0.002" in answer
    else:
        assert source_lines == []


def test_b2_source_line_names_each_document_once():
    decision = lookups.recognize_turn("2014", None, NOVEMBER_2026, RULES)
    assert decision.kind == "ready_for_bypass"

    b1_answer = lookups.render_answer(decision, "B1")
    assert not any(line.startswith("Bron:") for line in b1_answer.splitlines())

    b2_answer = lookups.render_answer(decision, "B2")
    assert b2_answer.splitlines()[-1] == (
        f"Bron: {RULES['bron']}, versie {RULES['versie']} "
        f"(artikel {RULES['leeftijdscategorieen']['artikel']} en artikel {RULES['licenties']['artikel']}); "
        f"{RULES['verzetten']['bron']}, versie {RULES['verzetten']['versie']} "
        f"(artikel {RULES['verzetten']['artikel']}); "
        f"{RULES['oude_categorie_indeling']['bron']}"
    )


def test_conflicting_category_and_birth_year_does_not_fall_back_to_partial_answer():
    decision = lookups.recognize_turn(
        "Welke categorie voor geboortejaar 2015 en jongens U11?",
        None,
        date(2026, 6, 1),
        RULES,
    )

    assert decision.kind == "not_eligible_for_bypass"


def test_old_category_and_explicit_new_category_must_match():
    decision = lookups.recognize_turn(
        "Welke categorie voor oude categorie 3 en JO10?",
        None,
        date(2026, 6, 1),
        RULES,
    )

    assert decision.kind == "not_eligible_for_bypass"


@pytest.mark.parametrize(
    ("message", "expected_heading"),
    [
        ("Wat is categorie 3 in de nieuwe indeling?", "Oude cat. 3 (JO11/MO12)"),
        ("Wat is cat. 3?", "Oude cat. 3 (JO11/MO12)"),
        ("Welke oude categorie is MU11, VU12?", "JO11/MO12"),
        ("Wat betekent MU12, VU13?", "JO12/MO13"),
        ("Hoe heet nieuwelingen nu?", "U17 Nieuweling"),
    ],
)
def test_original_category_translation_forms_remain_recognizable(message, expected_heading):
    decision = lookups.recognize_turn(message, None, NOVEMBER_2026, RULES)

    assert decision.kind == "ready_for_bypass"
    assert decision.ready.heading == expected_heading


# --- legacy lookup-vormen via recognize_turn (#91/#99) ---


@pytest.mark.parametrize(
    "message",
    [
        "Mag een kind van 6 meedoen met nationale wedstrijden?",
        "Welke licentiepakketten kent de KNWU voor jeugd in 2026 en wat kost elk pakket?",
        "In welke leeftijdscategorie rijdt een renner die in 2026 15 jaar wordt met een KNWU Licentie U17?",
        "Hoe meet ik het verzet voor U13 op de weg?",
        "Welke categorie is categorie 3 en wat zijn de regels?",
        "Welk verzet voor U9 op de baan?",
        "Welk verzet voor U9 op de baan en op de weg?",
        "Wanneer is de volgende wedstrijd?",
        "Hoeveel kost de contributie?",
        "Was U12 leuk?",
    ],
)
def test_explanations_rules_and_unrelated_questions_stay_out_of_the_bypass(message):
    assert lookups.recognize_turn(message, None, NOVEMBER_2026, RULES).kind == "not_eligible_for_bypass"


@pytest.mark.parametrize(
    "message",
    [
        "Welke licentie moet ik aanvragen voor mijn zoon?",
        "In welke categorie rijdt mijn zoon?",
        "Welk verzet op de weg?",
    ],
)
def test_question_without_primary_input_waits_for_it(message):
    assert lookups.recognize_turn(message, None, NOVEMBER_2026, RULES).kind == "needs_input_for_bypass"


@pytest.mark.parametrize(
    "message",
    [
        "In welke leeftijdscategorie rijdt een jongen geboren in 2015 bij wegwielrennen?",
        "Welke licentie heeft mijn zoon nodig? Hij is geboren in 2012.",
        "Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?",
        "Welk maximaal verzet geldt voor U17 (nieuwelingen) bij wegwielrennen?",
        "Welk verzet voor categorie 2 op de weg?",
        "Wat is categorie 3 in de nieuwe indeling?",
        "Welke oude categorie is JO11/MO12?",
        "Welke categorie, verzet en licentie voor geboortejaar 2014?",
        "Welke KNWU Licentie 17+ is nodig?",
        "2008",
    ],
)
@pytest.mark.parametrize("language_level", ["B1", "B2"])
def test_every_bypass_answer_uses_supported_markdown_format(message, language_level):
    decision = lookups.recognize_turn(message, None, NOVEMBER_2026, RULES)
    assert decision.kind == "ready_for_bypass", message

    answer = lookups.render_answer(decision, language_level)
    assert re.search(r"^[ \t]+[-*]\s", answer, re.MULTILINE) is None
    lines = answer.splitlines()
    source_line_indexes = [index for index, line in enumerate(lines) if line.startswith("Bron:")]
    if language_level == "B2":
        assert source_line_indexes == [len(lines) - 1]
    else:
        assert source_line_indexes == []
    assert "Moet ik de KNWU-documenten doorzoeken voor een gedetailleerder antwoord?" in answer
