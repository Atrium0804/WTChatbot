"""Deterministische rekenmodule voor het verzetadvies (issue #148, ADR-0010).

Pure functies zonder netwerk: wielomtrek uit de ETRTO-maat, zwaarste en
lichtste verzet, bereik, topsnelheid en drie berekeningen die een aanpassing
voorstellen. Het maximaal toegestane verzet komt uit knwu_categories.json (art. 20.1.007), alleen
voor wegwielrennen. Ongeldige invoer geeft een InvalidInput als resultaat.
"""

import math
from dataclasses import dataclass, replace

import knwu_categories
from knwu_categories import Gender, SourceFact

RIM_DIAMETERS_MM = (406, 507, 520, 540, 559, 584, 622)
SMALLEST_SPROCKET_RANGE = (9, 16)
LARGEST_SPROCKET_RANGE = (23, 59)
CHAINRING_RANGE = (32, 60)
TIRE_WIDTH_RANGE_MM = (23, 40)
REGULAR_CASSETTE_SPROCKETS = (11, 12)
FIRST_NON_PROPOSABLE_SPROCKET = 17
RPM_FOR_TOP_SPEED = 100


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
class SetupResult:
    setup: Setup
    heaviest_gear_m: float
    lightest_gear_m: float
    range_percent: int
    top_speed_kmh: float
    within_limit: bool


@dataclass(frozen=True)
class VerzetAdvies:
    category: str
    limit_m: float
    source: SourceFact
    wheel_circumference_mm: float
    current: SetupResult
    too_light: bool
    smallest_sprocket_proposal: SetupResult | None
    largest_chainring_proposal: SetupResult | None
    regular_cassette_proposals: tuple[SetupResult, ...]


@dataclass(frozen=True)
class InvalidInput:
    message: str


def gear_m(chainring: int, sprocket: int, circumference_mm: float) -> float:
    """Verzet in meters per pedaalomwenteling."""
    if sprocket <= 0:
        raise ValueError(f"sprocket must be > 0, got {sprocket}")
    return circumference_mm * chainring / sprocket / 1000


def _evaluate(setup: Setup, limit: Limit) -> SetupResult:
    """Zwaarste en lichtste verzet, bereik, topsnelheid en grenscontrole van een configuratie."""
    heaviest = limit.gear_m(setup.chainring, setup.smallest_sprocket)
    lightest = limit.gear_m(setup.small_chainring or setup.chainring, setup.largest_sprocket)
    return SetupResult(
        setup=setup,
        heaviest_gear_m=round(heaviest, 2),
        lightest_gear_m=round(lightest, 2),
        range_percent=round(heaviest / lightest * 100),
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


def _chainring_proposal(
    current: Setup, sprocket: int, limit: Limit, step: int
) -> SetupResult | None:
    """Grootste toegestane blad (veelvoud van `step`) bij `sprocket`; zakt het onder het kleine blad, dan 1x."""
    chainring = _largest_allowed_chainring(step, sprocket, limit)
    small_chainring = current.small_chainring
    if small_chainring is not None and chainring <= small_chainring:
        small_chainring = None
        chainring = _largest_allowed_chainring(2, sprocket, limit)
    if chainring < CHAINRING_RANGE[0]:
        return None
    setup = replace(
        current, chainring=chainring, small_chainring=small_chainring, smallest_sprocket=sprocket
    )
    return _evaluate(setup, limit)


def _sprocket_proposal(current: Setup, limit: Limit) -> SetupResult | None:
    """Kleinste toegestaan kransje bij het huidige blad; nooit 17T of groter."""
    sprocket = _smallest_allowed_sprocket(current.chainring, limit)
    if sprocket >= FIRST_NON_PROPOSABLE_SPROCKET:
        return None
    sprocket = max(sprocket, SMALLEST_SPROCKET_RANGE[0])
    setup = replace(
        current,
        smallest_sprocket=sprocket,
        largest_sprocket=max(current.largest_sprocket, sprocket),
    )
    return _evaluate(setup, limit)


def _regular_cassette_proposals(current: Setup, limit: Limit) -> tuple[SetupResult, ...]:
    """11T heeft voorkeur; 12T alleen als die dichter bij het maximaal toegestane verzet uitkomt.
    Het blad heeft altijd een even aantal tanden, ook bij twee bladen (#147)."""
    proposals: list[SetupResult] = []
    for sprocket in REGULAR_CASSETTE_SPROCKETS:
        candidate = _chainring_proposal(current, sprocket, limit, step=2)
        if candidate is None:
            continue
        if proposals and candidate.heaviest_gear_m <= proposals[0].heaviest_gear_m:
            continue
        proposals.append(candidate)
    return tuple(proposals)


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
        ("voorblad", setup.chainring, CHAINRING_RANGE, "T"),
        ("banddikte", wheel.tire_width_mm, TIRE_WIDTH_RANGE_MM, " mm"),
    ]
    if setup.small_chainring is not None:
        checks.append(("klein voorblad", setup.small_chainring, CHAINRING_RANGE, "T"))
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
            f"Het kleine voorblad ({setup.small_chainring}T) kan niet groter zijn dan "
            f"het grote voorblad ({setup.chainring}T)."
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
    """Controleer het verzet van een fiets tegen de wegwedstrijdgrens en stel aanpassingen voor.

    `chainring` is het grootste voorblad, `small_chainring` het kleine bij twee
    bladen (None = 1x). `year` is het wedstrijdjaar.
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
        smallest_sprocket_proposal=_sprocket_proposal(setup, limit),
        largest_chainring_proposal=_chainring_proposal(
            setup, smallest_sprocket, limit, step=setup.chainring_step
        ),
        regular_cassette_proposals=_regular_cassette_proposals(setup, limit),
    )
