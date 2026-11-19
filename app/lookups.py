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
render_answer zet een ReadyForBypass-beslissing om in tekst. app/main.py,
intake.decide_route en eval/run_eval.py (#92) gebruiken dezelfde operaties,
zodat de eval de productie-flow spiegelt.
"""

import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, TypeAlias

import context
import knwu_categories
import message_recognition

# Woorden die aangeven dat de vraag méér is dan het kale feit -> geen bypass.
_MEER_DAN_FEIT = re.compile(
    r"\b(waarom|hoe zit het|hoe zit|uitleg|leg uit|leg toe|versie|gecheckt|"
    r"heb je dit|bron|waar staat|geldt dit|ook voor|wat als|verschil|"
    r"toelichting|pakket|kosten|prijs|tarief|bedrag|regels|"
    r"hoe (meet|bereken|bepaal|werkt)|hoe (vraag|regel|krijg|kom)|uitzondering(en)?|"
    r"combinatiewedstrijd(en)?|hoger start\w*)\b",
    re.IGNORECASE,
)
# Onderwerpen die een echte (reglement)vraag zijn, geen kale lookup.
_REGELMENT_ONDERWERP = re.compile(
    r"\b(wedstrijd|nk|meedoen|deelnemen|inschrijf|verzekerd|verzekering|"
    r"contributie|zmc|mnc|training|kalender|starttijd|dispensatie|"
    r"ranglijst|kwalificatie)\b",
    re.IGNORECASE,
)
_CATEGORIE_VRAAG = re.compile(
    r"(in welke|welke|in welk|waarin)\s+(leeftijds)?categorie"
    r"|wat\s+is\s+(?:(?:de|een)\s+)?(?:leeftijds)?categorie\b"
    r"|categorie\s+(rijdt|valt|hoort)"
    r"|rijdt\s+in\s+(een\s+|de\s+)?categorie"
    r"|hoort\s+bij\s+(een\s+|de\s+)?categorie",
    re.IGNORECASE,
)
_LICENTIE_MENTION = re.compile(r"\blicentie", re.IGNORECASE)
_VRAAG_WOORD = re.compile(
    r"\b(welke|welk|wlke|wlk|wat|hoe|hoeveel|heeft|heb|nodig|aanvragen|krijg|krijgt)\b",
    re.IGNORECASE,
)
_VERZET_VRAAG = re.compile(
    r"verzet|tandwiel|versnelling|rollout|afgerolde\s+afstand", re.IGNORECASE
)
# Fietsgegevens (50/34, 11-28, 28-622, kettingblad) of een vraag om het verzet van
# de fiets te controleren of aan te passen: dat is geen kale grens-lookup (#150).
_FIETSGEGEVENS = re.compile(
    r"\b\d{2}\s*[/x×]\s*\d{2}\b"
    r"|\b(?:9|1[0-6])\s*-\s*(?:2\d|[3-5]\d)\b"
    r"|\b\d{2}\s*-\s*(?:406|507|520|540|559|584|622)\b"
    r"|\b(?:kettingbla(?:d|den)|voorbla(?:d|den)|cassette|tandkrans\w*|kransje\w*|bandenmaat|etrto)\b",
    re.IGNORECASE,
)
_VERZET_CONTROLE = re.compile(
    r"\bcontrol\w*|\bnakij\w*|\baanpas\w*|\bpast\s+(?:mijn|het|de)\b"
    r"|\bmag\s+(?:mijn|de)\s+fiets\b|\bte\s+zwaar\b",
    re.IGNORECASE,
)


def _is_verzet_question(text: str) -> bool:
    return bool(_VERZET_VRAAG.search(text) and (_VRAAG_WOORD.search(text) or "?" in text))


def _asks_only_verzet(text: str) -> bool:
    """Een gecombineerde vraag (categorie, licentie) blijft kaal: daar is het verzet bijzaak."""
    return (
        _is_verzet_question(text)
        and not _CATEGORIE_VRAAG.search(text)
        and not _LICENTIE_MENTION.search(text)
    )


def _is_verzet_check(text: str) -> bool:
    return bool(
        _FIETSGEGEVENS.search(text)
        or (_VERZET_CONTROLE.search(text) and re.search(r"verzet|fiets", text, re.IGNORECASE))
    )


_VERTALING_VRAAG = re.compile(
    r"wat\s+(is|betekent)|hoe\s+heet|betekenis|vertaling|nieuwe\s+aanduiding"
    r"|hoe\s+heet\s+.*\s+nu|omgerekend|in\s+de\s+nieuwe",
    re.IGNORECASE,
)
_NEW_CATEGORY_PATTERN = re.compile(r"\b(JO|MO|MU|VU|U)(\d{1,2})\b", re.IGNORECASE)
_CATEGORY_FRAGMENT_PATTERN = re.compile(
    r"(?:JO|MO|MU|VU|U)\d{1,2}"
    r"(?:\s*(?:/|,|&|\ben\b)\s*(?:JO|MO|MU|VU|U)\d{1,2})*",
    re.IGNORECASE,
)
_OLD_DESIGNATION_REQUEST = re.compile(r"\b(categorie(?:ën|en)?|oude\s+indeling)\b", re.IGNORECASE)
_DISCIPLINE_PATTERNS = [
    ("veld", re.compile(r"\b(veldrijden|veldrit|in het veld|het veld|veld|cross)\b", re.IGNORECASE)),
    ("weg", re.compile(r"\b(wegwielrennen|op de weg|de weg|weg)\b", re.IGNORECASE)),
]
_BUITEN_SCOPE_DISCIPLINE = re.compile(
    r"\b(baanwielrennen|baanrennen|baan|mountainbik\w*|mtb|bmx)\b", re.IGNORECASE
)
_MULTIPLE_RIDERS = re.compile(
    r"\b(?:twee|beide|allebei|meerdere|kinderen|renners)\b"
    r"|\b(?:zoon|dochter|kind)\s+en\s+(?:zoon|dochter|kind)\b",
    re.IGNORECASE,
)
# Een bericht dat alleen uit lookup-gegevens bestaat, bv. "jongen uit 2015, U12, weg" (#102/#125).
_DATA_TOKEN = (
    r"(?:(?:een|mijn)\s+)?(?:jongens?|meisjes?|zoon|dochter)"
    r"|(?:(?:uit|geboren(?:\s+in)?|geboortejaar)\s+)?(?:19|20)\d{2}"
    r"|(?:categorie|cat\.?)\s*\d+"
    rf"|{_CATEGORY_FRAGMENT_PATTERN.pattern}"
    r"|op\s+de\s+weg|in\s+het\s+veld|wegwielrennen|veldrijden|veldrit|weg|veld|cross"
)
_DATA_ONLY_MESSAGE = re.compile(
    rf"\s*(?:{_DATA_TOKEN})(?:(?:\s*,\s*|\s+en\s+|\s+)(?:{_DATA_TOKEN}))*\s*[.?!]*\s*",
    re.IGNORECASE,
)
_DATA_PRIMARY_INPUT = re.compile(
    rf"\b(?:19|20)\d{{2}}\b|\b(?:categorie|cat\.?)\s*\d+|{_CATEGORY_FRAGMENT_PATTERN.pattern}",
    re.IGNORECASE,
)

# Slotvraag aan het eind van elk deterministisch antwoord (#91 besluit 4, #135):
# dit is het kale feit; wie meer wil weten, krijgt het aanbod om de
# KNWU-documenten te doorzoeken. Een vervolgvraag gaat naar de inhoudelijke route.
_DISCLAIMER_LIBRARY = (
    "Moet ik de KNWU-documenten doorzoeken voor een gedetailleerder antwoord?"
)
# Aanbod bij een initiële verzetvraag; vervangt dan de slotvraag hierboven, zodat
# een "ja" maar één betekenis heeft (#150).
VERZET_OFFER = "Heb je hulp nodig bij het controleren of aanpassen van het verzet van je fiets?"
_POSITIVE_REPLY = re.compile(
    r"\s*(?:ja|jazeker|graag|ok|oke|oké|okay|prima|doe\s+maar)"
    r"(?:[\s,!.]+(?:ja|graag|hoor|alsjeblieft|alstublieft|doe\s+maar|bedankt|dankjewel))*[\s.!]*",
    re.IGNORECASE,
)

_Gender = knwu_categories.Gender
_SupportedDiscipline = Literal["weg", "veld"]


@dataclass(frozen=True)
class _BirthYearSelector:
    kind: Literal["birth_year"]
    birth_year: int


@dataclass(frozen=True)
class _CategoryMember:
    gender: _Gender | None
    category: str


@dataclass(frozen=True)
class _CategorySelector:
    kind: Literal["category"]
    members: tuple[_CategoryMember, ...]


@dataclass(frozen=True)
class _OldCategorySelector:
    kind: Literal["old_category"]
    number: int
    members: tuple[_CategoryMember, ...]


@dataclass(frozen=True)
class _StandaloneLicenceSelector:
    kind: Literal["standalone_licence"]
    name: Literal["KNWU Licentie 17+"]


_PrimarySelector: TypeAlias = (
    _BirthYearSelector
    | _CategorySelector
    | _OldCategorySelector
    | _StandaloneLicenceSelector
)


@dataclass(frozen=True)
class _LookupProfile:
    selector: _PrimarySelector | None
    gender: _Gender | None
    discipline: _SupportedDiscipline | None
    category_filter: tuple[tuple[_CategoryMember, ...], ...] = ()
    verzet_question: bool = False


@dataclass(frozen=True)
class NoLookupState:
    kind: Literal["none"] = "none"


@dataclass(frozen=True)
class _PendingLookupState:
    kind: Literal["pending"] = "pending"
    profile: _LookupProfile = _LookupProfile(None, None, None)


@dataclass(frozen=True)
class VerzetOffer:
    """De wegrijen-feiten van een bypass-antwoord waarop de gebruiker kan ingaan (#150)."""

    rows: tuple["_AnswerRow", ...]
    gearing: knwu_categories.SourceFact


@dataclass(frozen=True)
class _CompletedLookupState:
    kind: Literal["completed"] = "completed"
    profile: _LookupProfile = _LookupProfile(None, None, None)
    offer: VerzetOffer | None = None


LookupState: TypeAlias = NoLookupState | _PendingLookupState | _CompletedLookupState


@dataclass(frozen=True)
class _InputEvidence:
    explicit_birth_years: tuple[int, ...] = ()
    contains_age: bool = False
    requires_intake: bool = False


@dataclass(frozen=True)
class _Season:
    discipline: _SupportedDiscipline
    start_year: int
    end_year: int
    reference_year: int


@dataclass(frozen=True)
class _LicenceFact:
    name: str
    period: str | None = None


@dataclass(frozen=True)
class _AnswerRow:
    season: _Season
    gender: _Gender
    category: str
    birth_year: int
    old_category: int | None
    gear: float | str | None
    licences: tuple[_LicenceFact, ...]


@dataclass(frozen=True)
class _ReadyLookup:
    selector: _PrimarySelector
    profile: _LookupProfile
    heading: str
    rows: tuple[_AnswerRow, ...]
    sources: knwu_categories.RuleSources
    outside_youth_birth_year: int | None = None
    offer: VerzetOffer | None = None


@dataclass(frozen=True)
class ReadyForBypass:
    kind: Literal["ready_for_bypass"]
    ready: _ReadyLookup
    next_state: _CompletedLookupState


@dataclass(frozen=True)
class NeedsInputForBypass:
    kind: Literal["needs_input_for_bypass"]
    next_state: _PendingLookupState
    evidence: _InputEvidence = _InputEvidence()


@dataclass(frozen=True)
class NotEligibleForBypass:
    kind: Literal["not_eligible_for_bypass"]
    next_state: NoLookupState


BypassDecision: TypeAlias = ReadyForBypass | NeedsInputForBypass | NotEligibleForBypass


@dataclass(frozen=True)
class _ParsedTurn:
    eligible_for_bypass: bool
    profile: _LookupProfile
    evidence: _InputEvidence = _InputEvidence()


@dataclass(frozen=True)
class _TurnShape:
    is_complete_question: bool
    is_fragment: bool
    old_category_fragment: bool
    data_only: bool = False


@dataclass(frozen=True)
class _CategoryInputs:
    members: tuple[_CategoryMember, ...]
    old_number: int | None
    old_members: tuple[_CategoryMember, ...]


@dataclass(frozen=True)
class _ParsedInputs:
    profile: _LookupProfile
    evidence: _InputEvidence


def _supported_seasons(today: date) -> tuple[_Season, _Season]:
    year = today.year
    if today.month <= 2:
        return (
            _Season("veld", year - 1, year, year),
            _Season("weg", year, year, year),
        )
    if today.month <= 9:
        return (
            _Season("weg", year, year, year),
            _Season("veld", year, year + 1, year + 1),
        )
    return (
        _Season("veld", year, year + 1, year + 1),
        _Season("weg", year + 1, year + 1, year + 1),
    )


def _gender_in_message(message: str) -> _Gender | None:
    boys = re.search(r"\b(jongen(?:s)?|zoon)\b", message, re.IGNORECASE) is not None
    girls = re.search(r"\b(meisje(?:s)?|dochter)\b", message, re.IGNORECASE) is not None
    if boys == girls:
        return None
    return "jongens" if boys else "meisjes"


def _discipline_in_message(message: str) -> tuple[_SupportedDiscipline | None, bool]:
    selected: list[_SupportedDiscipline] = []
    for discipline, pattern in _DISCIPLINE_PATTERNS:
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
    if _BUITEN_SCOPE_DISCIPLINE.search(message):
        return None, True
    return None, False


def _category_members(message: str, rules: dict) -> tuple[_CategoryMember, ...] | None:
    members: list[_CategoryMember] = []
    for match in _NEW_CATEGORY_PATTERN.finditer(message):
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
        gender: _Gender | None = None
        if prefix.upper() in ("JO", "MU"):
            gender = "jongens"
        elif prefix.upper() in ("MO", "VU"):
            gender = "meisjes"
        member = _CategoryMember(gender, category)
        if member not in members:
            members.append(member)
    return tuple(members)


def _old_category_members(number: int, rules: dict) -> tuple[_CategoryMember, ...] | None:
    groups = knwu_categories.old_category_groups(number, rules)
    if not groups:
        return None
    members: list[_CategoryMember] = []
    for group in groups:
        for gender in ("jongens", "meisjes"):
            under = group.get(gender)
            if under is None:
                continue
            category = knwu_categories.category_name(under, rules)
            if category is None:
                return None
            members.append(_CategoryMember(gender, category))
    return tuple(members)


def _turn_shape(text: str) -> _TurnShape:
    licence_question = bool(_LICENTIE_MENTION.search(text) and _VRAAG_WOORD.search(text))
    verzet_question = _is_verzet_question(text)
    old_category_fragment = bool(
        message_recognition.has_old_category_fragment(text.rstrip(".?!"))
    )
    category_fragment = bool(_CATEGORY_FRAGMENT_PATTERN.fullmatch(text.rstrip(".?!")))
    data_only = bool(_DATA_ONLY_MESSAGE.fullmatch(text) and _DATA_PRIMARY_INPUT.search(text))
    translation_question = bool(
        _VERTALING_VRAAG.search(text)
        and (
            _NEW_CATEGORY_PATTERN.search(text)
            or message_recognition.has_calendar_categories(text)
            or message_recognition.has_nieuweling_mention(text)
            or message_recognition.old_category_numbers(text)
        )
    )
    is_complete_question = bool(
        _CATEGORIE_VRAAG.search(text)
        or licence_question
        or verzet_question
        or translation_question
        or (_OLD_DESIGNATION_REQUEST.search(text) and not old_category_fragment)
        or (
            message_recognition.old_category_numbers(text)
            and not old_category_fragment
        )
        or (
            message_recognition.has_calendar_categories(text)
            and not category_fragment
        )
        or data_only
    )
    is_fragment = bool(
        message_recognition.is_bare_year_message(text)
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
        or data_only
    )
    return _TurnShape(
        is_complete_question,
        is_fragment,
        old_category_fragment,
        data_only,
    )


def _parse_category_inputs(text: str, rules: dict) -> _CategoryInputs | None:
    members = _category_members(text, rules)
    if members is None:
        return None
    old_numbers = message_recognition.old_category_numbers(text)
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
) -> _InputEvidence | None:
    explicit_years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    if message_recognition.is_bare_year_message(text) or shape.data_only:
        birth_years = list(dict.fromkeys(int(year) for year in explicit_years))
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
    if len(birth_years) > 1 or message_recognition.find_ages_in_years(text):
        return None
    unmatched_years = [
        int(year) for year in explicit_years if int(year) not in birth_years
    ]
    if not unmatched_years:
        return _InputEvidence(tuple(birth_years))
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
        return _InputEvidence(tuple(unmatched_years), requires_intake=True)
    return None


def _selector_from_inputs(
    text: str, evidence: _InputEvidence, category_inputs: _CategoryInputs, rules: dict
) -> tuple[_PrimarySelector | None, tuple[tuple[_CategoryMember, ...], ...]] | None:
    selector: _PrimarySelector | None = None
    category_filter: tuple[tuple[_CategoryMember, ...], ...] = ()
    if evidence.explicit_birth_years and not evidence.requires_intake:
        selector = _BirthYearSelector("birth_year", evidence.explicit_birth_years[0])
        if category_inputs.members:
            category_filter += (category_inputs.members,)
        if category_inputs.old_members:
            category_filter += (category_inputs.old_members,)
    elif category_inputs.old_number is not None:
        selector = _OldCategorySelector(
            "old_category", category_inputs.old_number, category_inputs.old_members
        )
        if category_inputs.members:
            category_filter = (category_inputs.members,)
    elif category_inputs.members:
        selector = _CategorySelector("category", category_inputs.members)
    elif (
        re.search(r"\blicentie\s+17\s*\+", text, re.IGNORECASE)
        and _VRAAG_WOORD.search(text)
    ):
        selector = _StandaloneLicenceSelector("standalone_licence", "KNWU Licentie 17+")
    elif re.search(r"\bnieuweling(?:en)?\b", text, re.IGNORECASE):
        category = knwu_categories.category_name(17, rules)
        if category is not None:
            selector = _CategorySelector("category", (_CategoryMember(None, category),))
    if evidence.requires_intake and selector is not None:
        return None
    return selector, category_filter


def _explicit_attributes(text: str) -> tuple[_Gender | None, _SupportedDiscipline | None] | None:
    if (
        _MEER_DAN_FEIT.search(text)
        or _REGELMENT_ONDERWERP.search(text)
        or _BUITEN_SCOPE_DISCIPLINE.search(text)
        or _MULTIPLE_RIDERS.search(text)
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

    profile = _LookupProfile(
        selector=selector,
        gender=gender or (
            selector.members[0].gender
            if isinstance(selector, _CategorySelector) and len(selector.members) == 1
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
) -> _LookupProfile:
    if not shape.is_fragment or not isinstance(
        previous_state, (_PendingLookupState, _CompletedLookupState)
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
            and isinstance(selector, _CategorySelector)
            and len(selector.members) == 1
            and selector.members[0].gender is not None
        ):
            selector = _CategorySelector(
                "category", (_CategoryMember(None, selector.members[0].category),)
            )
    elif gender is None:
        gender = base.gender
    return _LookupProfile(selector, gender, discipline, category_filter)


def _parse_lookup_turn(
    message: str, rules: dict, previous_state: LookupState, is_first_turn: bool
) -> _ParsedTurn:
    text = message.strip()
    empty_profile = _LookupProfile(None, None, None)
    shape = _turn_shape(text)
    if _is_verzet_check(text):
        return _ParsedTurn(False, empty_profile)
    explicit_inputs = _parse_explicit_inputs(text, rules, shape)
    if explicit_inputs is None:
        return _ParsedTurn(False, empty_profile)

    # #143: een los gegeven ("2014", "2014, meisje", "categorie 3") is een
    # vervolgbericht; zonder open of voltooide lookup hoort het bij de vorige
    # (inhoudelijke) beurt en is het alleen als eerste beurt een eigen lookup.
    standalone_data = bool(
        message_recognition.is_bare_year_message(text)
        or shape.old_category_fragment
        or shape.data_only
    )
    lookup_in_progress = isinstance(previous_state, (_PendingLookupState, _CompletedLookupState))
    eligible_for_bypass = bool(
        (standalone_data and is_first_turn)
        or (shape.is_complete_question and not shape.data_only)
        or (shape.is_fragment and lookup_in_progress)
    )
    if not eligible_for_bypass:
        return _ParsedTurn(False, empty_profile)
    profile = _apply_followup(explicit_inputs, text, shape, previous_state)
    inherited = (
        shape.is_fragment
        and isinstance(previous_state, (_PendingLookupState, _CompletedLookupState))
        and previous_state.profile.verzet_question
    )
    profile = replace(profile, verzet_question=_asks_only_verzet(text) or inherited)
    return _ParsedTurn(True, profile, explicit_inputs.evidence)


def _season_label(season: _Season) -> str:
    if season.discipline == "veld":
        return f"Veldrijden {season.start_year}-{season.end_year}"
    return f"Wegwielrennen {season.reference_year}"


def _licences_for_season(birth_year: int, season: _Season, rules: dict) -> tuple[_LicenceFact, ...]:
    start_name = knwu_categories.licence(birth_year, season.start_year, rules)
    end_name = knwu_categories.licence(birth_year, season.end_year, rules)
    if start_name == end_name:
        return (_LicenceFact(start_name),) if start_name else ()
    facts: list[_LicenceFact] = []
    if start_name:
        facts.append(_LicenceFact(start_name, f"t/m dec {season.start_year}"))
    if end_name:
        facts.append(_LicenceFact(end_name, f"vanaf jan {season.end_year}"))
    return tuple(facts)


def _members_for_profile(profile: _LookupProfile) -> tuple[_CategoryMember, ...]:
    selector = profile.selector
    if isinstance(selector, _CategorySelector):
        return selector.members
    if isinstance(selector, _OldCategorySelector):
        return selector.members
    return ()


def _candidate_birth_years(
    selector: _PrimarySelector,
    season: _Season,
    members: tuple[_CategoryMember, ...],
    rules: dict,
) -> tuple[int, ...]:
    if isinstance(selector, _BirthYearSelector):
        return (selector.birth_year,)
    return tuple(
        season.reference_year - age
        for member in members
        for age in knwu_categories.ages_for_category(member.category, rules)
    )


def _matches_category_constraints(
    profile: _LookupProfile,
    category_members: tuple[_CategoryMember, ...],
    category: str,
    gender: _Gender,
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
    profile: _LookupProfile, season: _Season, genders: tuple[_Gender, ...], rules: dict
) -> list[_AnswerRow]:
    selector = profile.selector
    if selector is None:
        return []
    category_members = _members_for_profile(profile)
    rows: list[_AnswerRow] = []
    seen: set[tuple[_Gender, str, int]] = set()
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
                _AnswerRow(
                    season=season,
                    gender=gender,
                    category=category,
                    birth_year=birth_year,
                    old_category=knwu_categories.old_category_number(
                        gender, category, rules
                    ),
                    gear=knwu_categories.max_gear(category, season.discipline, gender, rules),
                    licences=_licences_for_season(birth_year, season, rules),
                )
            )
    return rows


def _calculate_rows(profile: _LookupProfile, today: date, rules: dict) -> tuple[_AnswerRow, ...]:
    if profile.selector is None or isinstance(profile.selector, _StandaloneLicenceSelector):
        return ()
    seasons = _supported_seasons(today)
    disciplines = (profile.discipline,) if profile.discipline else ("weg", "veld")
    genders: tuple[_Gender, ...] = (
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


def _heading_for(profile: _LookupProfile, rules: dict) -> str:
    selector = profile.selector
    if isinstance(selector, _BirthYearSelector):
        return f"Geboortejaar {selector.birth_year}"
    if isinstance(selector, _OldCategorySelector):
        last_group = (knwu_categories.old_category_groups(selector.number, rules) or [])[-1]
        notation = knwu_categories.combined_notation(last_group.get("jongens"), last_group.get("meisjes"))
        return f"Oude cat. {selector.number} ({notation})"
    if isinstance(selector, _StandaloneLicenceSelector):
        return selector.name
    if isinstance(selector, _CategorySelector):
        if len(selector.members) == 2 and all(member.gender for member in selector.members):
            boys = next(member for member in selector.members if member.gender == "jongens")
            girls = next(member for member in selector.members if member.gender == "meisjes")
            notation = knwu_categories.combined_notation(
                knwu_categories.category_under(boys.category),
                knwu_categories.category_under(girls.category),
            )
            return notation
        member = selector.members[0]
        if member.gender:
            prefix = "JO" if member.gender == "jongens" else "MO"
            under = knwu_categories.category_under(member.category)
            return f"{prefix}{under}"
        return member.category
    return "Overzicht"


def _gear_text(value: float | str | None) -> str:
    if value == "vrij":
        return "vrij"
    if value is None:
        return "NVT (niet van toepassing)"
    return f"{value:.2f}".replace(".", ",") + " meter"


def _render_standalone_licence(
    selector: _StandaloneLicenceSelector,
    source: knwu_categories.SourceFact,
    level: str,
) -> str:
    article = f" (artikel {source.article})" if level == "B2" else ""
    answer = (
        f"**{selector.name}**\n\n"
        f"- **Licentie:** {selector.name}\n\n"
        f"{_DISCLAIMER_LIBRARY}"
    )
    if level == "B2":
        answer += f"\n\nBron: {source.name}, versie {source.version}{article}"
    return answer


def _render_row(ready: _ReadyLookup, row: _AnswerRow) -> list[str]:
    title = f"### {_season_label(row.season)} · {row.gender.capitalize()}"
    if isinstance(ready.selector, _CategorySelector | _OldCategorySelector):
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


def _render_source_line(sources: knwu_categories.RuleSources, level: str) -> str:
    articles_per_document: dict[tuple[str, str | None], list[str]] = {}
    for fact in (sources.age_categories, sources.gearing, sources.licences):
        articles = articles_per_document.setdefault((fact.name, fact.version), [])
        if fact.article and fact.article not in articles:
            articles.append(fact.article)
    parts = []
    for (name, version), articles in articles_per_document.items():
        part = f"{name}, versie {version}"
        if level == "B2" and articles:
            part += " (" + " en ".join(f"artikel {article}" for article in articles) + ")"
        parts.append(part)
    parts.append(f"{sources.old_categories.name}")
    return "Bron: " + "; ".join(parts)


def _render_ready(ready: _ReadyLookup, language_level: str) -> str:
    level = context.normalize_language_level(language_level)
    if isinstance(ready.selector, _StandaloneLicenceSelector):
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
            VERZET_OFFER if ready.offer else _DISCLAIMER_LIBRARY,
        ]
    )
    if level == "B2":
        lines.extend(["", _render_source_line(ready.sources, level)])
    return "\n".join(lines)


def _decide_profile(profile: _LookupProfile, today: date, rules: dict) -> BypassDecision:
    selector = profile.selector
    if selector is None:
        return NotEligibleForBypass("not_eligible_for_bypass", NoLookupState())
    if isinstance(selector, _BirthYearSelector) and selector.birth_year > today.year:
        return NotEligibleForBypass("not_eligible_for_bypass", NoLookupState())

    rows = _calculate_rows(profile, today, rules)
    outside_youth = None
    if (
        not rows
        and isinstance(selector, _BirthYearSelector)
        and not profile.category_filter
        and knwu_categories.age_category(selector.birth_year, today.year, rules) is None
        and knwu_categories.licence(selector.birth_year, today.year, rules) is None
    ):
        outside_youth = selector.birth_year
    is_standalone_license = isinstance(selector, _StandaloneLicenceSelector)
    if not rows and outside_youth is None and not is_standalone_license:
        return NotEligibleForBypass("not_eligible_for_bypass", NoLookupState())

    sources = knwu_categories.sources(rules)
    ready = _ReadyLookup(
        selector=selector,
        profile=profile,
        heading=_heading_for(profile, rules),
        rows=rows,
        sources=sources,
        outside_youth_birth_year=outside_youth,
        offer=_verzet_offer(profile, rows, sources),
    )
    return ReadyForBypass(
        "ready_for_bypass", ready, _CompletedLookupState(profile=profile, offer=ready.offer)
    )


def _verzet_offer(
    profile: _LookupProfile, rows: tuple[_AnswerRow, ...], sources: knwu_categories.RuleSources
) -> VerzetOffer | None:
    """Alleen bij een verzetvraag en alleen met wegwielrennen: bij veldrijden is het verzet vrij."""
    if not profile.verzet_question:
        return None
    road_rows = tuple(
        row for row in rows if row.season.discipline == "weg" and isinstance(row.gear, float)
    )
    return VerzetOffer(road_rows, sources.gearing) if road_rows else None


def accepted_verzet_offer(message: str, previous_state: LookupState | None) -> VerzetOffer | None:
    """Het aanbod uit het vorige bypass-antwoord, als dit bericht er positief op ingaat."""
    if not isinstance(previous_state, _CompletedLookupState) or previous_state.offer is None:
        return None
    return previous_state.offer if _POSITIVE_REPLY.fullmatch(message) else None


def verzet_offer_context(offer: VerzetOffer) -> list[str]:
    """Contextregels voor de verzet-agent: geboortejaar, geslacht, categorie, grens, bron en versie."""
    source = offer.gearing
    article = f", artikel {source.article}" if source.article else ""
    return [
        f"Gegevens uit het bypass-antwoord, berekend door de app uit {source.name} "
        f"(versie {source.version}{article}): geboortejaar {row.birth_year}, {row.gender}, "
        f"categorie {row.category}, maximaal toegestaan verzet wegwielrennen "
        f"{_gear_text(row.gear)}."
        for row in offer.rows
    ]


def recognize_turn(
    message: str,
    previous_state: LookupState | None,
    today: date,
    rules: dict,
    *,
    is_first_turn: bool,
) -> BypassDecision:
    """Recognize, validate and calculate a deterministic lookup without side effects.

    `is_first_turn`: this is the first accepted turn of the conversation.
    """
    state = previous_state or NoLookupState()
    parsed = _parse_lookup_turn(message, rules, state, is_first_turn)
    if not parsed.eligible_for_bypass:
        return NotEligibleForBypass("not_eligible_for_bypass", NoLookupState())
    if parsed.profile.selector is None:
        pending = _PendingLookupState(profile=parsed.profile)
        return NeedsInputForBypass("needs_input_for_bypass", pending, parsed.evidence)
    return _decide_profile(parsed.profile, today, rules)


def complete_with_intake(
    needs_input: NeedsInputForBypass,
    intake_result: dict[str, object],
    today: date,
    rules: dict,
) -> BypassDecision:
    """Complete only a recognized pending lookup with explicit intake facts."""
    if not isinstance(needs_input, NeedsInputForBypass):
        raise TypeError(
            "complete_with_intake requires a NeedsInputForBypass decision; "
            "answer ReadyForBypass directly and route NotEligibleForBypass without intake completion"
        )
    profile = needs_input.next_state.profile
    year = intake_result.get("geboortejaar")
    age = intake_result.get("leeftijd")
    evidence = needs_input.evidence
    grounded_year = evidence.requires_intake and year in evidence.explicit_birth_years
    if (
        profile.selector is None
        and not evidence.contains_age
        and age is None
        and grounded_year
        and isinstance(year, int)
        and not isinstance(year, bool)
    ):
        profile = replace(profile, selector=_BirthYearSelector("birth_year", year))
    if profile.selector is None:
        return NeedsInputForBypass(
            "needs_input_for_bypass", _PendingLookupState(profile=profile), needs_input.evidence
        )
    return _decide_profile(profile, today, rules)


def render_answer(ready: ReadyForBypass, language_level: str) -> str:
    """Render validated answer facts without reading or interpreting user text."""
    if not isinstance(ready, ReadyForBypass):
        raise TypeError(
            "render_answer requires a ReadyForBypass decision; "
            "route NeedsInputForBypass and NotEligibleForBypass through intake.decide_route"
        )
    return _render_ready(ready.ready, language_level)
