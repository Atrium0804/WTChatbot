"""Deterministische rekenmodule voor het verzetadvies (issue #148, ADR-0010).

Pure functies zonder netwerk: wielomtrek uit de ETRTO-maat, zwaarste en
lichtste verzet, bereik, topsnelheid en drie adviezen (kettingbladadvies,
cassetteadvies, reguliere-cassetteadvies; zie GLOSSARY.md). Het maximaal toegestane verzet komt
uit knwu_categories.json (art. 20.1.007), alleen voor wegwielrennen. Ongeldige invoer geeft een
InvalidInput als resultaat.
"""

import math
from dataclasses import dataclass, replace
from typing import Literal

import knwu_categories
from knwu_categories import Gender, SourceFact

RIM_DIAMETERS_MM = (406, 507, 520, 540, 559, 584, 622)
SMALLEST_SPROCKET_RANGE = (9, 16)
LARGEST_SPROCKET_RANGE = (23, 59)
CHAINRING_RANGE = (28, 60)
TIRE_WIDTH_RANGE_MM = (23, 40)
# Kleinste tandkransjes waarop een cassetteadvies mag uitkomen (de optimale configuraties).
VALID_SPROCKETS = (11, 12, 13, 14, 15, 16)
REGULAR_CASSETTE_SPROCKETS = (11, 12)
# Een nieuw kettingblad adviseren we nooit kleiner; als invoer mag een kleiner blad wel.
MIN_ADVISED_CHAINRING = 30
RPM_FOR_TOP_SPEED = 100
# Cassettes tot 34T passen meestal zonder problemen op de achterderailleur.
COMMON_LARGEST_SPROCKET = 34
ADVICE_TITLES = {
    1: "Kettingblad aanpassen",
    2: "Cassette wijzigen",
    3: "Cassette en kettingblad (1x) wijzigen",
}


@dataclass(frozen=True)
class Setup:
    """Een fietsconfiguratie; `small_chainring` is None bij één kettingblad (1x)."""

    chainring: int
    small_chainring: int | None
    smallest_sprocket: int
    largest_sprocket: int

    @property
    def chainring_step(self) -> int:
        """Een 1x-kettingblad heeft een even aantal tanden, dus de stap is 2."""
        return 2 if self.small_chainring is None else 1


@dataclass(frozen=True)
class Wheel:
    tire_width_mm: int
    rim_diameter_mm: int

    @property
    def circumference_mm(self) -> float:
        """Wielomtrek = pi x (velgdiameter + 2 x banddikte) uit de ETRTO-maat."""
        return math.pi * (self.rim_diameter_mm + 2 * self.tire_width_mm)


@dataclass(frozen=True)
class Limit:
    """Het maximaal toegestane verzet voor een omtrek; een gelijk verzet is toegestaan (<=)."""

    circumference_mm: float
    max_gear_m: float

    def gear_m(self, chainring: int, sprocket: int) -> float:
        """Verzet in meters bij deze omtrek voor de combinatie blad/kransje."""
        return gear_m(chainring, sprocket, self.circumference_mm)

    def allows(self, chainring: int, sprocket: int) -> bool:
        """True als de combinatie blad/kransje binnen het maximaal toegestane verzet valt."""
        return self.gear_m(chainring, sprocket) <= self.max_gear_m


@dataclass(frozen=True)
class CassetteRange:
    """Een cassette als tekst (bv. "15-34") met het bereik dat de configuratie daarmee krijgt,
    en `tip`: de zin die de agent letterlijk overneemt."""

    cassette: str
    range_percent: int
    tip: str


@dataclass(frozen=True)
class SetupResult:
    setup: Setup
    heaviest_gear_m: float
    lightest_gear_m: float
    range_percent: int
    # None als het grootste kransje al 34T of groter is.
    with_34t: CassetteRange | None
    top_speed_kmh: float
    within_limit: bool


@dataclass(frozen=True)
class Advice:
    """Een geadviseerde configuratie met wat er verandert ten opzichte van de huidige.

    `number` en `title` volgen uit wat er verandert (zie ADVICE_TITLES). `chainring_status` is
    "binnenblad" als het huidige binnenblad het enige kettingblad wordt
    (`removes_outer_chainring`); `replaces_both_chainrings`: twee bladen worden één nieuw
    kettingblad. `single_sprocket_swap`: het kleinste kransje wijkt 1 tand af, dus mogelijk
    volstaat het vervangen van dat ene kransje. `chain_may_be_too_short`: grootste blad +
    grootste kransje is groter dan nu, dus de ketting moet mogelijk langer.
    """

    number: int
    title: str
    result: SetupResult
    chainring_status: Literal["huidig", "aangepast", "binnenblad"]
    cassette_status: Literal["huidig", "aangepast"]
    removes_outer_chainring: bool
    replaces_both_chainrings: bool
    single_sprocket_swap: bool
    chain_may_be_too_short: bool


