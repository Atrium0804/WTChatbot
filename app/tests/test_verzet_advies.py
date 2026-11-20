"""Tests voor de verzetadvies-rekenmodule (#148) — offline, pure functies."""

import copy
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knwu_categories  # noqa: E402
import verzet_advies  # noqa: E402
from verzet_advies import (  # noqa: E402
    Advice,
    CassetteRange,
    InvalidInput,
    VerzetAdvies,
    Wheel,
    advise,
)

RULES = knwu_categories.load_rules()
# Geboortejaar 2012 in 2026 = 14 jaar = U15 jongens, maximaal toegestaan verzet 6.70 m.
U15 = {"birth_year": 2012, "gender": "jongens", "year": 2026, "rules": RULES}
# Geboortejaar 2010 in 2026 = 16 jaar = U17 Nieuweling jongens, maximaal toegestaan verzet 7.68 m.
U17 = {**U15, "birth_year": 2010}
# Geboortejaar 2015 in 2026 = 11 jaar = U12 jongens, maximaal toegestaan verzet 5.90 m.
U12 = {**U15, "birth_year": 2015}
TIRE = {"tire_width_mm": 28, "rim_diameter_mm": 622}
CIRCUMFERENCE = Wheel(28, 622).circumference_mm


def _advise(**kwargs) -> VerzetAdvies:
    result = advise(**{"largest_sprocket": 28, **U15, **TIRE, **kwargs})
    assert isinstance(result, VerzetAdvies), result
    return result


def test_wheel_circumference_follows_etrto_formula():
    assert CIRCUMFERENCE == pytest.approx(math.pi * 678)


def test_over_limit_current_setup_is_evaluated():
    result = _advise(chainring=50, smallest_sprocket=11)

    assert result.category == "U15"
    assert result.limit_m == 6.7
    assert result.source == knwu_categories.sources(RULES).gearing
    assert not result.current.within_limit
    assert result.current.heaviest_gear_m == 9.68
    assert result.current.range_percent == 255
    assert result.current.top_speed_kmh == 58.1


def test_limit_is_inclusive_without_margin():
    rules = copy.deepcopy(RULES)
    exact = verzet_advies.gear_m(34, 11, CIRCUMFERENCE)
    rules["verzetten"]["per_geslacht"]["jongens"]["U15"]["weg"] = exact

    result = _advise(chainring=34, smallest_sprocket=11, rules=rules)

    assert result.current.within_limit


def _gears(advice: Advice | None) -> tuple[int, int | None, int] | None:
    """(kettingblad, binnenblad, kleinste kransje) van een advies."""
    if advice is None:
        return None
    setup = advice.result.setup
    return setup.chainring, setup.small_chainring, setup.smallest_sprocket


@pytest.mark.parametrize(
    "chainrings, smallest_sprocket, expected",
    [
        # Buitenblad wordt 38T; cassetteadvies op het binnenblad (50T past bij geen kransje);
        # het reguliere-cassetteadvies 30/11 (5.81 m) ligt dichter bij 5.9 m dan 32/12 (5.68 m).
        ((50, 34), 14, [(38, 34, 14), (34, None, 13), (30, None, 11)]),
        # Het cassetteadvies heeft al 12T: geen reguliere-cassetteadvies.
        ((50, 32), 14, [(38, 32, 14), (32, None, 12), None]),
        ((32, None), 14, [(38, None, 14), (32, None, 12), None]),
        # Bij 11T past maximaal 30T, kleiner dan het binnenblad: beide bladen worden één 30T-blad
        # bij de huidige cassette. Alleen het kettingblad verandert, dus advies 1.
        ((50, 39), 11, [(30, None, 11), (39, None, 15), None]),
        # 50/40: zelfde patroon; het binnenblad wordt bij advies 2 het enige blad.
        ((50, 40), 11, [(30, None, 11), (40, None, 15), None]),
    ],
)
def test_u12_examples(chainrings, smallest_sprocket, expected):
    chainring, small_chainring = chainrings
    result = _advise(
        chainring=chainring,
        small_chainring=small_chainring,
        smallest_sprocket=smallest_sprocket,
        **U12,
    )

    advices = [result.advice(1), result.advice(2), result.advice(3)]
    assert [_gears(a) for a in advices] == expected
    assert all(a.result.within_limit for a in advices if a is not None)


def test_chainring_advice_marks_what_changes():
    result = _advise(chainring=50, small_chainring=34, smallest_sprocket=14, **U12)

    chainring_advice = result.advice(1)
    assert chainring_advice is not None
    assert (chainring_advice.chainring_status, chainring_advice.cassette_status) == (
        "aangepast",
        "huidig",
    )
    assert not chainring_advice.removes_outer_chainring
    assert chainring_advice.title == "Kettingblad aanpassen"
    cassette_advice = result.advice(2)
    assert cassette_advice is not None
    assert (cassette_advice.chainring_status, cassette_advice.cassette_status) == (
        "binnenblad",
        "aangepast",
    )
    assert cassette_advice.removes_outer_chainring
    assert cassette_advice.title == "Cassette wijzigen"
    # 14T -> 13T: mogelijk volstaat het vervangen van alleen het kleinste kransje.
    assert cassette_advice.single_sprocket_swap
    regular = result.advice(3)
    assert regular is not None
    assert (regular.chainring_status, regular.cassette_status) == ("aangepast", "aangepast")
    assert regular.title == "Cassette en kettingblad (1x) wijzigen"
    assert regular.replaces_both_chainrings


