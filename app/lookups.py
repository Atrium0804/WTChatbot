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
from datetime import date

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

# Disclaimer aan het eind van elk deterministisch antwoord (#91 besluit 4):
# dit is het kale feit; bij een vervolgvraag ("waarom", versie, "heb je dit
# gecheckt") schakelt de app door naar de document-library.
DISCLAIMER_LIBRARY = (
    "Stel je een vervolgvraag, dan fiets ik met je "
    "door de KNWU-informatie"
)


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