@dataclass(frozen=True)
class VerzetAdvies:
    """`advices` bevat alleen de adviezen die gelden, op volgorde van `number`."""

    category: str
    limit_m: float
    source: SourceFact
    wheel_circumference_mm: float
    current: SetupResult
    too_light: bool
    advices: tuple[Advice, ...]

    def advice(self, number: int) -> Advice | None:
        return next((a for a in self.advices if a.number == number), None)


@dataclass(frozen=True)
class InvalidInput:
    message: str


def gear_m(chainring: int, sprocket: int, circumference_mm: float) -> float:
    """Verzet in meters per pedaalomwenteling."""
    if sprocket <= 0:
        raise ValueError(f"sprocket must be > 0, got {sprocket}")
    return circumference_mm * chainring / sprocket / 1000


def _with_34t(
    setup: Setup, heaviest: float, range_percent: int, limit: Limit
) -> CassetteRange | None:
    """Dezelfde configuratie met een 34T als grootste kransje, als indicatie van het bereik."""
    if setup.largest_sprocket >= COMMON_LARGEST_SPROCKET:
        return None
    lightest = limit.gear_m(setup.small_chainring or setup.chainring, COMMON_LARGEST_SPROCKET)
    cassette = f"{setup.smallest_sprocket}-{COMMON_LARGEST_SPROCKET}"
    range_with_34t = round(heaviest / lightest * 100)
    current_cassette = f"{setup.smallest_sprocket}-{setup.largest_sprocket}"
    return CassetteRange(
        cassette=cassette,
        range_percent=range_with_34t,
        tip=(
            f"Met een {cassette} in plaats van een {current_cassette} wordt het bereik "
            f"{range_with_34t}% in plaats van {range_percent}%; het zwaarste verzet blijft gelijk."
        ),
    )


def _evaluate(setup: Setup, limit: Limit) -> SetupResult:
    """Zwaarste en lichtste verzet, bereik, topsnelheid en grenscontrole van een configuratie."""
    heaviest = limit.gear_m(setup.chainring, setup.smallest_sprocket)
    lightest = limit.gear_m(setup.small_chainring or setup.chainring, setup.largest_sprocket)
    range_percent = round(heaviest / lightest * 100)
    return SetupResult(
        setup=setup,
        heaviest_gear_m=round(heaviest, 2),
        lightest_gear_m=round(lightest, 2),
        range_percent=range_percent,
        with_34t=_with_34t(setup, heaviest, range_percent, limit),
        top_speed_kmh=round(heaviest * RPM_FOR_TOP_SPEED * 60 / 1000, 1),
        within_limit=limit.allows(setup.chainring, setup.smallest_sprocket),
    )


def _largest_allowed_chainring(step: int, sprocket: int, limit: Limit) -> int:
    """Grootste toegestane blad bij `sprocket`, afgerond op een veelvoud van `step`."""
    chainring = math.floor(limit.max_gear_m * 1000 * sprocket / limit.circumference_mm)
    chainring -= chainring % step
    while chainring > 0 and not limit.allows(chainring, sprocket):
        chainring -= step
    return chainring


def _smallest_allowed_sprocket(chainring: int, limit: Limit) -> int:
    """Kleinste kransje (minimaal 1T) waarmee `chainring` binnen de grens blijft."""
    sprocket = max(math.ceil(limit.circumference_mm * chainring / (limit.max_gear_m * 1000)), 1)
    while not limit.allows(chainring, sprocket):
        sprocket += 1
    return sprocket


def _chainring_advice(current: Setup, limit: Limit) -> Setup | None:
    """Kettingbladadvies: grootste toegestane blad bij het huidige kleinste kransje.

    1x: even aantal tanden. Twee bladen: het binnenblad blijft altijd. Een groter blad dan het
    binnenblad wordt het nieuwe buitenblad; is het precies het binnenblad, dan gaat het
    buitenblad eraf. Is het kleiner, dan zou geen van beide bladen blijven: geen advies hier;
    het reguliere-cassetteadvies (1x) vangt dat op.
    """
    sprocket = current.smallest_sprocket
    inner = current.small_chainring
    if inner is None:
        chainring = _largest_allowed_chainring(2, sprocket, limit)
        if chainring != current.chainring and chainring < MIN_ADVISED_CHAINRING:
            return None
        return replace(current, chainring=chainring)
    optimal = _largest_allowed_chainring(1, sprocket, limit)
    if optimal > inner:
        if optimal < MIN_ADVISED_CHAINRING:
            return None
        return replace(current, chainring=optimal)
    if optimal == inner:
        return replace(current, chainring=inner, small_chainring=None)
    return None