def test_double_chainring_becomes_1x_on_inner_ring_when_it_is_exactly_the_largest_allowed():
    # U12 (5.9 m): bij 13T past maximaal 36T, precies het binnenblad.
    result = _advise(chainring=50, small_chainring=36, smallest_sprocket=13, **U12)

    advice = result.advice(1)
    assert advice is not None
    assert _gears(advice) == (36, None, 13)
    assert advice.chainring_status == "binnenblad"


def test_cassette_advice_keeps_both_chainrings_when_the_outer_ring_fits():
    # U17 (7.68 m): 50T past bij 14T.
    result = _advise(chainring=50, small_chainring=34, smallest_sprocket=11, **U17)

    assert _gears(result.advice(2)) == (50, 34, 14)


def test_cassette_advice_missing_when_no_valid_sprocket_fits():
    result = _advise(chainring=60, smallest_sprocket=11)

    assert result.advice(2) is None


def test_never_advises_a_new_chainring_below_30t():
    # U8 (5.5 m): bij 11T past maximaal 28T; bij 12T 30T.
    result = _advise(chainring=40, smallest_sprocket=11, **{**U15, "birth_year": 2019})

    assert result.advice(1) is None
    assert _gears(result.advice(3)) == (30, None, 12)


def test_advice_equal_to_current_setup_is_dropped():
    # U17 (7.68 m): 42/12 is al het grootste even blad bij 12T en 12T het kleinste kransje.
    result = _advise(chainring=42, smallest_sprocket=12, **U17)

    assert result.advices == ()


def test_both_chainrings_replaced_by_one_is_advice_1_when_the_cassette_stays():
    # U12 50/40 met 11-25: bij 11T past maximaal 30T, kleiner dan het binnenblad. 30T met de
    # huidige 11-25 verandert alleen het kettingblad: advies 1, geen advies 3.
    result = _advise(
        chainring=50, small_chainring=40, smallest_sprocket=11, largest_sprocket=25, **U12
    )

    assert [(a.number, a.title) for a in result.advices] == [
        (1, "Kettingblad aanpassen"),
        (2, "Cassette wijzigen"),
    ]
    chainring_advice = result.advices[0]
    assert _gears(chainring_advice) == (30, None, 11)
    assert chainring_advice.replaces_both_chainrings
    assert not chainring_advice.removes_outer_chainring


def test_larger_chainring_warns_that_the_chain_may_be_too_short():
    result = _advise(chainring=32, smallest_sprocket=14, **U12)

    chainring_advice, cassette_advice = result.advice(1), result.advice(2)
    assert result.too_light
    assert chainring_advice is not None
    assert chainring_advice.chain_may_be_too_short
    assert cassette_advice is not None
    assert not cassette_advice.chain_may_be_too_short


def test_every_result_gives_its_own_cassette_with_a_34t_largest_sprocket():
    # U12 (5.9 m), 50/40 met 11-25: het cassetteadvies is 40T met 15-25 (40/15 -> 40/25 = 167%);
    # met 15-34 wordt dat 34/15 = 227%. Advies 1 (30T met 11-25) krijgt 11-34.
    result = _advise(
        chainring=50, small_chainring=40, smallest_sprocket=11, largest_sprocket=25, **U12
    )

    cassette_advice = result.advice(2)
    assert cassette_advice is not None
    assert cassette_advice.result.range_percent == 167
    assert cassette_advice.result.with_34t == CassetteRange(
        "15-34",
        227,
        "Met een 15-34 in plaats van een 15-25 wordt het bereik 227% in plaats van 167%; "
        "het zwaarste verzet blijft gelijk.",
    )
    chainring_advice = result.advice(1)
    assert chainring_advice is not None
    with_34t = chainring_advice.result.with_34t
    assert with_34t is not None
    assert (with_34t.cassette, with_34t.range_percent) == ("11-34", 309)
    # Twee bladen: het lichtste verzet met 34T komt van het binnenblad (50/11 -> 40/34).
    current_with_34t = result.current.with_34t
    assert current_with_34t is not None
    assert (current_with_34t.cassette, current_with_34t.range_percent) == ("11-34", 386)


def test_no_34t_cassette_when_the_largest_sprocket_is_already_34t_or_more():
    result = _advise(chainring=50, smallest_sprocket=11, largest_sprocket=36)

    assert result.current.with_34t is None


def test_single_chainring_advices_have_even_teeth():
    result = _advise(chainring=51, smallest_sprocket=13)

    for advice in (result.advice(1), result.advice(3)):
        assert advice is not None
        assert advice.result.setup.chainring % 2 == 0


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
        ({"chainring": 27}, "kettingblad"),
        ({"chainring": 61}, "kettingblad"),
        ({"tire_width_mm": 22}, "banddikte"),
        ({"tire_width_mm": 41}, "banddikte"),
        ({"rim_diameter_mm": 600}, "velgdiameter"),
        ({"small_chainring": 52}, "binnenblad"),
        ({"birth_year": 1990}, "1990"),
    ],
)
def test_invalid_input_returns_error_result(overrides, fragment):
    args = {"chainring": 50, "smallest_sprocket": 11, "largest_sprocket": 28, **U15, **TIRE}

    result = advise(**{**args, **overrides})

    assert isinstance(result, InvalidInput)
    assert fragment in result.message
