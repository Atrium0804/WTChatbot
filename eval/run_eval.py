"""Eval-runner: launch-gate van de MVP.

Leest eval/evalset.yaml, stelt per vraag een nieuwe conversation met de
bijbehorende agent via de Mistral Conversations API (zelfde agent-instructies
als productie, offline — niet tegen de draaiende bot) en checkt:

- bron: een "Bron:"-regel in het antwoord matcht (na normalisatie) de `bron`
  of één van de alternatieven ("a | b")
- kernfeiten: elk token van elk item van `verwacht_antwoord` (gescheiden
  door ";") staat los in het antwoord (getallen en korte woorden heel,
  langere woorden als woordbegin; getallen/tijden genormaliseerd)
- strikethrough: `doorhaal_waarde` (indien opgegeven) mag NIET voorkomen
- `niet_in_antwoord` (optioneel, ";"-gescheiden): geen van die woorden mag
  in het antwoord staan (zelfde tokenmatching als de kernfeiten)
- `via: router` (optioneel): de vraag gaat naar de router-agent
  (MISTRAL_AGENT_ID) in plaats van de categorie-agent, dus end-to-end met
  handoff; de vraag telt mee in de score van zijn categorie
- `verwacht_route` (optioneel, #92): assert de productie-route van de app —
  `bypass` (deterministische lookup, 0 LLM-calls), `direct-<domein>`
  (direct-to-expert via de light intake) of `router`; mismatch = FAIL
- `beurten` (optioneel): eerdere gebruikersberichten in dezelfde
  conversatie, vóór `vraag`; alleen het antwoord op `vraag` wordt gecheckt
- `verwachte_agent` (optioneel): naam van de agent die het antwoord op
  `vraag` moet geven (bv. knwu-agent); vangt een sticky handoff
- verheldering: geen bron-check; de kernfeiten (bv. geboortejaar, geslacht)
  moeten in de wedervraag van de bot staan

Elk bericht krijgt dezelfde contextregels als in productie (taalniveau per
bericht, datum bij de eerste beurt, categorie bij een geboortejaar;
app/context.py). Als datum geldt de `peildatum` uit evalset.yaml, niet de
rundatum. Het taalniveau komt uit het optionele veld `taalniveau`
per evalset-entry (default B1, de productiestandaard sinds #52). Per beurt
legt last_run.json vast welke agent antwoordde (`trace`).

Gate: globaal >= 90% en per categorie >= 90% correct met correcte bron;
type `strikethrough` en `websearch` zijn een harde 100%-gate. Resultaat
naar eval/last_run.json; exit-code 0 bij halen van de gate, anders 1.

Draai handmatig door de beheerder na elke library-update — NOOIT in CI
(geen live API-calls in CI). Zie docs/reference/eval-set.md.

Environment (uit .env in de repo-root; de file wint van shellvariabelen):
- MISTRAL_API_KEY               (verplicht)
- MISTRAL_AGENT_ID_KNWU / MISTRAL_AGENT_ID_REGIO / MISTRAL_AGENT_ID_CLUB
  (agent per categorie; fallback: MISTRAL_AGENT_ID)

Afhankelijkheden: pip install requests pyyaml python-dotenv
"""

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

EVAL_DIR = Path(__file__).parent
ENV_PATH = EVAL_DIR.parent / ".env"
sys.path.insert(0, str(EVAL_DIR.parent / "app"))

import context  # noqa: E402  (app-module: dezelfde contextregels als de proxy)
import intake  # noqa: E402  (#91: light intake, zelfde route-beslissing als de app)
import knwu_categories  # noqa: E402
import lookups  # noqa: E402  (#91: deterministische bypass, zelfde templates als de app)

API_URL = "https://api.mistral.ai/v1/conversations"
CHAT_COMPLETIONS_URL = os.environ.get(
    "MISTRAL_CHAT_COMPLETIONS_URL", "https://api.mistral.ai/v1/chat/completions"
)
INTAKE_MODEL = os.environ.get("MISTRAL_INTAKE_MODEL", "mistral-small-latest")
INTAKE_CONFIDENCE_THRESHOLD = float(os.environ.get("INTAKE_CONFIDENCE_THRESHOLD", "0.8"))
GATE_PCT = 90.0
HARD_GATE_TYPES = {"strikethrough", "websearch"}
AGENT_ENV_PREFIX = "MISTRAL_AGENT_ID"


