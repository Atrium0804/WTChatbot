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
    r"toelichting|pakket|kosten|prijs|tarief|bedrag)\b",
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
CATEGORIE_AANDUIDING = re.compile(r"\bU(\d{1,2})\b", re.IGNORECASE)
DISCIPLINE_PATTERNS = [
    ("baan", re.compile(r"\b(baanwielrennen|op de baan|de baan|baan)\b", re.IGNORECASE)),
    ("veld", re.compile(r"\b(veldrijden|veldrit|in het veld|het veld|veld|cross)\b", re.IGNORECASE)),
    ("weg", re.compile(r"\b(wegwielrennen|op de weg|de weg|weg)\b", re.IGNORECASE)),
]
DISCIPLINE_NAAM = {"weg": "wegwielrennen", "veld": "veldrijden", "baan": "baanwielrennen"}


def _discipline_uit_bericht(message: str, extra: dict) -> str | None:
    discipline = extra.get("discipline")
    if discipline in DISCIPLINE_NAAM:
        return discipline
    for disc, pattern in DISCIPLINE_PATTERNS:
        if pattern.search(message):
            return disc
    return None


def _categorie_uit_bericht(message: str, rules: dict) -> str | None:
    match = CATEGORIE_AANDUIDING.search(message)
    if match:
        return knwu_categories.category_name(int(match.group(1)), rules)
    if context.NIEUWELING_PATTERN.search(message):
        return knwu_categories.category_name(17, rules)
    return None


def match_lookup(
    message: str, today: date, rules: dict, extra: dict | None = None
) -> dict | None:
    """Detecteer een pure lookup-vraag; geef de data terug, anders None.

    `extra` vult aan vanuit de light intake (#91): {"geboortejaar": int,
    "discipline": "weg"|"veld"|"baan"}. Alleen expliciete geboortejaren
    (of een kaal jaartal als antwoord op de geboortejaar-vraag) leiden
    tot een bypass — een leeftijd in jaren ("15-jarige") niet, omdat
    daarbij bronconflicten kunnen spelen die alleen een agent signaleert.
    """
    if MEER_DAN_FEIT.search(message) or REGELMENT_ONDERWERP.search(message):
        return None
    extra = extra or {}
    birth_years = context.find_birth_years(message, today, rules)
    extra_year = extra.get("geboortejaar")
    if extra_year:
        try:
            year = int(extra_year)
        except (TypeError, ValueError):
            year = 0
        if year and year not in birth_years:
            birth_years.insert(0, year)

    cat_vraag = bool(CATEGORIE_VRAAG.search(message))
    lic_vraag = bool(LICENTIE_MENTION.search(message) and VRAAG_WOORD.search(message))
    verzet_vraag = bool(VERZET_VRAAG.search(message))
    if sum((cat_vraag, lic_vraag, verzet_vraag)) > 1:
        # meerdere onderwerpen in één vraag (bv. categorie én licentie) ->
        # cross-check met bronconflict-mogelijkheid -> agent
        return None

    if verzet_vraag:
        category = _categorie_uit_bericht(message, rules)
        if not category and birth_years:
            category = knwu_categories.age_category(birth_years[0], today.year, rules)
        discipline = _discipline_uit_bericht(message, extra)
        if category and discipline:
            return {"kind": "verzet", "category": category, "discipline": discipline}
        return None  # categorie of discipline ontbreekt -> agent stelt bij

    if cat_vraag or lic_vraag:
        if birth_years:
            return {"kind": "categorie" if cat_vraag else "licentie", "birth_year": birth_years[0]}
        return None  # geen geboortejaar bekend -> agent vraagt ernaar

    bare_year = context.BIRTH_YEAR_PATTERN.search(message)
    if bare_year and context.BARE_YEAR_MESSAGE.match(message):
        return {"kind": "categorie", "birth_year": int(bare_year.group(0))}

    has_old_designation = bool(
        context.old_category_numbers(message)
        or context.NIEUWELING_PATTERN.search(message)
        or context.CALENDAR_PATTERN.search(message)
    )
    if has_old_designation and (
        VERTALING_VRAAG.search(message) or len(message.split()) <= 12
    ):
        return {"kind": "vertaling"}
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
    agent-antwoorden (#52).
    """
    level = context.normalize_language_level(language_level)
    kind = match["kind"]

    if kind == "vertaling":
        lines = context.old_designation_lines(message, rules)
        answer = "\n".join(lines) if lines else "Die aanduiding ken ik niet."
        if level == "B2":
            answer += f"\n\nBron: {rules['oude_categorie_indeling']['bron']}"
        return answer

    if kind == "verzet":
        category = match["category"]
        discipline = match["discipline"]
        gear = knwu_categories.max_gear(category, discipline, rules)
        label = f"{category} (nieuwelingen)" if "Nieuweling" in category else category
        answer = (
            f"Het maximaal toegestane verzet voor {label} bij "
            f"{DISCIPLINE_NAAM[discipline]} is {_fmt_verzet(gear)}."
        )
        if level == "B2":
            answer += (
                f"\n\nBron: {rules['verzetten']['bron']}, versie "
                f"{rules['verzetten']['versie']} (artikel {rules['verzetten']['artikel']})"
            )
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
    if level == "B2":
        answer += (
            f"\n\nBron: {rules['bron']}, versie {rules['versie']} "
            f"(artikel {rules['leeftijdscategorieen']['artikel']} voor de "
            f"leeftijdscategorie, artikel {rules['licenties']['artikel']} voor de licentie)"
        )
    return answer
