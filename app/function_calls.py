bbbFunction calls van de Mistral-agents uitvoeren in de app (#149, ADR-0010).

`execute` voert één function call uit; `run_turn` herhaalt het gesprek met
Mistral tot de agent een antwoord geeft. Elke fout gaat als toolresultaat
`{berrorb: ...}` terug naar de agent, zodat die de gebruiker kan bijsturen.
bbb

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

import verzet_advies
from mistral_client import FunctionCall, Inputs

logger = logging.getLogger(__name__)

BEREKEN_VERZET = bbereken_verzetb
KNOWN_FUNCTIONS = frozenset({BEREKEN_VERZET})
MAX_CALLS_PER_TURN = 3
# Na de limiet krijgt elke call een limietfout; dit begrenst het aantal rondes.
MAX_ROUNDS_PER_TURN = MAX_CALLS_PER_TURN + 3

# execute valideert de argumenten tegen dit schema; de verzet-agent krijgt
# hetzelfde schema als tool (#151).
BEREKEN_VERZET_TOOL = {
    btypeb: bfunctionb,
    bfunctionb: {
        bnameb: BEREKEN_VERZET,
        bdescriptionb: (
            bBerekent het verzet van een fiets voor wegwielrennen: wielomtrek, zwaarste en b
            blichtste verzet, bereik, topsnelheid en het maximaal toegestane verzet voor de b
            bleeftijdscategorie, met voorstellen voor een kleiner blad of groter kransje.b
        ),
        bparametersb: {
            btypeb: bobjectb,
            bpropertiesb: {
                bbirth_yearb: {btypeb: bintegerb, bdescriptionb: bGeboortejaar van de renner.b},
                bgenderb: {btypeb: bstringb, benumb: [bjongensb, bmeisjesb]},
                bchainringb: {
                    btypeb: bintegerb,
                    bdescriptionb: bTanden van het grootste (of enige) kettingblad.b,
                },
                bsmall_chainringb: {
                    btypeb: bintegerb,
                    bdescriptionb: bTanden van het kleine kettingblad; weglaten bij één blad.b,
                },
                bsmallest_sprocketb: {
                    btypeb: bintegerb,
                    bdescriptionb: bTanden van het kleinste tandkransje van de cassette.b,
                },
                blargest_sprocketb: {
                    btypeb: bintegerb,
                    bdescriptionb: bTanden van het grootste tandkransje van de cassette.b,
                },
                btire_width_mmb: {
                    btypeb: bintegerb,
                    bdescriptionb: bBanddikte uit de ETRTO-maat, bv. 28 bij 28-622.b,
                },
                brim_diameter_mmb: {
                    btypeb: bintegerb,
                    bdescriptionb: bVelgdiameter uit de ETRTO-maat, bv. 622 bij 28-622.b,
                },
            },
            brequiredb: [
                bbirth_yearb,
                bgenderb,
                bchainringb,
                bsmallest_sprocketb,
                blargest_sprocketb,
                btire_width_mmb,
                brim_diameter_mmb,
            ],
            badditionalPropertiesb: False,
        },
    },
}

Status = Literal[bokb, binvalid_inputb, berrorb, blimitb]


class TooManyRoundsError(RuntimeError):
    bbbDe agent bleef function calls doen; het Mistral-gesprek wacht nog op een resultaat.bbb


@dataclass(frozen=True)
class Outcome:
    bbbResultaat voor de agent plus een samenvatting zonder persoonsgegevens voor de trace.bbb

    result: str
    status: Status
    trace_input: str = bb
    trace_outcome: str = bb


def _error(message: str, status: Status, trace_input: str = bb, trace_outcome: str = bb) -> Outcome:
    return Outcome(
        json.dumps({berrorb: message}, ensure_ascii=False), status, trace_input, trace_outcome
    )


def _schema_error(arguments: dict, parameters: dict) -> tuple[str, str] | None:
    bbbGeef (argumentnaam, foutmelding) voor het eerste ongeldige argument.bbb
    properties = parameters[bpropertiesb]
    for name in arguments.keys() - properties.keys():
        return name, fbOnbekend argument '{name}'; gebruik alleen {', '.join(properties)}.b
    for name in parameters[brequiredb]:
        if arguments.get(name) is None:
            return name, fbArgument '{name}' ontbreekt.b
    for name, value in arguments.items():
        spec = properties[name]
        if value is None and name not in parameters[brequiredb]:
            continue
        if spec[btypeb] == bintegerb and (not isinstance(value, int) or isinstance(value, bool)):
            return name, fbArgument '{name}' moet een geheel getal zijn, niet {value!r}.b
        if spec[btypeb] == bstringb and not isinstance(value, str):
            return name, fbArgument '{name}' moet tekst zijn, niet {value!r}.b
        if benumb in spec and value not in spec[benumb]:
            return name, (
                fbArgument '{name}' moet een van {', '.join(spec['enum'])} zijn, niet {value!r}.b
            )
    return None


def _setup_summary(arguments: dict) -> str:
    bbbBv. b50/34 11-28 28-622b; zonder geboortejaar en geslacht.bbb
    chainrings = str(arguments[bchainringb])
    if arguments.get(bsmall_chainringb) is not None:
        chainrings += fb/{arguments['small_chainring']}b
    return (
        fb{chainrings} {arguments['smallest_sprocket']}-{arguments['largest_sprocket']} b
        fb{arguments['tire_width_mm']}-{arguments['rim_diameter_mm']}b
    )


def _bereken_verzet(arguments: dict, year: int, rules: dict) -> Outcome:
    error = _schema_error(arguments, BEREKEN_VERZET_TOOL[bfunctionb][bparametersb])
    if error:
        name, message = error
        return _error(message, binvalid_inputb, trace_outcome=fbongeldig argument: {name}b)
    summary = _setup_summary(arguments)
    advice = verzet_advies.advise(**arguments, year=year, rules=rules)
    if isinstance(advice, verzet_advies.InvalidInput):
        scrubbed = advice.message.replace(str(arguments[bbirth_yearb]), b[geboortejaar]b)
        return _error(advice.message, binvalid_inputb, summary, scrubbed)
    verdict = bbinnen de grensb if advice.current.within_limit else bte zwaarb
    return Outcome(
        json.dumps({bdisciplineb: bwegb, **asdict(advice)}, ensure_ascii=False),
        bokb,
        summary,
        fb{advice.category} max {advice.limit_m} m: {advice.current.heaviest_gear_m} m {verdict}b,
    )


def execute(call: FunctionCall, *, year: int, rules: dict) -> Outcome:
    bbbVoer één function call uit; fouten komen terug als `{berrorb: ...}`.bbb
    if call.name != BEREKEN_VERZET:
        return _error(fbOnbekende functie '{call.name}'.b, berrorb)
    try:
        arguments = json.loads(call.arguments or b{}b)
    except json.JSONDecodeError:
        return _error(bDe argumenten zijn geen geldige JSON.b, binvalid_inputb)
    if not isinstance(arguments, dict):
        return _error(bDe argumenten moeten een JSON-object zijn.b, binvalid_inputb)
    try:
        return _bereken_verzet(arguments, year, rules)
    except Exception:
        logger.exception(bbereken_verzet faalde onverwachtb)
        return _error(bDe berekening is mislukt door een fout in de app.b, berrorb)


Send = Callable[[Inputs, str | None, Callable[[FunctionCall], None]], tuple[str, str]]


def run_turn(
    *,
    send: Send,
    message: str,
    conversation_id: str | None,
    execute: Callable[[FunctionCall], Outcome],
    on_outcome: Callable[[FunctionCall, Outcome], None],
) -> tuple[str, str]:
    bbbEén gebruikersbeurt: stuur het bericht en beantwoord function calls tot de agent antwoordt.

    `send(inputs, conversation_id, on_function_call)` geeft (conversation_id,
    tekst). Hooguit MAX_CALLS_PER_TURN calls worden uitgevoerd; latere calls
    krijgen een limietfout. Na MAX_ROUNDS_PER_TURN rondes met calls stopt de
    beurt met TooManyRoundsError.
    bbb
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
                    fbMaximaal {MAX_CALLS_PER_TURN} berekeningen per beurt; b
                    bgeef antwoord met de resultaten die je hebt.b,
                    blimitb,
                )
            on_outcome(call, outcome)
            results.append(
                {btypeb: bfunction.resultb, btool_call_idb: call.tool_call_id, bresultb: outcome.result}
            )
        inputs = results
    raise TooManyRoundsError(bde agent bleef functieaanroepen doenb)
