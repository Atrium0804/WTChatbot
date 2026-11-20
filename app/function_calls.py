"""Function calls van de Mistral-agents uitvoeren in de app (#149, ADR-0010).

`execute` voert één function call uit; `run_turn` herhaalt het gesprek met
Mistral tot de agent een antwoord geeft. Elke fout gaat als toolresultaat
`{"error": ...}` terug naar de agent, zodat die de gebruiker kan bijsturen.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

import verzet_advies
from mistral_client import FunctionCall, Inputs

logger = logging.getLogger(__name__)

BEREKEN_VERZET = "bereken_verzet"
KNOWN_FUNCTIONS = frozenset({BEREKEN_VERZET})
MAX_CALLS_PER_TURN = 3
# Na de limiet krijgt elke call een limietfout; dit begrenst het aantal rondes.
MAX_ROUNDS_PER_TURN = MAX_CALLS_PER_TURN + 3

# execute valideert de argumenten tegen dit schema; de verzet-agent krijgt
# hetzelfde schema als tool (#151).
BEREKEN_VERZET_TOOL = {
    "type": "function",
    "function": {
        "name": BEREKEN_VERZET,
        "description": (
            "Berekent het verzet van een fiets voor wegwielrennen: wielomtrek, zwaarste en "
            "lichtste verzet, bereik, topsnelheid en het maximaal toegestane verzet voor de "
            "leeftijdscategorie, met een kettingbladadvies, cassetteadvies en "
            "reguliere-cassetteadvies."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "birth_year": {"type": "integer", "description": "Geboortejaar van de renner."},
                "gender": {"type": "string", "enum": ["jongens", "meisjes"]},
                "chainring": {
                    "type": "integer",
                    "description": "Tanden van het buitenblad (of het enige kettingblad).",
                },
                "small_chainring": {
                    "type": "integer",
                    "description": "Tanden van het binnenblad; weglaten bij één kettingblad (1x).",
                },
                "smallest_sprocket": {
                    "type": "integer",
                    "description": "Tanden van het kleinste tandkransje van de cassette.",
                },
                "largest_sprocket": {
                    "type": "integer",
                    "description": "Tanden van het grootste tandkransje van de cassette.",
                },
                "tire_width_mm": {
                    "type": "integer",
                    "description": "Banddikte uit de ETRTO-maat, bv. 28 bij 28-622.",
                },
                "rim_diameter_mm": {
                    "type": "integer",
                    "description": "Velgdiameter uit de ETRTO-maat, bv. 622 bij 28-622.",
                },
            },
            "required": [
                "birth_year",
                "gender",
                "chainring",
                "smallest_sprocket",
                "largest_sprocket",
                "tire_width_mm",
                "rim_diameter_mm",
            ],
            "additionalProperties": False,
        },
    },
}

Status = Literal["ok", "invalid_input", "error", "limit"]


class TooManyRoundsError(RuntimeError):
    """De agent bleef function calls doen; het Mistral-gesprek wacht nog op een resultaat."""


@dataclass(frozen=True)
class Outcome:
    """Resultaat voor de agent plus een samenvatting zonder persoonsgegevens voor de trace."""

    result: str
    status: Status
    trace_input: str = ""
    trace_outcome: str = ""


def _error(message: str, status: Status, trace_input: str = "", trace_outcome: str = "") -> Outcome:
    return Outcome(
        json.dumps({"error": message}, ensure_ascii=False), status, trace_input, trace_outcome
    )


def _schema_error(arguments: dict, parameters: dict) -> tuple[str, str] | None:
    """Geef (argumentnaam, foutmelding) voor het eerste ongeldige argument."""
    properties = parameters["properties"]
    for name in arguments.keys() - properties.keys():
        return name, f"Onbekend argument '{name}'; gebruik alleen {', '.join(properties)}."
    for name in parameters["required"]:
        if arguments.get(name) is None:
            return name, f"Argument '{name}' ontbreekt."
    for name, value in arguments.items():
        spec = properties[name]
        if value is None and name not in parameters["required"]:
            continue
        if spec["type"] == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return name, f"Argument '{name}' moet een geheel getal zijn, niet {value!r}."
        if spec["type"] == "string" and not isinstance(value, str):
            return name, f"Argument '{name}' moet tekst zijn, niet {value!r}."
        if "enum" in spec and value not in spec["enum"]:
            return name, (
                f"Argument '{name}' moet een van {', '.join(spec['enum'])} zijn, niet {value!r}."
            )
    return None


def _setup_summary(arguments: dict) -> str:
    """Bv. "50/34 11-28 28-622"; zonder geboortejaar en geslacht."""
    chainrings = str(arguments["chainring"])
    if arguments.get("small_chainring") is not None:
        chainrings += f"/{arguments['small_chainring']}"
    return (
        f"{chainrings} {arguments['smallest_sprocket']}-{arguments['largest_sprocket']} "
        f"{arguments['tire_width_mm']}-{arguments['rim_diameter_mm']}"
    )


def _bereken_verzet(arguments: dict, year: int, rules: dict) -> Outcome:
    error = _schema_error(arguments, BEREKEN_VERZET_TOOL["function"]["parameters"])
    if error:
        name, message = error
        return _error(message, "invalid_input", trace_outcome=f"ongeldig argument: {name}")
    summary = _setup_summary(arguments)
    advice = verzet_advies.advise(**arguments, year=year, rules=rules)
    if isinstance(advice, verzet_advies.InvalidInput):
        scrubbed = advice.message.replace(str(arguments["birth_year"]), "[geboortejaar]")
        return _error(advice.message, "invalid_input", summary, scrubbed)
    verdict = "toegestaan" if advice.current.within_limit else "te zwaar"
    return Outcome(
        json.dumps({"discipline": "weg", **asdict(advice)}, ensure_ascii=False),
        "ok",
        summary,
        f"{advice.category} max {advice.limit_m} m: {advice.current.heaviest_gear_m} m {verdict}",
    )


def execute(call: FunctionCall, *, year: int, rules: dict) -> Outcome:
    """Voer één function call uit; fouten komen terug als `{"error": ...}`."""
    if call.name != BEREKEN_VERZET:
        return _error(f"Onbekende functie '{call.name}'.", "error")
    try:
        arguments = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        return _error("De argumenten zijn geen geldige JSON.", "invalid_input")
    if not isinstance(arguments, dict):
        return _error("De argumenten moeten een JSON-object zijn.", "invalid_input")
    try:
        return _bereken_verzet(arguments, year, rules)
    except Exception:
        logger.exception("bereken_verzet faalde onverwacht")
        return _error("De berekening is mislukt door een fout in de app.", "error")


Send = Callable[[Inputs, str | None, Callable[[FunctionCall], None]], tuple[str, str]]


def run_turn(
    *,
    send: Send,
    message: str,
    conversation_id: str | None,
    execute: Callable[[FunctionCall], Outcome],
    on_outcome: Callable[[FunctionCall, Outcome], None],
) -> tuple[str, str]:
    """Eén gebruikersbeurt: stuur het bericht en beantwoord function calls tot de agent antwoordt.

    `send(inputs, conversation_id, on_function_call)` geeft (conversation_id,
    tekst). Hooguit MAX_CALLS_PER_TURN calls worden uitgevoerd; latere calls
    krijgen een limietfout. Na MAX_ROUNDS_PER_TURN rondes met calls stopt de
    beurt met TooManyRoundsError.
    """
    inputs: Inputs = message
    executed = 0
    for _ in range(MAX_ROUNDS_PER_TURN):
        calls: list[FunctionCall] = []
        conversation_id, text = send(inputs, conversation_id, calls.append)
        if not calls:
            return conversation_id, text
        results = []
        for call in calls:
            if executed < MAX_CALLS_PER_TURN:
                outcome = execute(call)
                executed += 1
            else:
                outcome = _error(
                    f"Maximaal {MAX_CALLS_PER_TURN} berekeningen per beurt; "
                    "geef antwoord met de resultaten die je hebt.",
                    "limit",
                )
            on_outcome(call, outcome)
            results.append(
                {"type": "function.result", "tool_call_id": call.tool_call_id, "result": outcome.result}
            )
        inputs = results
    raise TooManyRoundsError("de agent bleef functieaanroepen doen")
