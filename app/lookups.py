"""Deterministische lookup-antwoorden (#91; data uit #94; overzicht #102).

Pure feitelijke lookup-vragen — leeftijdscategorie, licentie, maximaal
verzet per discipline, oude categorie-indeling — beantwoordt de app zelf
met een gecombineerd overzicht uit knwu_categories.json, zonder LLM-call
(#88 besluit 3). Alleen bij vervolgvragen ("waarom…", versievragen,
"heb je dit gecheckt") of als de vraag méér vraagt dan het kale feit gaat
het bericht naar een agent.

Drie pure operaties (geen netwerk/LLM, #124): recognize_turn herkent een
beurt tegen de lookup-toestand van de conversatie, complete_with_intake vult
alleen een herkende onvolledige lookup aan met gegronde intakefeiten, en
render_answer zet een Ready-beslissing om in tekst. app/main.py,
intake.decide_route en eval/run_eval.py (#92) gebruiken dezelfde operaties,
zodat de eval de productie-flow spiegelt.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

import context
import knwu_categories

# Woorden die aangeven dat de vraag méér is dan het kale feit -> geen bypass.
MEER_DAN_FEIT = re.compile(
    r"\b(waarom|hoe zit het|hoe zit|uitleg|leg uit|leg toe|versie|gecheckt|"
    r"heb je dit|bron|waar staat|geldt dit|ook voor|wat als|verschil|"
    r"toelichting|pakket|kosten|prijs|tarief|bedrag|regels|"
    r"hoe (meet|bereken|bepaal|werkt)|hoe (vraag|regel|krijg|kom)|uitzondering(en)?|"
    r"combinatiewedstrijd(en)?|hoger start\w*)\b",
    re.IGNORECASE,
)
# Onderwerpen die een echte (reglement)vraag zijn, geen kale lookup.
REGELMENT_ONDERWERP = re.compile(
    r"\b(wedstrijd|nk|meedoen|deelnemen|inschrijf|verzekerd|verzekering|"
    r"contributie|zmc|mnc|training|kalender|starttijd|dispensatie|"
    r"ranglijst|kwalificatie)\b",
    re.IGNORECASE,
)
CATEGORIE_VRAAG = re.compile(
    r"(in welke|welke|in welk|waarin)\s+(leeftijds)?categorie"
    r"|wat\s+is\s+(?:(?:de|een)\s+)?(?:leeftijds)?categorie\b"
    r"|categorie\s+(rijdt|valt|hoort)"
    r"|rijdt\s+in\s+(een\s+|de\s+)?categorie"
    r"|hoort\s+bij\s+(een\s+|de\s+)?categorie",
    re.IGNORECASE,
)
LICENTIE_MENTION = re.compile(r"\blicentie", re.IGNORECASE)
VRAAG_WOORD = re.compile(
    r"\b(welke|welk|wlke|wlk|wat|hoe|hoeveel|heeft|heb|nodig|aanvragen|krijg|krijgt)\b",
    re.IGNORECASE,
)
VERZET_VRAAG = re.compile(
    r"verzet|tandwiel|versnelling|rollout|afgerolde\s+afstand", re.IGNORECASE
)
VERTALING_VRAAG = re.compile(
    r"wat\s+(is|betekent)|hoe\s+heet|betekenis|vertaling|nieuwe\s+aanduiding"
    r"|hoe\s+heet\s+.*\s+nu|omgerekend|in\s+de\s+nieuwe",
    re.IGNORECASE,
)
NEW_CATEGORY_PATTERN = re.compile(r"\b(JO|MO|MU|VU|U)(\d{1,2})\b", re.IGNORECASE)
CATEGORY_FRAGMENT_PATTERN = re.compile(
    r"(?:JO|MO|MU|VU|U)\d{1,2}"
    r"(?:\s*(?:/|,|&|\ben\b)\s*(?:JO|MO|MU|VU|U)\d{1,2})*",
    re.IGNORECASE,
)
OLD_DESIGNATION_REQUEST = re.compile(r"\b(categorie(?:ën|en)?|oude\s+indeling)\b", re.IGNORECASE)
DISCIPLINE_PATTERNS = [
    ("veld", re.compile(r"\b(veldrijden|veldrit|in het veld|het veld|veld|cross)\b", re.IGNORECASE)),
    ("weg", re.compile(r"\b(wegwielrennen|op de weg|de weg|weg)\b", re.IGNORECASE)),
]
BUITEN_SCOPE_DISCIPLINE = re.compile(
    r"\b(baanwielrennen|baanrennen|baan|mountainbik\w*|mtb|bmx)\b", re.IGNORECASE
)
MULTIPLE_RIDERS = re.compile(
    r"\b(?:twee|beide|allebei|meerdere|kinderen|renners)\b"
    r"|\b(?:zoon|dochter|kind)\s+en\s+(?:zoon|dochter|kind)\b",
    re.IGNORECASE,
)

# Disclaimer aan het eind van elk deterministisch antwoord (#91 besluit 4):
# dit is het kale feit; bij een vervolgvraag ("waarom", versie, "heb je dit
# gecheckt") schakelt de app door naar de document-library.
DISCLAIMER_LIBRARY = (
    "Stel je een vervolgvraag, dan fiets ik met je "
    "door de KNWU-informatie"
)

Gender = knwu_categories.Gender
SupportedDiscipline = Literal["weg", "veld"]


@dataclass(frozen=True)
class SourceFact:
    name: str
    version: str | None
    article: str | None


@dataclass(frozen=True)
class AnswerSources:
    age_categories: SourceFact
    gearing: SourceFact
    licences: SourceFact
    old_categories: SourceFact


@dataclass(frozen=True)
class BirthYearSelector:
    kind: Literal["birth_year"]
    birth_year: int


@dataclass(frozen=True)
class CategoryMember:
    gender: Gender | None
    category: str


@dataclass(frozen=True)
class CategorySelector:
    kind: Literal["category"]
    members: tuple[CategoryMember, ...]


@dataclass(frozen=True)
class OldCategorySelector:
    kind: Literal["old_category"]
    number: int
    members: tuple[CategoryMember, ...]


@dataclass(frozen=True)
class StandaloneLicenceSelector:
    kind: Literal["standalone_licence"]
    name: Literal["KNWU Licentie 17+"]


PrimarySelector: TypeAlias = (
    BirthYearSelector
    | CategorySelector
    | OldCategorySelector
    | StandaloneLicenceSelector
)


@dataclass(frozen=True)
class LookupProfile:
    selector: PrimarySelector | None
    gender: Gender | None
    discipline: SupportedDiscipline | None
    category_filter: tuple[tuple[CategoryMember, ...], ...] = ()


@dataclass(frozen=True)
class NoLookupState:
    kind: Literal["none"] = "none"


@dataclass(frozen=True)
class PendingLookupState:
    kind: Literal["pending"] = "pending"
    profile: LookupProfile = LookupProfile(None, None, None)


@dataclass(frozen=True)
class CompletedLookupState:
    kind: Literal["completed"] = "completed"
    profile: LookupProfile = LookupProfile(None, None, None)


LookupState: TypeAlias = NoLookupState | PendingLookupState | CompletedLookupState


@dataclass(frozen=True)
class InputEvidence:
    explicit_birth_years: tuple[int, ...] = ()
    contains_age: bool = False
    requires_intake: bool = False


@dataclass(frozen=True)
class Season:
    discipline: SupportedDiscipline
    start_year: int
    end_year: int
    reference_year: int


@dataclass(frozen=True)
class LicenceFact:
    name: str
    period: str | None = None


@dataclass(frozen=True)
class AnswerRow:
    season: Season
    gender: Gender
    category: str
    birth_year: int
    old_category: int | None
    gear: float | str | None
    licences: tuple[LicenceFact, ...]


@dataclass(frozen=True)
class ReadyLookup:
    selector: PrimarySelector
    profile: LookupProfile
    heading: str
    rows: tuple[AnswerRow, ...]
    sources: AnswerSources
    outside_youth_birth_year: int | None = None


@dataclass(frozen=True)
class Ready:
    kind: Literal["ready"]
    ready: ReadyLookup
    next_state: CompletedLookupState


@dataclass(frozen=True)
class NeedsInformation:
    kind: Literal["needs_information"]
    next_state: PendingLookupState
    evidence: InputEvidence = InputEvidence()


@dataclass(frozen=True)
class NotEligible:
    kind: Literal["not_eligible"]
    next_state: NoLookupState


LookupDecision: TypeAlias = Ready | NeedsInformation | NotEligible


@dataclass(frozen=True)
class _ParsedTurn:
    eligible: bool
    profile: LookupProfile
    evidence: InputEvidence = InputEvidence()


@dataclass(frozen=True)
class _TurnShape:
    is_complete_question: bool
    is_fragment: bool
    old_category_fragment: bool


@dataclass(frozen=True)
class _CategoryInputs:
    members: tuple[CategoryMember, ...]
    old_number: int | None
    old_members: tuple[CategoryMember, ...]


@dataclass(frozen=True)
class _ParsedInputs:
    profile: LookupProfile
    evidence: InputEvidence


def _supported_seasons(today: date) -> tuple[Season, Season]:
    year = today.year
    if today.month <= 2:
        return (
            Season("veld", year - 1, year, year),
            Season("weg", year, year, year),
        )
    if today.month <= 9:
        return (
            Season("weg", year, year, year),
            Season("veld", year, year + 1, year + 1),
        )
    return (
        Season("veld", year, year + 1, year + 1),
        Season("weg", year + 1, year + 1, year + 1),
    )


def _gender_in_message(message: str) -> Gender | None:
    boys = re.search(r"\b(jongen(?:s)?|zoon)\b", message, re.IGNORECASE) is not None
    girls = re.search(r"\b(meisje(?:s)?|dochter)\b", message, re.IGNORECASE) is not None
    if boys == girls:
        return None
    return "jongens" if boys else "meisjes"


def _discipline_in_message(message: str) -> tuple[SupportedDiscipline | None, bool]:
    selected: list[SupportedDiscipline] = []
    for discipline, pattern in DISCIPLINE_PATTERNS:
        if not pattern.search(message):
            continue
        if discipline == "weg":
            selected.append("weg")
        elif discipline == "veld":
            selected.append("veld")
    if len(selected) > 1:
        return None, True
    if selected:
        return selected[0], False
    if BUITEN_SCOPE_DISCIPLINE.search(message):
        return None, True
    return None, False


def _category_members(message: str, rules: dict) -> tuple[CategoryMember, ...] | None:
    members: list[CategoryMember] = []
    for match in NEW_CATEGORY_PATTERN.finditer(message):
        if re.search(
            r"\blicentie\s*$",
            message[max(0, match.start() - 15) : match.start()],
            re.IGNORECASE,
        ):
            continue
        prefix, under_text = match.groups()
        under = int(under_text)
        if under == 16:
            under = 17
        category = knwu_categories.category_name(under, rules)
        if category is None:
            return None
        gender: Gender | None = None
        if prefix.upper() in ("JO", "MU"):
            gender = "jongens"
        elif prefix.upper() in ("MO", "VU"):
            gender = "meisjes"
        member = CategoryMember(gender, category)
        if member not in members:
            members.append(member)
    return tuple(members)


def _old_category_members(number: int, rules: dict) -> tuple[CategoryMember, ...] | None:
    groups = knwu_categories.old_category_groups(number, rules)
    if not groups:
        return None
    members: list[CategoryMember] = []
    for group in groups:
        for gender in ("jongens", "meisjes"):
            under = group.get(gender)
            if under is None:
                continue
            category = knwu_categories.category_name(under, rules)
            if category is None:
                return None
            members.append(CategoryMember(gender, category))
    return tuple(members)


def _turn_shape(text: str) -> _TurnShape:
    licence_question = bool(LICENTIE_MENTION.search(text) and VRAAG_WOORD.search(text))
    verzet_question = bool(
        VERZET_VRAAG.search(text)
        and (VRAAG_WOORD.search(text) or "?" in text)
    )
    old_category_fragment = bool(
        context.OLD_CATEGORY_PATTERN.fullmatch(text.rstrip(".?!"))
    )
    category_fragment = bool(CATEGORY_FRAGMENT_PATTERN.fullmatch(text.rstrip(".?!")))
    translation_question = bool(
        VERTALING_VRAAG.search(text)
        and (
            NEW_CATEGORY_PATTERN.search(text)
            or context.CALENDAR_PATTERN.search(text)
            or context.NIEUWELING_PATTERN.search(text)
            or context.old_category_numbers(text)
        )
    )
    is_complete_question = bool(
        CATEGORIE_VRAAG.search(text)
        or licence_question
        or verzet_question
        or translation_question
        or (OLD_DESIGNATION_REQUEST.search(text) and not old_category_fragment)
        or (context.old_category_numbers(text) and not old_category_fragment)
        or (context.CALENDAR_PATTERN.search(text) and not category_fragment)
    )
    is_fragment = bool(
        context.BARE_YEAR_MESSAGE.fullmatch(text)
        or re.fullmatch(r"\s*(?:en\s+)?voor\s+(?:19|20)\d{2}\s*[.?!]*", text, re.IGNORECASE)
        or re.fullmatch(
            r"\s*(?:geboortejaar|geboren(?:\s+in)?)\s*[:=]?\s*(?:19|20)\d{2}\s*[.?!]*",
            text,
            re.IGNORECASE,
        )
        or re.fullmatch(r"\s*(?:U17[\s-]+)?nieuweling(?:en)?\s*[.?!]*", text, re.IGNORECASE)
        or old_category_fragment
        or re.fullmatch(r"\s*(?:alleen\s+)?(?:jongens|meisjes)\s*[.?!]*", text, re.IGNORECASE)
        or re.fullmatch(
            r"\s*(?:alleen\s+)?(?:weg(?:wielrennen)?|veld(?:rijden|rit)?|cross)\s*[.?!]*",
            text,
            re.IGNORECASE,
        )
        or category_fragment
    )
    return _TurnShape(
        is_complete_question,
        is_fragment,
        old_category_fragment,
    )


def _parse_category_inputs(text: str, rules: dict) -> _CategoryInputs | None:
    members = _category_members(text, rules)
    if members is None:
        return None
    old_numbers = context.old_category_numbers(text)
    if len(old_numbers) > 1:
        return None
    old_members = _old_category_members(old_numbers[0], rules) if old_numbers else ()
    if old_members is None:
        return None
    if len(members) > 1 and not (
        len(members) == 2
        and {member.gender for member in members} == {"jongens", "meisjes"}
    ):
        return None
    return _CategoryInputs(members, old_numbers[0] if old_numbers else None, old_members)


def _parse_year_evidence(
    text: str, shape: _TurnShape, has_category_selector: bool
) -> InputEvidence | None:
    explicit_years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    if context.BARE_YEAR_MESSAGE.fullmatch(text):
        year_match = re.search(r"\d{4}", text)
        birth_years = [int(year_match.group())] if year_match else []
    else:
        birth_years = []
        birth_year_patterns = (
            r"\bgeboortejaar\s*[:=]?\s*((?:19|20)\d{2})\b",
            r"\bgeboren(?:\s+in)?\s+((?:19|20)\d{2})\b",
            r"\b(?:uit|voor)\s+((?:19|20)\d{2})\b",
        )
        for pattern in birth_year_patterns:
            birth_years.extend(
                int(match) for match in re.findall(pattern, text, re.IGNORECASE)
            )
        birth_years = list(dict.fromkeys(birth_years))
    if len(birth_years) > 1 or context.find_ages_in_years(text):
        return None
    unmatched_years = [
        int(year) for year in explicit_years if int(year) not in birth_years
    ]
    if not unmatched_years:
        return InputEvidence(tuple(birth_years))
    is_groundable_year = (
        len(explicit_years) == 1
        and len(unmatched_years) == 1
        and not birth_years
        and not has_category_selector
        and shape.is_complete_question
        and not re.search(
            r"\b(?:in|seizoen|veldritseizoen|wedstrijdjaar)\s+(?:19|20)\d{2}\b",
            text,
            re.IGNORECASE,
        )
    )
    if is_groundable_year:
        return InputEvidence(tuple(unmatched_years), requires_intake=True)
    return None


def _selector_from_inputs(
    text: str, evidence: InputEvidence, category_inputs: _CategoryInputs, rules: dict
) -> tuple[PrimarySelector | None, tuple[tuple[CategoryMember, ...], ...]] | None:
    selector: PrimarySelector | None = None
    category_filter: tuple[tuple[CategoryMember, ...], ...] = ()
    if evidence.explicit_birth_years and not evidence.requires_intake:
        selector = BirthYearSelector("birth_year", evidence.explicit_birth_years[0])
        if category_inputs.members:
            category_filter += (category_inputs.members,)
        if category_inputs.old_members:
            category_filter += (category_inputs.old_members,)
    elif category_inputs.old_number is not None:
        selector = OldCategorySelector(
            "old_category", category_inputs.old_number, category_inputs.old_members
        )
        if category_inputs.members:
            category_filter = (category_inputs.members,)
    elif category_inputs.members:
        selector = CategorySelector("category", category_inputs.members)
    elif (
        re.search(r"\blicentie\s+17\s*\+", text, re.IGNORECASE)
        and VRAAG_WOORD.search(text)
    ):
        selector = StandaloneLicenceSelector("standalone_licence", "KNWU Licentie 17+")
    elif re.search(r"\bnieuweling(?:en)?\b", text, re.IGNORECASE):
        category = knwu_categories.category_name(17, rules)
        if category is not None:
            selector = CategorySelector("category", (CategoryMember(None, category),))
    if evidence.requires_intake and selector is not None:
        return None
    return selector, category_filter


def _explicit_attributes(text: str) -> tuple[Gender | None, SupportedDiscipline | None] | None:
    if (
        MEER_DAN_FEIT.search(text)
        or REGELMENT_ONDERWERP.search(text)
        or BUITEN_SCOPE_DISCIPLINE.search(text)
        or MULTIPLE_RIDERS.search(text)
    ):
        return None
    discipline, conflict = _discipline_in_message(text)
    if conflict:
        return None
    gender = _gender_in_message(text)
    if re.search(r"\b(?:jongens|meisjes)\b", text, re.IGNORECASE) and gender is None:
        return None
    return gender, discipline


def _parse_explicit_inputs(
    text: str, rules: dict, shape: _TurnShape
) -> _ParsedInputs | None:
    attributes = _explicit_attributes(text)
    if attributes is None:
        return None
    gender, discipline = attributes

    category_inputs = _parse_category_inputs(text, rules)
    if category_inputs is None:
        return None
    members = category_inputs.members
    if (
        len(members) == 1
        and members[0].gender is not None
        and gender is not None
        and gender != members[0].gender
    ):
        return None
    evidence = _parse_year_evidence(
        text, shape, bool(members or category_inputs.old_number is not None)
    )
    if evidence is None:
        return None

    selection = _selector_from_inputs(text, evidence, category_inputs, rules)
    if selection is None:
        return None
    selector, category_filter = selection

    profile = LookupProfile(
        selector=selector,
        gender=gender or (
            selector.members[0].gender
            if isinstance(selector, CategorySelector) and len(selector.members) == 1
            else None
        ),
        discipline=discipline,
        category_filter=category_filter,
    )
    return _ParsedInputs(profile, evidence)


def _apply_followup(
    parsed: _ParsedInputs,
    text: str,
    shape: _TurnShape,
    previous_state: LookupState,
) -> LookupProfile:
    if not shape.is_fragment or not isinstance(
        previous_state, (PendingLookupState, CompletedLookupState)
    ):
        return parsed.profile
    base = previous_state.profile
    profile = parsed.profile
    selector = profile.selector
    gender = profile.gender
    discipline = profile.discipline or base.discipline
    category_filter = profile.category_filter
    has_gender_word = bool(re.search(r"\b(?:jongens|meisjes)\b", text, re.IGNORECASE))

    if selector is None:
        selector = base.selector
        category_filter = base.category_filter
        if gender is None and not has_gender_word:
            gender = base.gender
        elif (
            gender is not None
            and gender != base.gender
            and isinstance(selector, CategorySelector)
            and len(selector.members) == 1
            and selector.members[0].gender is not None
        ):
            selector = CategorySelector(
                "category", (CategoryMember(None, selector.members[0].category),)
            )
    elif gender is None:
        gender = base.gender
    return LookupProfile(selector, gender, discipline, category_filter)


def _parse_lookup_turn(
    message: str, rules: dict, previous_state: LookupState
) -> _ParsedTurn:
    text = message.strip()
    empty_profile = LookupProfile(None, None, None)
    shape = _turn_shape(text)
    explicit_inputs = _parse_explicit_inputs(text, rules, shape)
    if explicit_inputs is None:
        return _ParsedTurn(False, empty_profile)

    eligible = bool(
        context.BARE_YEAR_MESSAGE.fullmatch(text)
        or shape.old_category_fragment
        or shape.is_complete_question
        or (
            shape.is_fragment
            and isinstance(previous_state, (PendingLookupState, CompletedLookupState))
        )
    )
    if not eligible:
        return _ParsedTurn(False, empty_profile)
    profile = _apply_followup(explicit_inputs, text, shape, previous_state)
    return _ParsedTurn(True, profile, explicit_inputs.evidence)


def _season_label(season: Season) -> str:
    if season.discipline == "veld":
        return f"Veldrijden {season.start_year}-{season.end_year}"
    return f"Wegwielrennen {season.reference_year}"


def _old_category_for(gender: Gender, category: str, rules: dict) -> int | None:
    under = int(category.split()[0][1:])
    for number_text, groups in rules["oude_categorie_indeling"]["categorieen"].items():
        if any(group.get(gender) == under for group in groups):
            return int(number_text)
    return None


def _licences_for_season(birth_year: int, season: Season, rules: dict) -> tuple[LicenceFact, ...]:
    start_name = knwu_categories.licence(birth_year, season.start_year, rules)
    end_name = knwu_categories.licence(birth_year, season.end_year, rules)
    if start_name == end_name:
        return (LicenceFact(start_name),) if start_name else ()
    facts: list[LicenceFact] = []
    if start_name:
        facts.append(LicenceFact(start_name, f"t/m dec {season.start_year}"))
    if end_name:
        facts.append(LicenceFact(end_name, f"vanaf jan {season.end_year}"))
    return tuple(facts)


def _members_for_profile(profile: LookupProfile) -> tuple[CategoryMember, ...]:
    selector = profile.selector
    if isinstance(selector, CategorySelector):
        return selector.members
    if isinstance(selector, OldCategorySelector):
        return selector.members
    return ()


def _ages_for_category(category: str, rules: dict) -> tuple[int, ...]:
    return tuple(
        int(age)
        for age, name in rules["leeftijdscategorieen"]["per_leeftijd"].items()
        if name == category
    )


def _candidate_birth_years(
    selector: PrimarySelector,
    season: Season,
    members: tuple[CategoryMember, ...],
    rules: dict,
) -> tuple[int, ...]:
    if isinstance(selector, BirthYearSelector):
        return (selector.birth_year,)
    return tuple(
        season.reference_year - age
        for member in members
        for age in _ages_for_category(member.category, rules)
    )


def _matches_category_constraints(
    profile: LookupProfile,
    category_members: tuple[CategoryMember, ...],
    category: str,
    gender: Gender,
) -> bool:
    if profile.category_filter and any(
        not any(
            member.category == category and member.gender in (None, gender)
            for member in constraint
        )
        for constraint in profile.category_filter
    ):
        return False
    if category_members and not any(
        member.category == category and member.gender in (None, gender)
        for member in category_members
    ):
        return False
    return not (
        profile.gender
        and category_members
        and not any(
            member.category == category and member.gender in (None, profile.gender)
            for member in category_members
        )
    )


def _rows_for_season(
    profile: LookupProfile, season: Season, genders: tuple[Gender, ...], rules: dict
) -> list[AnswerRow]:
    selector = profile.selector
    if selector is None:
        return []
    category_members = _members_for_profile(profile)
    rows: list[AnswerRow] = []
    seen: set[tuple[Gender, str, int]] = set()
    for birth_year in _candidate_birth_years(selector, season, category_members, rules):
        age = season.reference_year - birth_year
        category = knwu_categories.age_category(birth_year, season.reference_year, rules)
        if not 5 <= age <= 16 or category is None:
            continue
        for gender in genders:
            if not _matches_category_constraints(profile, category_members, category, gender):
                continue
            row_key = (gender, category, birth_year)
            if row_key in seen:
                continue
            seen.add(row_key)
            rows.append(
                AnswerRow(
                    season=season,
                    gender=gender,
                    category=category,
                    birth_year=birth_year,
                    old_category=_old_category_for(gender, category, rules),
                    gear=knwu_categories.max_gear(category, season.discipline, gender, rules),
                    licences=_licences_for_season(birth_year, season, rules),
                )
            )
    return rows


def _calculate_rows(profile: LookupProfile, today: date, rules: dict) -> tuple[AnswerRow, ...]:
    if profile.selector is None or isinstance(profile.selector, StandaloneLicenceSelector):
        return ()
    seasons = _supported_seasons(today)
    disciplines = (profile.discipline,) if profile.discipline else ("weg", "veld")
    genders: tuple[Gender, ...] = (
        (profile.gender,) if profile.gender else ("jongens", "meisjes")
    )
    rows = [
        row
        for season in seasons
        if season.discipline in disciplines
        for row in _rows_for_season(profile, season, genders, rules)
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                seasons.index(row.season),
                0 if row.gender == "jongens" else 1,
                row.birth_year,
            ),
        )
    )


def _heading_for(profile: LookupProfile, rules: dict) -> str:
    selector = profile.selector
    if isinstance(selector, BirthYearSelector):
        return f"Geboortejaar {selector.birth_year}"
    if isinstance(selector, OldCategorySelector):
        last_group = (knwu_categories.old_category_groups(selector.number, rules) or [])[-1]
        notation = knwu_categories.combined_notation(last_group.get("jongens"), last_group.get("meisjes"))
        return f"Oude cat. {selector.number} ({notation})"
    if isinstance(selector, StandaloneLicenceSelector):
        return selector.name
    if isinstance(selector, CategorySelector):
        if len(selector.members) == 2 and all(member.gender for member in selector.members):
            boys = next(member for member in selector.members if member.gender == "jongens")
            girls = next(member for member in selector.members if member.gender == "meisjes")
            notation = knwu_categories.combined_notation(
                int(boys.category.split()[0][1:]),
                int(girls.category.split()[0][1:]),
            )
            return notation
        member = selector.members[0]
        if member.gender:
            prefix = "JO" if member.gender == "jongens" else "MO"
            under = member.category.split()[0].removeprefix("U")
            return f"{prefix}{under}"
        return member.category
    return "Overzicht"


def _answer_sources(rules: dict) -> AnswerSources:
    return AnswerSources(
        age_categories=SourceFact(
            rules["bron"], rules["versie"], rules["leeftijdscategorieen"]["artikel"]
        ),
        gearing=SourceFact(
            rules["verzetten"]["bron"],
            rules["verzetten"]["versie"],
            rules["verzetten"]["artikel"],
        ),
        licences=SourceFact(rules["bron"], rules["versie"], rules["licenties"]["artikel"]),
        old_categories=SourceFact(
            rules["oude_categorie_indeling"]["bron"], None, None
        ),
    )


def _gear_text(value: float | str | None) -> str:
    if value == "vrij":
        return "vrij"
    if value is None:
        return "NVT (niet van toepassing)"
    return f"{value:.2f}".replace(".", ",") + " meter"


def _render_standalone_licence(
    selector: StandaloneLicenceSelector, source: SourceFact, level: str
) -> str:
    article = f" (artikel {source.article})" if level == "B2" else ""
    return (
        f"**{selector.name}**\n\n"
        f"- **Licentie:** {selector.name}\n\n"
        f"{DISCLAIMER_LIBRARY}\n\n"
        f"Bron: {source.name}, versie {source.version}{article}"
    )


def _render_row(ready: ReadyLookup, row: AnswerRow) -> list[str]:
    title = f"### {_season_label(row.season)} · {row.gender.capitalize()}"
    if isinstance(ready.selector, CategorySelector | OldCategorySelector):
        title += f" · geboortejaar {row.birth_year}"
    category = (
        f"- **Categorie:** {row.category} "
        f"(oude cat. {row.old_category if row.old_category is not None else 'n.v.t.'})"
    )
    licence_text = ", ".join(
        fact.name.removeprefix("KNWU Licentie ")
        + (f" ({fact.period})" if fact.period else "")
        for fact in row.licences
    ) or "geen jeugdlicentie"
    return [
        title,
        category,
        f"- **Verzet:** {_gear_text(row.gear)}",
        f"- **Licentie:** {licence_text}",
        "",
    ]


def _render_source_line(sources: AnswerSources, level: str) -> str:
    age_source = f"{sources.age_categories.name}, versie {sources.age_categories.version}"
    gear_source = f"{sources.gearing.name}, versie {sources.gearing.version}"
    licence_source = f"{sources.licences.name}, versie {sources.licences.version}"
    if level == "B2":
        age_source += f" (artikel {sources.age_categories.article})"
        gear_source += f" (artikel {sources.gearing.article})"
        licence_source += f" (artikel {sources.licences.article})"
    return (
        f"Bron: {age_source}; {gear_source}; {licence_source}; "
        f"{sources.old_categories.name}"
    )


def _render_ready(ready: ReadyLookup, language_level: str) -> str:
    level = context.normalize_language_level(language_level)
    if isinstance(ready.selector, StandaloneLicenceSelector):
        return _render_standalone_licence(ready.selector, ready.sources.licences, level)
    lines = [f"**{ready.heading}**", ""]
    for row in ready.rows:
        lines.extend(_render_row(ready, row))
    if ready.outside_youth_birth_year is not None:
        lines.extend(
            [
                f"Geboortejaar {ready.outside_youth_birth_year} valt buiten de jeugdindeling.",
                "",
            ]
        )
    lines.extend(
        [
            "Vooruitblik op basis van de bekende regels; die kunnen wijzigen.",
            DISCLAIMER_LIBRARY,
            "",
            _render_source_line(ready.sources, level),
        ]
    )
    return "\n".join(lines)


def recognize_turn(
    message: str,
    previous_state: LookupState | None,
    today: date,
    rules: dict,
) -> LookupDecision:
    """Recognize, validate and calculate a deterministic lookup without side effects."""
    state = previous_state or NoLookupState()
    parsed = _parse_lookup_turn(message, rules, state)
    if not parsed.eligible:
        return NotEligible("not_eligible", NoLookupState())
    if parsed.profile.selector is None:
        pending = PendingLookupState(profile=parsed.profile)
        return NeedsInformation("needs_information", pending, parsed.evidence)
    if (
        isinstance(parsed.profile.selector, BirthYearSelector)
        and parsed.profile.selector.birth_year > today.year
    ):
        return NotEligible("not_eligible", NoLookupState())

    rows = _calculate_rows(parsed.profile, today, rules)
    outside_youth = None
    if (
        not rows
        and isinstance(parsed.profile.selector, BirthYearSelector)
        and not parsed.profile.category_filter
        and knwu_categories.age_category(
            parsed.profile.selector.birth_year, today.year, rules
        ) is None
        and knwu_categories.licence(
            parsed.profile.selector.birth_year, today.year, rules
        ) is None
    ):
        outside_youth = parsed.profile.selector.birth_year
    is_standalone_license = isinstance(parsed.profile.selector, StandaloneLicenceSelector)
    if not rows and outside_youth is None and not is_standalone_license:
        return NotEligible("not_eligible", NoLookupState())
    ready = ReadyLookup(
        selector=parsed.profile.selector,
        profile=parsed.profile,
        heading=_heading_for(parsed.profile, rules),
        rows=rows,
        sources=_answer_sources(rules),
        outside_youth_birth_year=outside_youth,
    )
    completed = CompletedLookupState(profile=parsed.profile)
    return Ready("ready", ready, completed)


def complete_with_intake(
    needs_information: NeedsInformation,
    intake_result: dict[str, object],
    today: date,
    rules: dict,
) -> LookupDecision:
    """Complete only a recognized pending lookup with explicit intake facts."""
    if not isinstance(needs_information, NeedsInformation):
        raise TypeError("complete_with_intake requires a NeedsInformation decision")
    profile = needs_information.next_state.profile
    year = intake_result.get("geboortejaar")
    age = intake_result.get("leeftijd")
    evidence = needs_information.evidence
    grounded_year = evidence.requires_intake and year in evidence.explicit_birth_years
    if (
        profile.selector is None
        and not evidence.contains_age
        and age is None
        and grounded_year
        and isinstance(year, int)
        and not isinstance(year, bool)
    ):
        if year > today.year:
            return NotEligible("not_eligible", NoLookupState())
        profile = LookupProfile(
            BirthYearSelector("birth_year", year),
            profile.gender,
            profile.discipline,
            profile.category_filter,
        )
    if profile.selector is None:
        return NeedsInformation(
            "needs_information", PendingLookupState(profile=profile), needs_information.evidence
        )
    rows = _calculate_rows(profile, today, rules)
    if not rows:
        return NotEligible("not_eligible", NoLookupState())
    ready = ReadyLookup(
        profile.selector,
        profile,
        _heading_for(profile, rules),
        rows,
        _answer_sources(rules),
    )
    return Ready("ready", ready, CompletedLookupState(profile=profile))


def render_answer(ready: Ready, language_level: str) -> str:
    """Render validated answer facts without reading or interpreting user text."""
    if not isinstance(ready, Ready):
        raise TypeError("render_answer requires a Ready decision")
    return _render_ready(ready.ready, language_level)