def _cassette_advice(current: Setup, limit: Limit) -> Setup | None:
    """Cassetteadvies: kleinste geldige kransje bij het huidige blad.

    Bij twee bladen eerst met het buitenblad; past dat bij geen enkel geldig kransje, dan
    met het binnenblad zonder buitenblad.
    """
    candidates = [(current.chainring, current.small_chainring)]
    if current.small_chainring is not None:
        candidates.append((current.small_chainring, None))
    for chainring, small_chainring in candidates:
        for sprocket in VALID_SPROCKETS:
            if limit.allows(chainring, sprocket):
                return replace(
                    current,
                    chainring=chainring,
                    small_chainring=small_chainring,
                    smallest_sprocket=sprocket,
                )
    return None


def _regular_cassette_advice(current: Setup, limit: Limit) -> Setup | None:
    """Reguliere-cassetteadvies: 1x met 11T of 12T en een even blad van minstens 30T,
    het dichtst bij het maximaal toegestane verzet; bij gelijke stand 11T."""
    candidates = []
    for sprocket in REGULAR_CASSETTE_SPROCKETS:
        chainring = _largest_allowed_chainring(2, sprocket, limit)
        if chainring >= MIN_ADVISED_CHAINRING:
            candidates.append(
                replace(current, chainring=chainring, small_chainring=None, smallest_sprocket=sprocket)
            )
    if not candidates:
        return None
    return max(candidates, key=lambda setup: limit.gear_m(setup.chainring, setup.smallest_sprocket))


def _chainring_status(advised: Setup, current: Setup) -> Literal["huidig", "aangepast", "binnenblad"]:
    if (advised.chainring, advised.small_chainring) == (current.chainring, current.small_chainring):
        return "huidig"
    if advised.small_chainring is None and advised.chainring == current.small_chainring:
        return "binnenblad"
    return "aangepast"


def _advice_number(
    chainring_status: Literal["huidig", "aangepast", "binnenblad"], cassette_changed: bool
) -> int | None:
    """1: alleen het kettingblad verandert; 2: alleen de cassette (het kettingblad blijft, of
    alleen het binnenblad); 3: allebei. None als er niets verandert."""
    if not cassette_changed:
        return None if chainring_status == "huidig" else 1
    return 3 if chainring_status == "aangepast" else 2


def _advice(advised: Setup, current: Setup, limit: Limit) -> Advice | None:
    sprocket_change = abs(advised.smallest_sprocket - current.smallest_sprocket)
    cassette_changed = sprocket_change > 0 or advised.largest_sprocket != current.largest_sprocket
    chainring_status = _chainring_status(advised, current)
    number = _advice_number(chainring_status, cassette_changed)
    if number is None:
        return None
    to_1x = current.small_chainring is not None and advised.small_chainring is None
    return Advice(
        number=number,
        title=ADVICE_TITLES[number],
        result=_evaluate(advised, limit),
        chainring_status=chainring_status,
        cassette_status="aangepast" if cassette_changed else "huidig",
        removes_outer_chainring=to_1x and chainring_status == "binnenblad",
        replaces_both_chainrings=to_1x and chainring_status == "aangepast",
        single_sprocket_swap=sprocket_change == 1,
        chain_may_be_too_short=advised.chainring + advised.largest_sprocket
        > current.chainring + current.largest_sprocket,
    )


def _advices(current: Setup, limit: Limit) -> tuple[Advice, ...]:
    """Adviezen uit drie berekeningen: kettingbladadvies, cassetteadvies en
    reguliere-cassetteadvies. Het reguliere-cassetteadvies vervalt als een van de eerste twee al
    een reguliere cassette heeft. Nummer en titel volgen uit wat er verandert (_advice_number);
    een advies gelijk aan de huidige configuratie, of met hetzelfde nummer of dezelfde
    configuratie als een eerder advies, vervalt."""
    chainring_setup = _chainring_advice(current, limit)
    cassette_setup = _cassette_advice(current, limit)
    regular_setup = _regular_cassette_advice(current, limit)
    if any(
        setup is not None and setup.smallest_sprocket in REGULAR_CASSETTE_SPROCKETS
        for setup in (chainring_setup, cassette_setup)
    ):
        regular_setup = None

    advices: dict[int, Advice] = {}
    seen = {current}
    for setup in (chainring_setup, cassette_setup, regular_setup):
        if setup is None or setup in seen:
            continue
        advice = _advice(setup, current, limit)
        if advice is None or advice.number in advices:
            continue
        seen.add(setup)
        advices[advice.number] = advice
    return tuple(advices[number] for number in sorted(advices))