def normalize(text: str) -> str:
    """Lowercase, decimale punt/tijd-dubbelepunt -> komma, alleen [a-z0-9,] over.

    Zo matchen "085-070 19 00" en "+31 (0)85 070 1900" beide als "0850701900",
    "artikel 20.1.007" als "artikel20,1,007" en "11:05"/"11.05" als "11,05".
    """
    lowered = text.lower().replace(".", ",").replace(":", ",")
    return re.sub(r"[^a-z0-9,]", "", lowered)


def load_evalset(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["evalset"]


def load_peildatum(path: Path) -> date:
    """De `peildatum` van de evalset: de datum waarop de verwachte antwoorden
    kloppen. Live runner en offline tests rekenen er allebei mee."""
    with path.open(encoding="utf-8") as f:
        value = yaml.safe_load(f).get("peildatum")
    if not isinstance(value, date):
        raise ValueError(f"{path.name}: 'peildatum' ontbreekt of is geen datum (JJJJ-MM-DD): {value!r}")
    return value


def agent_id_for(entry: dict) -> str:
    """Agent-id per evalvraag: `via: router` -> de router (end-to-end met
    handoff), anders de agent van de categorie (fallback: de router)."""
    categorie = entry["categorie"]
    if entry.get("via") == "router":
        key = os.environ.get("MISTRAL_AGENT_ID")
        if not key:
            raise RuntimeError(f"Geen router-id voor '{entry.get('id', categorie)}': zet MISTRAL_AGENT_ID")
        return key
    key = os.environ.get(f"MISTRAL_AGENT_ID_{categorie.upper()}") or os.environ.get(
        "MISTRAL_AGENT_ID"
    )
    if not key:
        raise RuntimeError(
            f"Geen agent-id voor categorie '{categorie}': zet "
            f"MISTRAL_AGENT_ID_{categorie.upper()} of MISTRAL_AGENT_ID"
        )
    return key


def expert_agent_ids_from_env() -> dict[str, str]:
    """Domein -> expert-agent-id uit de env (zelfde vars als de app, #88)."""
    return {
        domein: os.environ.get(f"MISTRAL_AGENT_ID_{domein.upper()}", "")
        for domein in ("knwu", "regio", "club", "archief")
    }


def plan_entry(entry: dict, api_key: str, today: date, rules: dict) -> dict:
    """Spiegel de productie-route van de app per evalvraag (#91/#92).

    Zelfde volgorde als app/main.py: eerst de deterministische lookup
    (bypass, 0 LLM-calls, geen conversation), anders `via: router` (vaste
    router-route om end-to-end handoff te testen), anders de light intake
    (1 kleine call) met decide_route -> direct-<domein> of router.
    """
    vraag = lookups.resolve_lookup_message(entry["vraag"], entry.get("beurten", []), today, rules)
    lookup = lookups.match_lookup(vraag, today, rules)
    if lookup:
        return {
            "route": "bypass", "agent_id": None, "lookup": lookup,
            "lookup_message": vraag, "intake_ms": 0.0,
        }
    if entry.get("via") == "router":
        return {
            "route": "router",
            "agent_id": os.environ.get("MISTRAL_AGENT_ID"),
            "lookup": None,
            "intake_ms": 0.0,
        }
    t0 = time.monotonic()
    intake_result = intake.classify_message(
        api_key=api_key,
        base_url=CHAT_COMPLETIONS_URL,
        model=INTAKE_MODEL,
        message=vraag,
        timeout=30,
    )
    intake_ms = round((time.monotonic() - t0) * 1000, 1)
    route = intake.decide_route(
        message=vraag,
        today=today,
        rules=rules,
        intake_result=intake_result,
        expert_agent_ids=expert_agent_ids_from_env(),
        threshold=INTAKE_CONFIDENCE_THRESHOLD,
    )
    if route["route"] == "bypass":
        return {
            "route": "bypass", "agent_id": None, "lookup": route["lookup"],
            "lookup_message": vraag, "intake_ms": intake_ms,
        }
    if route["route"] == "direct":
        return {
            "route": f"direct-{route['domein']}",
            "agent_id": route["agent_id"],
            "lookup": None,
            "intake_ms": intake_ms,
        }
    return {"route": "router", "agent_id": os.environ.get("MISTRAL_AGENT_ID"), "lookup": None, "intake_ms": intake_ms}


def extract_text(outputs: list[dict]) -> str:
    """Plak de tekst-chunks van een Conversations-antwoord aan elkaar.

    Shape van POST /v1/conversations: outputs[]-entries met
    type == "message.output" en top-level "content" (string of list of
    chunks; alleen chunks met type == "text" zijn antwoordtekst).
    """
    texts = []
    for out in outputs:
        if out.get("type") != "message.output":
            continue
        content = out.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    texts.append(chunk.get("text", ""))
    return "\n".join(texts)


def agent_names_from_env() -> dict[str, str]:
    """Agent-id -> naam uit de env-variabelen van create_agents.py:
    MISTRAL_AGENT_ID = router-agent, MISTRAL_AGENT_ID_<NAAM> = <naam>-agent."""
    names = {}
    for key, agent_id in os.environ.items():
        if not key.startswith(AGENT_ENV_PREFIX) or not agent_id:
            continue
        suffix = key[len(AGENT_ENV_PREFIX):].lstrip("_")
        names[agent_id] = f"{suffix.lower().replace('_', '-') or 'router'}-agent"
    return names


def answering_agents(outputs: list[dict], agent_names: dict[str, str]) -> list[str]:
    """Namen van de agents met een message.output in deze beurt (in volgorde)."""
    agents = []
    for out in outputs:
        if out.get("type") == "message.output":
            agent_id = out.get("agent_id") or "?"
            agents.append(agent_names.get(agent_id, agent_id))
    return agents


def send_message(
    message: str,
    api_key: str,
    timeout: int,
    agent_id: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Start een conversation (agent_id) of zet er één voort (conversation_id);
    geef de ruwe response (conversation_id + outputs)."""
    url = f"{API_URL}/{conversation_id}" if conversation_id else API_URL
    body = {"inputs": message} if conversation_id else {"agent_id": agent_id, "inputs": message}
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


TIMEOUT_EN_POGINGEN = {"websearch": (300, 3)}
STANDAARD_TIMEOUT_EN_POGINGEN = (180, 2)


def ask_with_retry(
    message: str,
    api_key: str,
    vraagtype: str = "standaard",
    attempts: int | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
) -> tuple[dict, str]:
    """Stuur het bericht met retry bij netwerkfouten; geef (response, error).

    Websearch-vragen draaien langer (meerdere tool-calls), dus ruimere timeout
    en een extra poging.
    """
    timeout, default_attempts = TIMEOUT_EN_POGINGEN.get(vraagtype, STANDAARD_TIMEOUT_EN_POGINGEN)
    error = ""
    for _ in range(attempts or default_attempts):
        try:
            response = send_message(
                message, api_key, timeout, agent_id=agent_id, conversation_id=conversation_id
            )
            return response, ""
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
    return {}, error


def play_conversation(
    entry: dict,
    agent_id: str,
    api_key: str,
    today: date,
    rules: dict,
    agent_names: dict[str, str],
) -> dict:
    """Speel `beurten` + `vraag` één keer af in een nieuwe conversation, met de
    contextregels van de proxy; geef het laatste antwoord, de trace per beurt
    en een error. Geen retry per beurt: na een timeout kan Mistral het bericht
    al verwerkt hebben, dus opnieuw posten zou de conversatie vervuilen."""
    conversation_id = None
    trace: list[dict] = []
    outputs: list[dict] = []
    previous_messages: list[str] = []
    for message in entry.get("beurten", []) + [entry["vraag"]]:
        beurt_t0 = time.monotonic()
        lookup_message = lookups.resolve_lookup_message(message, previous_messages, today, rules)
        lines = context.build_context_lines(
            lookup_message,
            today,
            rules,
            new_conversation=conversation_id is None,
            language_level=entry.get("taalniveau", "B1"),
        )
        response, error = ask_with_retry(
            context.add_context(lookup_message, lines),
            api_key,
            vraagtype=entry["type"],
            attempts=1,
            agent_id=None if conversation_id else agent_id,
            conversation_id=conversation_id,
        )
        if error:
            return {"antwoord": "", "trace": trace, "error": error, "duur_ms": 0.0}
        conversation_id = response.get("conversation_id") or conversation_id
        previous_messages.append(message)
        outputs = response.get("outputs", [])
        trace.append({
            "vraag": message,
            "agents": answering_agents(outputs, agent_names),
            "duur_ms": round((time.monotonic() - beurt_t0) * 1000, 1),
        })
    return {"antwoord": extract_text(outputs), "trace": trace, "error": ""}


def run_conversation(
    entry: dict,
    agent_id: str,
    api_key: str,
    today: date,
    rules: dict,
    agent_names: dict[str, str],
) -> dict:
    """Speel de conversation af; bij een netwerkfout start hij helemaal opnieuw
    (zelfde aantal pogingen als ask_with_retry voor dit vraagtype)."""
    _, attempts = TIMEOUT_EN_POGINGEN.get(entry["type"], STANDAARD_TIMEOUT_EN_POGINGEN)
    run: dict = {}
    for _ in range(attempts):
        run = play_conversation(entry, agent_id, api_key, today, rules, agent_names)
        if not run["error"]:
            break
    return run


def extract_bron(antwoord: str) -> str:
    """Geef alle 'Bron: ...'-regels uit het antwoord, samengevoegd met '; '."""
    matches = re.findall(r"^\s*Bron:\s*(.+)$", antwoord, flags=re.MULTILINE)
    return "; ".join(m.strip() for m in matches)


def bron_key(text: str) -> str:
    """Alfanumerieke sleutel voor bronvergelijking (URL's en bestandsnamen).

    Locale-segmenten (/nl_NL/), /index.php en de sessie-parameter sid tellen
    niet mee.
    """
    lowered = text.lower()
    lowered = re.sub(r"/[a-z]{2}_[a-z]{2}(?=/)", "", lowered)
    lowered = re.sub(r"/index\.php", "", lowered)
    lowered = re.sub(r"[?&]sid=\w+", "", lowered)
    return re.sub(r"[^a-z0-9]", "", lowered)


def bron_match(expected: str, bron_line: str) -> bool:
    """Match als één van de alternatieven ("a | b") in de Bron-regel staat."""
    line = bron_key(bron_line)
    for alternatief in expected.split("|"):
        exp = bron_key(alternatief)
        if exp and line and (exp in line or line in exp):
            return True
    return False


def _canoniek(token: str) -> str:
    """Token canoniek: "art" -> "artikel" (review 2026-11-12: modellen schrijven
    "art. 20.1.007" waar de evalset "artikel 20.1.007" verwacht), en getal-token
    canoniek: voorloopnullen weg, nul-decimalen weg (08,30->8,30; 10,00->10)."""
    if token == "art":
        return "artikel"
    if not token[0].isdigit():
        return token
    parts = [p.lstrip("0") or "0" for p in token.split(",")]
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ",".join(parts)


def tokens(text: str) -> list[str]:
    """Woorden en getallen; decimale punt/tijd-dubbelepunt tussen cijfers -> komma."""
    lowered = re.sub(r"(?<=\d)[.:](?=\d)", ",", text.lower())
    return [_canoniek(t) for t in re.findall(r"[a-z0-9]+(?:,[0-9]+)*", lowered)]


KORT_WOORD = 3


def kernfeit_gevonden(feit: str, antwoord: str) -> bool:
    """Elk token van het kernfeit staat los in het antwoord.

    Getallen en korte woorden (<= KORT_WOORD tekens) moeten als heel token
    voorkomen ("5" niet in "15", "ja" niet in "jaar"); langere woorden als
    woordbegin, zodat stammen als "verzeker" ook "verzekering" matchen.
    """
    antwoord_tokens = set(tokens(antwoord))
    for token in tokens(feit):
        if token[0].isdigit() or len(token) <= KORT_WOORD:
            if token not in antwoord_tokens:
                return False
        elif not any(t.startswith(token) for t in antwoord_tokens):
            return False
    return True


def check_entry(
    entry: dict, antwoord: str, trace: list[dict] | None = None, route: str = ""
) -> dict:
    """Beoordeel het antwoord op `vraag`; `trace` (per beurt de agents) is
    nodig voor de `verwachte_agent`-check; `route` (#92) voor de
    `verwacht_route`-check (bypass | direct-<domein> | router)."""
    trace = trace or []
    bron_line = extract_bron(antwoord)
    norm_antwoord = normalize(antwoord)
    feits = [f.strip() for f in entry["verwacht_antwoord"].split(";") if f.strip()]
    missing = [f for f in feits if not kernfeit_gevonden(f, antwoord)]
    # optioneel `verwacht_marker` (#47): bv. "[BRONCONFLICT]" — moet in de RUWE
    # agent-output staan (de proxy stript de marker pas voor de gebruiker)
    marker = entry.get("verwacht_marker", "")
    marker_gevonden = bool(marker) and normalize(marker) in norm_antwoord
    doorhaal = entry.get("doorhaal_waarde")
    doorhaal_gevonden = bool(doorhaal) and normalize(doorhaal) in norm_antwoord
    verboden = [w.strip() for w in entry.get("niet_in_antwoord", "").split(";") if w.strip()]
    verboden_gevonden = [w for w in verboden if kernfeit_gevonden(w, antwoord)]
    # type `verheldering` checkt alleen de kernfeiten (de bot stelt een
    # wedervraag); de bron-check vervalt. Bij taalniveau B2 (default B1,
    # issue #52) moet de bron in een "Bron:"-regel staan; bij B1 mag het
    # antwoord géén Bron-regel bevatten.
    level = entry.get("taalniveau", "B1")
    if entry.get("type") == "verheldering":
        bron_ok = True
    elif level == "B2":
        bron_ok = bron_match(entry.get("bron", ""), bron_line)
    else:
        bron_ok = bron_line == ""
    agents_laatste_beurt = trace[-1]["agents"] if trace else []
    verwachte_agent = entry.get("verwachte_agent", "")
    agent_ok = not verwachte_agent or verwachte_agent in agents_laatste_beurt
    # #92: `verwacht_route` assert de productie-route van de app (bypass | direct-<domein> | router)
    verwachte_route = entry.get("verwacht_route", "")
    route_ok = not verwachte_route or (route == verwachte_route)
    ok = (
        bron_ok
        and agent_ok
        and (not marker or marker_gevonden)
        and not missing
        and not doorhaal_gevonden
        and not verboden_gevonden
        and route_ok
    )
    return {
        "id": entry["id"],
        "categorie": entry["categorie"],
        "type": entry["type"],
        "taalniveau": level,
        "ok": ok,
        "bron_gevonden": bron_line,
        "bron_ok": bron_ok,
        "missende_kernfeiten": missing,
        "doorhaal_waarde_gevonden": doorhaal_gevonden,
        "verboden_gevonden": verboden_gevonden,
        "agent_ok": agent_ok,
        "verwachte_agent": verwachte_agent,
        "route": route,
        "verwachte_route": entry.get("verwacht_route", ""),
        "route_ok": route_ok,
        "agents_laatste_beurt": agents_laatste_beurt,
        # Volledige trace per vraag: wat verwacht werd + wat de agent teruggaf.
        "beurten": entry.get("beurten", []),
        "vraag": entry["vraag"],
        "verwacht_antwoord": entry["verwacht_antwoord"],
        "verwachte_bron": entry.get("bron", ""),
        "versiedatum": entry.get("versiedatum", ""),
        "doorhaal_waarde": entry.get("doorhaal_waarde", ""),
        "niet_in_antwoord": entry.get("niet_in_antwoord", ""),
        "verwacht_marker": marker,
        "marker_gevonden": marker_gevonden,
        "antwoord": antwoord,
        "trace": trace,
    }


def pct(n_ok: int, n_total: int) -> float:
    return round(100.0 * n_ok / n_total, 1) if n_total else 0.0


def main() -> int:
    # override=True: na create_agents.py --apply staan nieuwe agent-ids in .env,
    # terwijl de shell vaak nog de oude (verwijderde) ids heeft → anders 404.
    load_dotenv(ENV_PATH, override=True)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY ontbreekt")
    entries = load_evalset(EVAL_DIR / "evalset.yaml")
    today = load_peildatum(EVAL_DIR / "evalset.yaml")
    rules = knwu_categories.load_rules()
    agent_names = agent_names_from_env()
    results = []
    for entry in entries:
        # #92: spiegel de productie-route (bypass / direct-<domein> / router)
        t0 = time.monotonic()
        plan = plan_entry(entry, api_key, today, rules)
        if plan["route"] == "bypass":
            # deterministische bypass: geen conversation, template-antwoord uit
            # dezelfde app-functie als productie (0 LLM-calls voor de vraag)
            run = {
                "antwoord": lookups.render_lookup_answer(
                    plan["lookup"], plan["lookup_message"], rules, today, entry.get("taalniveau", "B1")
                ),
                "trace": [],
                "error": "",
                "llm_calls": 0,
            }
        else:
            run = run_conversation(entry, plan["agent_id"], api_key, today, rules, agent_names)
            run["llm_calls"] = len(run["trace"][-1]["agents"]) if run["trace"] else 0
        result = check_entry(entry, run["antwoord"], run["trace"], route=plan["route"])
        result["route"] = plan["route"]
        result["duur_ms"] = round((time.monotonic() - t0) * 1000, 1)
        result["llm_calls"] = run.get("llm_calls", 0)
        result["intake_ms"] = plan["intake_ms"]
        if run["error"]:
            result["ok"] = False
            result["error"] = run["error"]
        results.append(result)
        print(f"[{'OK ' if result['ok'] else 'FAIL'}] {entry['id']} ({plan['route']}, {result['duur_ms']}ms, {result['llm_calls']} calls)")

    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    per_categorie = {}
    for cat in {r["categorie"] for r in results}:
        subset = [r for r in results if r["categorie"] == cat]
        per_categorie[cat] = {
            "ok": sum(1 for r in subset if r["ok"]),
            "totaal": len(subset),
            "pct": pct(sum(1 for r in subset if r["ok"]), len(subset)),
        }
    hard = [r for r in results if r["type"] in HARD_GATE_TYPES]
    hard_ok = sum(1 for r in hard if r["ok"])
    # #92: aggregatie per route, zodat de 4 baseline-vragen vóór/na de
    # snelheidsflow direct vergelijkbaar zijn (duur_ms, llm_calls, route)
    per_route: dict[str, dict] = {}
    for route in {r.get("route", "") for r in results}:
        subset = [r for r in results if r.get("route", "") == route]
        per_route[route] = {
            "n": len(subset),
            "ok": sum(1 for r in subset if r["ok"]),
            "gemiddelde_duur_ms": round(
                sum(r.get("duur_ms", 0) for r in subset) / len(subset), 1
            ) if subset else 0.0,
            "llm_calls_totaal": sum(r.get("llm_calls", 0) for r in subset),
        }
    summary = {
        "totaal": total,
        "ok": ok,
        "pct": pct(ok, total),
        "per_categorie": per_categorie,
        "per_route": per_route,
        "harde_gate": {"types": sorted(HARD_GATE_TYPES), "ok": hard_ok, "totaal": len(hard)},
        "gate_gehaald": (
            pct(ok, total) >= GATE_PCT
            and all(c["pct"] >= GATE_PCT for c in per_categorie.values())
            and hard_ok == len(hard)
        ),
    }
    out = EVAL_DIR / "last_run.json"
    out.write_text(
        json.dumps({"summary": summary, "resultaten": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["gate_gehaald"] else 1


if __name__ == "__main__":
    sys.exit(main())
