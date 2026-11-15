"""Tests voor de deterministische lookup-laag (#91/#94) — offline, puur functies."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knwu_categories  # noqa: E402
import lookups  # noqa: E402

RULES = knwu_categories.load_rules()
NOVEMBER_2026 = date(2026, 11, 9)


# --- match_lookup: welke vragen zijn een pure lookup? ---


def test_categorie_vraag_met_geboortejaar_is_lookup():
    m = lookups.match_lookup(
        "In welke leeftijdscategorie rijdt een jongen geboren in 2013 bij wegwielrennen in 2026?",
        NOVEMBER_2026,
        RULES,
    )
    assert m == {"kind": "categorie", "birth_year": 2013}


def test_licentie_vraag_met_geboortejaar_is_lookup():
    m = lookups.match_lookup(
        "Welke licentie heeft mijn zoon nodig? Hij is geboren in 2012.",
        NOVEMBER_2026,
        RULES,
    )
    assert m == {"kind": "licentie", "birth_year": 2012}


def test_verzet_vraag_met_categorie_en_discipline_is_lookup():
    m = lookups.match_lookup(
        "Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?",
        NOVEMBER_2026,
        RULES,
    )
    assert m == {"kind": "verzet", "category": "U15", "discipline": "weg"}


def test_verzet_vraag_zonder_discipline_is_geen_lookup():
    # de agent moet eerst vragen: weg of veld?
    assert lookups.match_lookup("Welk verzet mag U15 maximaal rijden?", NOVEMBER_2026, RULES) is None


def test_verzet_met_nieuwelingen_wordt_u17():
    m = lookups.match_lookup(
        "Welk maximaal verzet geldt voor U17 (nieuwelingen) bij wegwielrennen?",
        NOVEMBER_2026,
        RULES,
    )
    assert m["category"] == "U17 Nieuweling"


def test_kaal_jaartal_is_lookup():
    # vervolg op de vraag naar het geboortejaar (#91 besluit 5)
    assert lookups.match_lookup("2015", NOVEMBER_2026, RULES) == {
        "kind": "categorie",
        "birth_year": 2015,
    }


def test_oude_aanduiding_met_vertaalvraag_is_lookup():
    m = lookups.match_lookup("Wat is categorie 3 in de nieuwe indeling?", NOVEMBER_2026, RULES)
    assert m == {"kind": "vertaling"}


def test_waarom_vraag_is_geen_lookup():
    assert lookups.match_lookup("Waarom rijdt mijn zoon in U12?", NOVEMBER_2026, RULES) is None


@pytest.mark.parametrize(
    "message",
    [
        "Hoe meet ik het verzet voor U13 op de weg?",
        "Welke uitzonderingen gelden voor het verzet van U13 op de weg?",
        "Welke categorie is categorie 3 en wat zijn de regels?",
        "Wat is categorie 8 in de nieuwe indeling?",
    ],
)
def test_lookup_does_not_answer_explanations_or_unknown_designations(message):
    assert lookups.match_lookup(message, NOVEMBER_2026, RULES) is None


def test_licentiepakketten_vraag_is_geen_lookup():
    # pakketten/prijzen komen uit het Kenniscentrum, niet uit de tabel
    assert (
        lookups.match_lookup(
            "Welke licentiepakketten kent de KNWU voor jeugd in 2026 en wat kost elk pakket?",
            NOVEMBER_2026,
            RULES,
        )
        is None
    )


def test_categorie_en_licentie_samen_is_geen_lookup():
    # cross-check met bronconflict-mogelijkheid (#47) -> agent
    assert (
        lookups.match_lookup(
            "In welke leeftijdscategorie rijdt een renner die in 2026 15 jaar wordt met een KNWU Licentie U17?",
            NOVEMBER_2026,
            RULES,
        )
        is None
    )


def test_leeftijd_in_jaren_is_geen_lookup():
    # "15-jarige" kan een bronconflict opleveren; alleen expliciete geboortejaren bypassen
    assert (
        lookups.match_lookup("Welke leeftijdscategorie is een 15-jarige in 2026?", NOVEMBER_2026, RULES)
        is None
    )


def test_reglement_vraag_is_geen_lookup():
    assert (
        lookups.match_lookup("Mag een kind van 6 meedoen met nationale wedstrijden?", NOVEMBER_2026, RULES)
        is None
    )


def test_verhelderingsvraag_zonder_geboortejaar_is_geen_lookup():
    assert lookups.match_lookup("Welke licentie moet ik aanvragen voor mijn zoon?", NOVEMBER_2026, RULES) is None
    assert lookups.match_lookup("In welke categorie rijdt mijn zoon?", NOVEMBER_2026, RULES) is None


def test_algemene_vraag_is_geen_lookup():
    assert lookups.match_lookup("Wanneer is de volgende wedstrijd?", NOVEMBER_2026, RULES) is None
    assert lookups.match_lookup("Hoeveel kost de contributie?", NOVEMBER_2026, RULES) is None


def test_extra_geboortejaar_uit_intake_vult_aan():
    m = lookups.match_lookup("Welke licentie heb ik nodig?", NOVEMBER_2026, RULES, extra={"geboortejaar": 2012})
    assert m == {"kind": "licentie", "birth_year": 2012}


def test_extra_discipline_uit_intake_vult_aan():
    m = lookups.match_lookup(
        "Wat is het maximale verzet voor U13?", NOVEMBER_2026, RULES, extra={"discipline": "veld"}
    )
    assert m == {"kind": "verzet", "category": "U13", "discipline": "veld"}


@pytest.mark.parametrize(
    ("message", "extra"),
    [
        ("Welk verzet voor U9 op de baan?", None),
        ("Welk verzet voor U9 op de baan en op de weg?", {"discipline": "weg"}),
        ("Welk verzet voor U9?", {"discipline": "baan"}),
    ],
)
def test_track_cycling_never_bypasses(message, extra):
    assert lookups.match_lookup(message, NOVEMBER_2026, RULES, extra=extra) is None


def test_render_lookup_rejects_track_cycling():
    with pytest.raises(ValueError, match="buiten scope"):
        lookups.render_lookup_answer(
            {"kind": "verzet", "category": "U9", "discipline": "baan"},
            "Welk verzet voor U9 op de baan?",
            RULES,
            NOVEMBER_2026,
            "B2",
        )


def test_former_words_without_category_request_do_not_trigger_translation():
    assert lookups.match_lookup("Was U12 leuk?", NOVEMBER_2026, RULES) is None


# --- render_lookup_answer: templates met bron+versie+artikel ---


def _render(message, level, today=NOVEMBER_2026):
    m = lookups.match_lookup(message, today, RULES)
    assert m is not None, message
    return lookups.render_lookup_answer(m, message, RULES, today, level)


def test_render_categorie_b1_heeft_geen_bron_regel():
    answer = _render(
        "In welke leeftijdscategorie rijdt een jongen geboren in 2015 bij wegwielrennen in 2026?", "B1"
    )
    assert "U12" in answer
    assert "2015" in answer
    assert "KNWU Licentie U13" in answer
    assert "Bron:" not in answer  # B1-regel (#52): géén bronvermelding


def test_render_categorie_b2_citeert_bron_versie_en_artikel():
    answer = _render(
        "In welke leeftijdscategorie rijdt een jongen geboren in 2013 bij wegwielrennen in 2026?", "B2"
    )
    assert "U14" in answer
    assert "Bron:" in answer
    assert RULES["bron"] in answer
    assert f"versie {RULES['versie']}" in answer
    assert "artikel 20.0.004" in answer
    assert "artikel 20.0.002" in answer


def test_render_licentie_bevat_licentie_en_categorie():
    answer = _render("Welke licentie heeft mijn zoon nodig? Hij is geboren in 2012.", "B2")
    assert "KNWU Licentie U17" in answer
    assert "U15" in answer  # weg 2026


def test_render_verzet_weg_b2():
    answer = _render(
        "Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?", "B2"
    )
    assert "6,70 meter" in answer
    assert "U15" in answer
    assert "artikel 20.1.007" in answer
    assert RULES["verzetten"]["bron"] in answer


def test_render_verzet_nieuwelingen_noemt_nieuwelingen():
    answer = _render(
        "Welk maximaal verzet geldt voor U17 (nieuwelingen) bij wegwielrennen?", "B2"
    )
    assert "7,68 meter" in answer
    assert "nieuwelingen" in answer


def test_render_verzet_veld_is_vrij():
    answer = _render("Wat is het verzet voor U9 in het veld?", "B1")
    assert "vrij" in answer
    assert "Bron:" not in answer


def test_render_verzet_nvt():
    answer = _render("Wat is het verzet voor U6 in het veld?", "B1")
    assert "NVT" in answer


def test_render_buiten_jeugdindeling():
    answer = _render("2008", "B1")
    assert "buiten de jeugdindeling" in answer


def test_render_vertaling_oude_categorie():
    answer = _render("Wat is categorie 3 in de nieuwe indeling?", "B2")
    assert "JO11/MO12" in answer
    assert "Bron:" in answer
    assert RULES["oude_categorie_indeling"]["bron"] in answer

def test_render_eindigt_op_library_disclaimer():
    # #91 besluit 4: het standaardantwoord eindigt met de disclaimer die aangeeft
    # wanneer de document-library wél geraadpleegd wordt
    answer = _render("In welke leeftijdscategorie rijdt een jongen geboren in 2015?", "B1")
    assert "KNWU-documenten" in answer
    assert "Bron:" not in answer  # B1-regel (#52) blijft gelden
    answer_b2 = _render("In welke leeftijdscategorie rijdt een jongen geboren in 2015?", "B2")
    assert "KNWU-documenten" in answer_b2
    assert "Bron:" in answer_b2
