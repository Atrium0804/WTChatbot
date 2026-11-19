"""Tests voor de verzetadvies-rekenmodule (#148) — offline, pure functies."""

import copy
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knwu_categories  # noqa: E402
import verzet_advies  # noqa: E402
from verzet_advies import InvalidInput, VerzetAdvies, Wheel, advise  # noqa: E402

RULES = knwu_categories.load_rules()
# Geboortejaar 2012 in 2026 = 14 jaar = U15 jongens, maximaal toegestaan verzet 6.70 m.
U15 = {"birth_year": 2012, "gender": "jongens", "year": 2026, "rules": RULES}
# Geboortejaar 2010 in 2026 = 16 jaar = U17 Nieuweling jongens, maximaal toegestaan verzet 7.68 m.
U17 = {**U15, "birth_year": 2010}
TIRE = {"tire_width_mm": 28, "rim_diameter_mm": 622}
CIRCUMFERENCE = Wheel(28, 622).circumference_mm


def _advise(**kwargs) -> VerzetAdvies:
    result = advise(**{"largest_sprocket": 28, **U15, **TIRE, **kwargs})
    assert isinstance(result, VerzetAdvies), result
    return result


def test_wheel_circumference_follows_etrto_formula():
    assert CIRCUMFERENCE == pytest.approx(math.pi * 678)


def test_over_limit_current_setup_with_all_three_proposals():
    result = _advise(chainring=50, smallest_sprocket=11)

    assert result.category == "U15"
    assert result.limit_m == 6.7
    assert result.source == knwu_categories.sources(RULES).gearing
    assert not result.current.within_limit
    assert result.current.heaviest_gear_m == 9.68
    assert result.current.range_percent == 255
    assert result.current.top_speed_kmh == 58.1
    assert result.smallest_sprocket_proposal is not None
    assert result.smallest_sprocket_proposal.setup.smallest_sprocket == 16
    assert result.largest_chainring_proposal is not None
    assert result.largest_chainring_proposal.setup.chainring == 34
    assert [p.setup.smallest_sprocket for p in result.regular_cassette_proposals] == [11]


def test_limit_is_inclusive_without_margin():
    rules = copy.deepcopy(RULES)
    exact = verzet_advies.gear_m(34, 11, CIRCUMFERENCE)
    rules["verzetten"]["per_geslacht"]["jongens"]["U15"]["weg"] = exact

    result = _advise(chainring=34, smallest_sprocket=11, rules=rules)

    assert result.current.within_limit


def test_regular_cassette_adds_12t_only_when_closer_to_limit():
    # U17 1x: 11T -> 38T (7.36 m), 12T -> 42T (7.45 m) ligt dichter bij 7.68 m.
    result = _advise(chainring=50, smallest_sprocket=11, **U17)

    first, second = result.regular_cassette_proposals
    assert (first.setup.chainring, first.setup.smallest_sprocket) == (38, 11)
    assert (second.setup.chainring, second.setup.smallest_sprocket) == (42, 12)


def test_single_chainring_proposals_have_even_teeth_and_never_17t_or_more():
    result = _advise(chainring=51, smallest_sprocket=11)

    proposals = [result.largest_chainring_proposal, *result.regular_cassette_proposals]
    for proposal in proposals:
        assert proposal is not None
        assert proposal.setup.chainring % 2 == 0
        assert proposal.setup.smallest_sprocket < 17


def test_smallest_sprocket_proposal_missing_when_17t_or_more_needed():
    result = _advise(chainring=60, smallest_sprocket=11)

    assert result.smallest_sprocket_proposal is None


def test_double_chainring_becomes_1x_when_allowed_ring_drops_below_small_ring():
    # U14 jongens (6.30 m): bij 11T past maximaal 32T, kleiner dan het kleine blad van 34T.
    u14 = {**U15, "birth_year": 2013}
    result = _advise(chainring=50, small_chainring=34, smallest_sprocket=11, **u14)

    proposal = result.largest_chainring_proposal
    assert proposal is not None
    assert proposal.setup.small_chainring is None
    assert proposal.setup.chainring % 2 == 0
    assert proposal.within_limit


@pytest.mark.parametrize(
    "setup, too_light",
    [
        # Bij 12T is 36T het grootste 1x-blad; een stap is 2 tanden.
        ({"chainring": 32, "smallest_sprocket": 12}, True),
        ({"chainring": 34, "smallest_sprocket": 12}, False),
        # 34T past al vanaf 11T; op 14T zit je drie kransjes onder het maximaal toegestane verzet.
        ({"chainring": 34, "smallest_sprocket": 14}, True),
    ],
)
def test_too_light_when_more_than_one_step_below_limit(setup, too_light):
    result = _advise(**setup)

    assert result.current.within_limit
    assert result.too_light is too_light


def test_two_chainrings_use_small_one_for_lightest_gear():
    result = _advise(chainring=50, small_chainring=34, smallest_sprocket=14)

    assert result.current.lightest_gear_m == round(verzet_advies.gear_m(34, 28, CIRCUMFERENCE), 2)


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"smallest_sprocket": 8}, "kleinste tandkransje"),
        ({"smallest_sprocket": 17}, "kleinste tandkransje"),
        ({"largest_sprocket": 22}, "grootste tandkransje"),
        ({"largest_sprocket": 60}, "grootste tandkransje"),
        ({"chainring": 31}, "voorblad"),
        ({"chainring": 61}, "voorblad"),
        ({"tire_width_mm": 22}, "banddikte"),
        ({"tire_width_mm": 41}, "banddikte"),
        ({"rim_diameter_mm": 600}, "velgdiameter"),
        ({"small_chainring": 52}, "kleine voorblad"),
        ({"birth_year": 1990}, "1990"),
    ],
)
def test_invalid_input_returns_error_result(overrides, fragment):
    args = {"chainring": 50, "smallest_sprocket": 11, "largest_sprocket": 28, **U15, **TIRE}

    result = advise(**{**args, **overrides})

    assert isinstance(result, InvalidInput)
    assert fragment in result.message