def _is_too_light(current: Setup, limit: Limit) -> bool:
    """Ruim te licht: meer dan een stap (blad of kransje) onder het maximaal toegestane verzet."""
    if not limit.allows(current.chainring, current.smallest_sprocket):
        return False
    chainring_room = (
        _largest_allowed_chainring(current.chainring_step, current.smallest_sprocket, limit)
        - current.chainring
    )
    sprocket_room = current.smallest_sprocket - _smallest_allowed_sprocket(
        current.chainring, limit
    )
    return chainring_room > current.chainring_step or sprocket_room > 1


def _validate(setup: Setup, wheel: Wheel) -> str | None:
    """Foutmelding voor de eerste ongeldige invoer, of None als alles klopt."""
    checks = [
        ("kleinste tandkransje", setup.smallest_sprocket, SMALLEST_SPROCKET_RANGE, "T"),
        ("grootste tandkransje", setup.largest_sprocket, LARGEST_SPROCKET_RANGE, "T"),
        ("kettingblad", setup.chainring, CHAINRING_RANGE, "T"),
        ("banddikte", wheel.tire_width_mm, TIRE_WIDTH_RANGE_MM, " mm"),
    ]
    if setup.small_chainring is not None:
        checks.append(("binnenblad", setup.small_chainring, CHAINRING_RANGE, "T"))
    for name, value, (low, high), unit in checks:
        if not low <= value <= high:
            return f"Het {name} moet tussen {low} en {high}{unit} liggen, niet {value}{unit}."
    if wheel.rim_diameter_mm not in RIM_DIAMETERS_MM:
        options = ", ".join(str(d) for d in RIM_DIAMETERS_MM)
        return f"De velgdiameter moet een van {options} mm zijn, niet {wheel.rim_diameter_mm} mm."
    # Met de huidige bereiken onbereikbaar; blijft staan als de bereiken ooit veranderen.
    if setup.largest_sprocket < setup.smallest_sprocket:
        return (
            f"Het grootste tandkransje ({setup.largest_sprocket}T) kan niet kleiner zijn dan "
            f"het kleinste ({setup.smallest_sprocket}T)."
        )
    if setup.small_chainring is not None and setup.small_chainring > setup.chainring:
        return (
            f"Het binnenblad ({setup.small_chainring}T) kan niet groter zijn dan "
            f"het buitenblad ({setup.chainring}T)."
        )
    return None


def _road_limit(
    birth_year: int, gender: Gender, year: int, rules: dict
) -> tuple[str, float] | InvalidInput:
    """Leeftijdscategorie en maximaal toegestaan wegverzet, of InvalidInput als die ontbreken."""
    category = knwu_categories.age_category(birth_year, year, rules)
    if category is None:
        return InvalidInput(
            f"Geboortejaar {birth_year} valt in {year} buiten de jeugdcategorieën "
            "(U6 t/m U17); er is geen maximaal toegestaan verzet."
        )
    try:
        limit = knwu_categories.max_gear(category, "weg", gender, rules)
    except ValueError as exc:
        return InvalidInput(str(exc))
    if not isinstance(limit, float | int):
        return InvalidInput(
            f"Voor {category} ({gender}) is geen maximaal verzet voor weg vastgelegd."
        )
    return category, float(limit)


def advise(
    *,
    birth_year: int,
    gender: Gender,
    year: int,
    chainring: int,
    smallest_sprocket: int,
    largest_sprocket: int,
    tire_width_mm: int,
    rim_diameter_mm: int,
    rules: dict,
    small_chainring: int | None = None,
) -> VerzetAdvies | InvalidInput:
    """Controleer het verzet van een fiets tegen de wegwedstrijdgrens en adviseer aanpassingen.

    `chainring` is het buitenblad (of het enige kettingblad), `small_chainring` het binnenblad
    bij twee bladen (None = 1x). `year` is het wedstrijdjaar.
    """
    setup = Setup(chainring, small_chainring, smallest_sprocket, largest_sprocket)
    wheel = Wheel(tire_width_mm, rim_diameter_mm)
    error = _validate(setup, wheel)
    if error:
        return InvalidInput(error)

    road_limit = _road_limit(birth_year, gender, year, rules)
    if isinstance(road_limit, InvalidInput):
        return road_limit
    category, max_gear_m = road_limit

    limit = Limit(wheel.circumference_mm, max_gear_m)
    return VerzetAdvies(
        category=category,
        limit_m=max_gear_m,
        source=knwu_categories.sources(rules).gearing,
        wheel_circumference_mm=round(wheel.circumference_mm, 1),
        current=_evaluate(setup, limit),
        too_light=_is_too_light(setup, limit),
        advices=_advices(setup, limit),
    )
