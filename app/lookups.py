"""Deterministische lookup-antwoorden (#91; data uit #94).

Pure feitelijke lookup-vragen — leeftijdscategorie, licentie, maximaal
verzet per discipline, oude categorie-indeling — beantwoordt de app zelf
met een template-antwoord uit knwu_categories.json, zonder LLM-call
(#88 besluit 3). Alleen bij vervolgvragen ("waarom…", versievragen,
"heb je dit gecheckt") of als de vraag méér vraagt dan het kale feit gaat
het bericht naar een agent.

match_lookup() is een pure functie (geen netwerk/LLM), net als
render_lookup_answer(); samen met intake.decide_route() bepalen ze de
route van een bericht. Dezelfde functies gebruikt eval/run_eval.py (#92),
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
    r"hoe (meet|bereken|bepaal|werkt)|uitzondering(en)?)\b",
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
    r"\b(welke|welk|wat|hoe|hoeveel|heeft|heb|nodig|aanvragen|krijg|krijgt)\b",
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
BIRTH_YEAR_REPLY = re.compile(
    r"(?:(?:hij|zij|ik)\s+(?:is|ben)\s+)?(?:geboren(?:\s+in)?|geboortejaar)"
    r"\s+(?:19|20)\d{2}",
    re.IGNORECASE,
)
DISCIPLINE_PATTERNS = [
    ("veld", re.compile(r"\b(veldrijden|veldrit|in het veld|het veld|veld|cross)\b", re.IGNORECASE)),
    ("weg", re.compile(r"\b(wegwielrennen|op de weg|de weg|weg)\b", re.IGNORECASE)),
]
DISCIPLINE_NAAM = {"weg": "wegwielrennen", "veld": "veldrijden"}
BUITEN_SCOPE_DISCIPLINE = re.compile(r"\b(baanwielrennen|baanrennen|baan)\b", re.IGNORECASE)
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
    is_complete_question: bool
    rejected: bool = False
    evidence: InputEvidence = InputEvidence()


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
    for prefix, under_text in NEW_CATEGORY_PATTERN.findall(message):
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


def _parse_lookup_turn(
    message: str, rules: dict, previous_state: LookupState
) -> _ParsedTurn:
    text = message.strip()
    no_state = LookupProfile(None, None, None)
    licence_question = bool(LICENTIE_MENTION.search(text) and VRAAG_WOORD.search(text))
    old_category_fragment = bool(
        context.OLD_CATEGORY_PATTERN.fullmatch(text.rstrip(".?!"))
    )
    category_fragment = bool(CATEGORY_FRAGMENT_PATTERN.fullmatch(text.rstrip(".?!")))
    is_complete_question = bool(
        CATEGORIE_VRAAG.search(text)
        or licence_question
        or VERZET_VRAAG.search(text)
        or (OLD_DESIGNATION_REQUEST.search(text) and not old_category_fragment)
        or (context.old_category_numbers(text) and not old_category_fragment)
        or (context.CALENDAR_PATTERN.search(text) and not category_fragment)
    )
    is_fragment = bool(
        context.BARE_YEAR_MESSAGE.fullmatch(text)
        or re.fullmatch(r"\s*(?:en\s+)?voor\s+(?:19|20)\d{2}\s*[.?!]*", text, re.IGNORECASE)
        or old_category_fragment
        or re.fullmatch(r"\s*(?:alleen\s+)?(?:jongens|meisjes)\s*[.?!]*", text, re.IGNORECASE)
        or re.fullmatch(
            r"\s*(?:alleen\s+)?(?:weg(?:wielrennen)?|veld(?:rijden|rit)?|cross)\s*[.?!]*",
            text,
            re.IGNORECASE,
        )
        or category_fragment
    )
    previous_profile = (
        previous_state.profile
        if isinstance(previous_state, (PendingLookupState, CompletedLookupState))
        else no_state
    )
    if (
        MEER_DAN_FEIT.search(text)
        or REGELMENT_ONDERWERP.search(text)
        or BUITEN_SCOPE_DISCIPLINE.search(text)
        or MULTIPLE_RIDERS.search(text)
    ):
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    discipline, discipline_conflict = _discipline_in_message(text)
    if discipline_conflict:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    gender = _gender_in_message(text)
    if re.search(r"\b(?:jongens|meisjes)\b", text, re.IGNORECASE) and gender is None:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    category_members = _category_members(text, rules)
    if category_members is None:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    if NEW_CATEGORY_PATTERN.search(text):
        category_matches = list(NEW_CATEGORY_PATTERN.finditer(text))
        non_license_matches = [
            match for match in category_matches
            if not re.search(r"\blicentie\s*$", text[max(0, match.start() - 15):match.start()], re.IGNORECASE)
        ]
        if len(non_license_matches) != len(category_matches):
            category_members = tuple(
                member for member, match in zip(category_members, category_matches)
                if match in non_license_matches
            )

    old_numbers = context.old_category_numbers(text)
    if len(old_numbers) > 1:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    old_members = (
        _old_category_members(old_numbers[0], rules)
        if old_numbers
        else None
    )
    if old_numbers and old_members is None:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    explicit_year_matches = re.findall(r"\b(?:19|20)\d{2}\b", text)
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
    if explicit_year_matches and not birth_years:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    ages = context.find_ages_in_years(text)
    evidence = InputEvidence(tuple(birth_years), bool(ages))
    if len(birth_years) > 1 or ages:
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    if any(int(year) not in birth_years for year in explicit_year_matches):
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    if len(category_members) > 1 and not (
        len(category_members) == 2
        and {member.gender for member in category_members} == {"jongens", "meisjes"}
    ):
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    paired_categories = len(category_members) > 1
    if not paired_categories and category_members and gender and category_members[0].gender:
        if gender != category_members[0].gender:
            return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    selector: PrimarySelector | None = None
    category_filter: tuple[tuple[CategoryMember, ...], ...] = ()
    if birth_years:
        selector = BirthYearSelector("birth_year", birth_years[0])
        if category_members:
            category_filter += (category_members,)
        if old_members:
            category_filter += (old_members,)
    elif old_numbers and old_members is not None:
        selector = OldCategorySelector("old_category", old_numbers[0], old_members)
        if category_members:
            category_filter = (category_members,)
    elif category_members:
        selector = CategorySelector("category", category_members)
    elif (
        re.search(r"\blicentie\s+17\s*\+", text, re.IGNORECASE)
        and VRAAG_WOORD.search(text)
    ):
        selector = StandaloneLicenceSelector("standalone_licence", "KNWU Licentie 17+")
    elif re.search(r"\bnieuweling(?:en)?\b", text, re.IGNORECASE):
        category = knwu_categories.category_name(17, rules)
        if category is not None:
            selector = CategorySelector("category", (CategoryMember(None, category),))

    eligible = bool(
        context.BARE_YEAR_MESSAGE.fullmatch(text)
        or old_category_fragment
        or is_complete_question
        or (is_fragment and isinstance(previous_state, (PendingLookupState, CompletedLookupState)))
    )
    if not eligible:
        return _ParsedTurn(False, no_state, is_complete_question)
    if is_complete_question and not (
        CATEGORIE_VRAAG.search(text)
        or licence_question
        or VERZET_VRAAG.search(text)
        or OLD_DESIGNATION_REQUEST.search(text)
        or context.old_category_numbers(text)
        or context.CALENDAR_PATTERN.search(text)
    ):
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)
    if is_fragment and isinstance(previous_state, (PendingLookupState, CompletedLookupState)):
        base = previous_profile
        if selector is not None:
            if (
                isinstance(selector, CategorySelector)
                and len(selector.members) == 1
                and selector.members[0].gender is not None
            ):
                gender = selector.members[0].gender
            elif gender is None:
                gender = base.gender
        else:
            selector = base.selector
            category_filter = base.category_filter
            if gender is None and not re.search(
                r"\b(?:jongens|meisjes)\b", text, re.IGNORECASE
            ):
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
        if discipline is None and not any(pattern.search(text) for _, pattern in DISCIPLINE_PATTERNS):
            discipline = base.discipline

    if selector is None and not (
        is_complete_question and (licence_question or VERZET_VRAAG.search(text))
    ):
        return _ParsedTurn(False, no_state, is_complete_question, rejected=True)

    # A single-category prefix fixes its gender; paired/old selectors are filtered by gender.
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
    return _ParsedTurn(True, profile, is_complete_question, evidence=evidence)


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


def _calculate_rows(profile: LookupProfile, today: date, rules: dict) -> tuple[AnswerRow, ...]:
    selector = profile.selector
    if selector is None or isinstance(selector, StandaloneLicenceSelector):
        return ()
    seasons = _supported_seasons(today)
    disciplines = (profile.discipline,) if profile.discipline else ("weg", "veld")
    genders: tuple[Gender, ...] = (
        (profile.gender,) if profile.gender else ("jongens", "meisjes")
    )
    category_members = _members_for_profile(profile)
    rows: list[AnswerRow] = []
    for season in seasons:
        if season.discipline not in disciplines:
            continue
        if isinstance(selector, BirthYearSelector):
            candidate_years = (selector.birth_year,)
        else:
            candidate_years = tuple(
                season.reference_year - age
                for member in category_members
                for age in _ages_for_category(member.category, rules)
            )
        seen: set[tuple[Gender, str, int]] = set()
        for birth_year in candidate_years:
            age = season.reference_year - birth_year
            category = knwu_categories.age_category(birth_year, season.reference_year, rules)
            if not 5 <= age <= 16 or category is None:
                continue
            for gender in genders:
                if profile.category_filter and any(
                    not any(
                        member.category == category and member.gender in (None, gender)
                        for member in constraint
                    )
                    for constraint in profile.category_filter
                ):
                    continue
                if category_members and not any(
                    member.category == category and member.gender in (None, gender)
                    for member in category_members
                ):
                    continue
                if profile.gender and category_members and not any(
                    member.category == category and member.gender in (None, profile.gender)
                    for member in category_members
                ):
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


def _render_ready(ready: ReadyLookup, language_level: str) -> str:
    level = context.normalize_language_level(language_level)
    if isinstance(ready.selector, StandaloneLicenceSelector):
        source = ready.sources.licences
        article = f" (artikel {source.article})" if level == "B2" else ""
        return (
            f"**{ready.selector.name}**\n\n"
            f"- **Licentie:** {ready.selector.name}\n\n"
            f"{DISCLAIMER_LIBRARY}\n\n"
            f"Bron: {source.name}, versie {source.version}{article}"
        )
    lines = [f"**{ready.heading}**", ""]
    for row in ready.rows:
        title = f"### {_season_label(row.season)} · {row.gender.capitalize()}"
        if isinstance(ready.selector, CategorySelector | OldCategorySelector):
            title += f" · geboortejaar {row.birth_year}"
        lines.extend(
            [
                title,
                f"- **Categorie:** {row.category} "
                f"(oude cat. {row.old_category if row.old_category is not None else 'n.v.t.'})",
                f"- **Verzet:** {_gear_text(row.gear)}",
            ]
        )
        licence_text = ", ".join(
            fact.name.removeprefix("KNWU Licentie ") +
            (f" ({fact.period})" if fact.period else "")
            for fact in row.licences
        ) or "geen jeugdlicentie"
        lines.append(f"- **Licentie:** {licence_text}")
        lines.append("")
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
        ]
    )
    sources = ready.sources
    age_source = f"{sources.age_categories.name}, versie {sources.age_categories.version}"
    gear_source = f"{sources.gearing.name}, versie {sources.gearing.version}"
    licence_source = f"{sources.licences.name}, versie {sources.licences.version}"
    old_source = sources.old_categories.name
    if level == "B2":
        age_source += f" (artikel {sources.age_categories.article})"
        gear_source += f" (artikel {sources.gearing.article})"
        licence_source += f" (artikel {sources.licences.article})"
    lines.append(f"Bron: {age_source}; {gear_source}; {licence_source}; {old_source}")
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
    grounded_year = year in needs_information.evidence.explicit_birth_years
    if (
        profile.selector is None
        and not needs_information.evidence.contains_age
        and age is None
        and grounded_year
        and isinstance(year, int)
        and not isinstance(year, bool)
    ):
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


def _discipline_uit_bericht(message: str, extra: dict) -> str | None:
    disciplines = [disc for disc, pattern in DISCIPLINE_PATTERNS if pattern.search(message)]
    if len(disciplines) == 1:
        return disciplines[0]
    if disciplines:
        return None
    discipline = extra.get("discipline")
    if discipline in DISCIPLINE_NAAM:
        return discipline
    return None


def _category_references(message: str, rules: dict) -> list[tuple[str, str | None]]:
    references = []
    boys = bool(re.search(r"\b(jongen(s)?|zoon)\b", message, re.IGNORECASE))
    girls = bool(re.search(r"\b(meisje(s)?|dochter)\b", message, re.IGNORECASE))
    for prefix, under in NEW_CATEGORY_PATTERN.findall(message):
        name = knwu_categories.category_name(int(under), rules)
        if not name:
            return []
        sex = {"JO": "jongens", "MU": "jongens", "MO": "meisjes", "VU": "meisjes"}.get(prefix.upper())
        if sex is None and boys != girls:
            sex = "jongens" if boys else "meisjes"
        if (name, sex) not in references:
            references.append((name, sex))
    return references


def _categorieen_uit_bericht(message: str, rules: dict) -> list[str]:
    references = _category_references(message, rules)
    if NEW_CATEGORY_PATTERN.search(message):
        return list(dict.fromkeys(name for name, _ in references))
    categories = []
    for number in context.old_category_numbers(message):
        groups = knwu_categories.old_category_groups(number, rules)
        if not groups:
            return []
        for group in groups:
            for under in group.values():
                name = knwu_categories.category_name(under, rules)
                if name and name not in categories:
                    categories.append(name)
    if context.NIEUWELING_PATTERN.search(message):
        categories.append(knwu_categories.category_name(17, rules))
    return [name for name in categories if name]


def _lookup_kind(message: str) -> str | None:
    if (
        MEER_DAN_FEIT.search(message)
        or REGELMENT_ONDERWERP.search(message)
        or BUITEN_SCOPE_DISCIPLINE.search(message)
    ):
        return None
    kinds = []
    if CATEGORIE_VRAAG.search(message):
        kinds.append("categorie")
    if LICENTIE_MENTION.search(message) and VRAAG_WOORD.search(message):
        kinds.append("licentie")
    if VERZET_VRAAG.search(message):
        kinds.append("verzet")
    return kinds[0] if len(kinds) == 1 else None


def _reply_kind(message: str) -> str | None:
    fragment = message.strip().rstrip(".?!")
    if any(pattern.fullmatch(fragment) for _, pattern in DISCIPLINE_PATTERNS):
        return "discipline"
    if context.BARE_YEAR_MESSAGE.fullmatch(message) or BIRTH_YEAR_REPLY.fullmatch(fragment):
        return "birth_year"
    if NEW_CATEGORY_PATTERN.search(fragment) and re.fullmatch(
        r"(?:\s|,|/|\ben\b)*",
        NEW_CATEGORY_PATTERN.sub("", fragment),
        re.IGNORECASE,
    ):
        return "category"
    if context.OLD_CATEGORY_PATTERN.fullmatch(fragment):
        return "category"
    if re.fullmatch(r"(?:U17[\s-]+)?nieuweling(?:en)?", fragment, re.IGNORECASE):
        return "category"
    return None


def resolve_lookup_message(
    message: str, previous_messages: list[str], today: date, rules: dict
) -> str:
    """Vul alleen korte antwoorden op een onvolledige lookup-vraag aan."""
    reply_kind = _reply_kind(message)
    if reply_kind is None:
        return message
    fragments = [message]
    for previous in reversed(previous_messages):
        if _reply_kind(previous):
            fragments.insert(0, previous)
            continue
        kind = _lookup_kind(previous)
        pending_message = "\n".join([previous, *fragments[:-1]])
        if not kind or match_lookup(pending_message, today, rules):
            break
        if kind != "verzet" and any(_reply_kind(part) != "birth_year" for part in fragments):
            break
        if kind == "verzet":
            if reply_kind == "discipline" and _discipline_uit_bericht(pending_message, {}):
                break
            if reply_kind != "discipline" and (
                _categorieen_uit_bericht(pending_message, rules)
                or context.find_birth_years(pending_message, today, rules)
            ):
                break
        return "\n".join([previous, *fragments])
    return message


def _reverse_designation_lines(message: str, rules: dict) -> list[str]:
    lines = []
    for name, sex in _category_references(message, rules):
        if name == rules["oude_categorie_indeling"]["nieuwelingen"]:
            lines.append(f"{name}: oude aanduiding nieuwelingen.")
            continue
        under = int(name.split()[0][1:])
        for gender in (sex,) if sex else ("jongens", "meisjes"):
            for number, groups in rules["oude_categorie_indeling"]["categorieen"].items():
                if any(group.get(gender) == under for group in groups):
                    notation = " en ".join(
                        knwu_categories.combined_notation(group.get("jongens"), group.get("meisjes"))
                        for group in groups
                    )
                    lines.append(f"{gender} {name}: categorie {number} ({notation}).")
    return list(dict.fromkeys(lines))


def match_lookup(
    message: str, today: date, rules: dict, extra: dict | None = None
) -> dict | None:
    """Detecteer een pure lookup-vraag; geef de data terug, anders None.

    `extra` vult aan vanuit de light intake (#91): {"geboortejaar": int,
    "discipline": "weg"|"veld"}. Alleen expliciete geboortejaren
    (of een kaal jaartal als antwoord op de geboortejaar-vraag) leiden
    tot een bypass — een leeftijd in jaren ("15-jarige") niet, omdat
    daarbij bronconflicten kunnen spelen die alleen een agent signaleert.
    """
    if (
        MEER_DAN_FEIT.search(message)
        or REGELMENT_ONDERWERP.search(message)
        or BUITEN_SCOPE_DISCIPLINE.search(message)
    ):
        return None
    extra = extra or {}
    if any(
        not knwu_categories.old_category_groups(number, rules)
        for number in context.old_category_numbers(message)
    ):
        return None
    if NEW_CATEGORY_PATTERN.search(message) and not _category_references(message, rules):
        return None
    birth_years = context.find_birth_years(message, today, rules)
    extra_year = extra.get("geboortejaar")
    if extra_year:
        try:
            year = int(extra_year)
        except (TypeError, ValueError):
            year = 0
        if year and year not in birth_years:
            birth_years.insert(0, year)

    kind = _lookup_kind(message)
    if kind is None and (
        CATEGORIE_VRAAG.search(message) or LICENTIE_MENTION.search(message) or VERZET_VRAAG.search(message)
    ):
        # meerdere onderwerpen in één vraag (bv. categorie én licentie) ->
        # cross-check met bronconflict-mogelijkheid -> agent
        return None

    if kind == "verzet":
        discipline = _discipline_uit_bericht(message, extra)
        categories = _categorieen_uit_bericht(message, rules)
        if not categories and len(birth_years) == 1 and not (
            NEW_CATEGORY_PATTERN.search(message) or context.old_category_numbers(message)
        ):
            year = knwu_categories.cyclocross_season(today)[1] if discipline == "veld" else today.year
            category = knwu_categories.age_category(birth_years[0], year, rules)
            categories = [category] if category else []
        if categories and discipline:
            if len(categories) == 1:
                return {"kind": "verzet", "category": categories[0], "discipline": discipline}
            return {"kind": "verzet", "categories": categories, "discipline": discipline}
        return None  # categorie of discipline ontbreekt -> agent stelt bij

    if (
        kind != "licentie"
        and not (kind == "categorie" and birth_years)
        and OLD_DESIGNATION_REQUEST.search(message)
    ):
        if _reverse_designation_lines(message, rules):
            return {"kind": "vertaling", "direction": "oud"}

    has_old_designation = bool(
        context.old_category_numbers(message)
        or context.NIEUWELING_PATTERN.search(message)
        or context.CALENDAR_PATTERN.search(message)
    )
    if kind != "licentie" and not (kind == "categorie" and birth_years) and has_old_designation and (
        VERTALING_VRAAG.search(message) or len(message.split()) <= 12
    ) and context.old_designation_lines(message, rules):
        return {"kind": "vertaling"}

    if kind in ("categorie", "licentie"):
        if birth_years:
            return {"kind": kind, "birth_year": birth_years[0]}
        return None  # geen geboortejaar bekend -> agent vraagt ernaar

    bare_year = context.BIRTH_YEAR_PATTERN.search(message)
    if bare_year and context.BARE_YEAR_MESSAGE.match(message):
        return {"kind": "categorie", "birth_year": int(bare_year.group(0))}

    return None


def _fmt_verzet(value: float | str | None) -> str:
    """6.7 -> "6,70 meter"; "vrij" -> "vrij"; None -> NVT."""
    if value == "vrij":
        return "vrij (geen beperking)"
    if value is None:
        return "NVT (niet van toepassing)"
    return f"{value:.2f}".replace(".", ",") + " meter"


def render_lookup_answer(
    match: dict, message: str, rules: dict, today: date, language_level: str
) -> str:
    """Template-antwoord uit knwu_categories.json met bron+versie+artikel.

    Bij taalniveau B2 staat de bron in een "Bron:"-regel (met artikel en
    versie); bij B1 (standaard) géén Bron-regel — zelfde regel als voor
    agent-antwoorden (#52). Elke variant eindigt op de disclaimer die
    aangeeft wanneer de library wél geraadpleegd wordt (#91 besluit 4).
    """
    level = context.normalize_language_level(language_level)
    kind = match["kind"]

    if kind == "vertaling":
        lines = (
            _reverse_designation_lines(message, rules)
            if match.get("direction") == "oud"
            else context.old_designation_lines(message, rules)
        )
        if not lines:
            raise ValueError("Geen categorievertaling gevonden voor de lookup.")
        answer = "\n".join(lines)
        answer += f"\n\n{DISCLAIMER_LIBRARY}"
        if level == "B2":
            answer += f"\n\nBron: {rules['oude_categorie_indeling']['bron']}"
        return answer

    if kind == "verzet":
        discipline = match["discipline"]
        if discipline not in DISCIPLINE_NAAM:
            raise ValueError(f"Discipline '{discipline}' valt buiten scope; gebruik weg of veld.")
        categories = match["categories"] if "categories" in match else [match["category"]]
        gender = match.get("gender")
        if gender == "jongens":
            genders: list[knwu_categories.Gender] = ["jongens"]
        elif gender == "meisjes":
            genders = ["meisjes"]
        elif gender is None:
            genders = ["jongens", "meisjes"]
        else:
            raise ValueError(f"Onbekend geslacht: {gender}")
        lines = context.old_designation_lines(message, rules) if context.old_category_numbers(message) else []
        for category in categories:
            label = f"{category} (nieuwelingen)" if "Nieuweling" in category else category
            for selected_gender in genders:
                gear = knwu_categories.max_gear(category, discipline, selected_gender, rules)
                lines.append(
                    f"Het maximaal toegestane verzet voor {selected_gender} {label} bij "
                    f"{DISCIPLINE_NAAM[discipline]} is {_fmt_verzet(gear)}."
                )
        answer = "\n".join(lines)
        answer += f"\n\n{DISCLAIMER_LIBRARY}"
        if level == "B2":
            answer += (
                f"\n\nBron: {rules['verzetten']['bron']}, versie "
                f"{rules['verzetten']['versie']} (artikel {rules['verzetten']['artikel']})"
            )
            if context.old_category_numbers(message):
                answer += f"\nBron categorievertaling: {rules['oude_categorie_indeling']['bron']}"
        return answer

    # kind == "categorie" | "licentie": categorie weg + veldseizoen + licentie
    birth_year = match["birth_year"]
    season_start, season_end = knwu_categories.cyclocross_season(today)
    road = knwu_categories.age_category(birth_year, today.year, rules)
    cross = knwu_categories.age_category(birth_year, season_end, rules)
    licence = knwu_categories.licence(birth_year, today.year, rules)
    if not road and not cross and not licence:
        return (
            f"Geboortejaar {birth_year} valt buiten de jeugdindeling: "
            "er is geen jeugdleeftijdscategorie en geen jeugdlicentie."
            f"\n\n{DISCLAIMER_LIBRARY}"
        )
    road_txt = road or "valt buiten de jeugdindeling"
    cross_txt = cross or "valt buiten de jeugdindeling"
    licence_txt = licence or "geen jeugdlicentie"
    answer = (
        f"Een renner geboren in {birth_year} rijdt in {today.year} in "
        f"leeftijdscategorie {road_txt} bij wegwielrennen en in het "
        f"veldritseizoen {season_start}-{season_end} in {cross_txt}. "
        f"De licentie in {today.year} is {licence_txt}."
    )
    answer += f"\n\n{DISCLAIMER_LIBRARY}"
    if level == "B2":
        answer += (
            f"\n\nBron: {rules['bron']}, versie {rules['versie']} "
            f"(artikel {rules['leeftijdscategorieen']['artikel']} voor de "
            f"leeftijdscategorie, artikel {rules['licenties']['artikel']} voor de licentie)"
        )
    return answer
