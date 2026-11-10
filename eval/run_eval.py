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
- `beurten` (optioneel): eerdere gebruikersberichten in dezelfde
  conversatie, vóór `vraag`; alleen het antwoord op `vraag` wordt gecheckt
- `verwachte_agent` (optioneel): naam van de agent die het antwoord op
  `vraag` moet geven (bv. knwu-agent); vangt een sticky handoff
- verheldering: geen bron-check; de kernfeiten (bv. geboortejaar, geslacht)
  moeten in de wedervraag van de bot staan

Elk bericht krijgt dezelfde contextregels als in productie (taalniveau per
bericht, datum bij de eerste beurt, categorie bij een geboortejaar;
app/context.py). Het taalniveau komt uit het optionele veld `taalniveau`
per evalset-entry (default B1, de productiestandaard sinds #52). Per beurt
legt last_run.json vast welke agent antwoordde (`trace`).

Gate: globaal >= 90% en per categorie >= 90% correct met correcte bron;
type `strikethrough` en `websearch` zijn een harde 100%-gate. Resultaat
naar eval/last_run.json; exit-code 0 bij halen van de gate, anders 1.

Draai handmatig door de beheerder na elke library-update — NOOIT in CI
(geen live API-calls in CI). Zie docs/reference/eval-set.md.

Environment (uit .env in de repo-root; .env wint van shellvariabelen):
- MISTRAL_API_KEY               (verplicht)
- MISTRAL_AGENT_ID_KNWU / MISTRAL_AGENT_ID_REGIO / MISTRAL_AGENT_ID_CLUB
  (agent per categorie; fallback: MISTRAL_AGENT_ID)

Afhankelijkheden: pip install requests pyyaml python-dotenv
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

EVAL_DIR = Path(__file__).parent
ENV_PATH = EVAL_DIR.parent / ".env"
sys.path.insert(0, str(EVAL_DIR.parent / "app"))

import context  # noqa: E402  (app-module: dezelfde contextregels als de proxy)
import knwu_categories  # noqa: E402

API_URL = "https://api.mistral.ai/v1/conversations"
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
    for message in entry.get("beurten", []) + [entry["vraag"]]:
        lines = context.build_context_lines(
            message,
            today,
            rules,
            new_conversation=conversation_id is None,
            language_level=entry.get("taalniveau", "B1"),
        )
        response, error = ask_with_retry(
            context.add_context(message, lines),
            api_key,
            vraagtype=entry["type"],
            attempts=1,
            agent_id=None if conversation_id else agent_id,
            conversation_id=conversation_id,
        )
        if error:
            return {"antwoord": "", "trace": trace, "error": error}
        conversation_id = response.get("conversation_id") or conversation_id
        outputs = response.get("outputs", [])
        trace.append({"vraag": message, "agents": answering_agents(outputs, agent_names)})
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
    """Getal-token canoniek: voorloopnullen weg, nul-decimalen weg (08,30->8,30; 10,00->10)."""
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


def check_entry(entry: dict, antwoord: str, trace: list[dict] | None = None) -> dict:
    """Beoordeel het antwoord op `vraag`; `trace` (per beurt de agents) is
    nodig voor de `verwachte_agent`-check."""
    trace = trace or []
    bron_line = extract_bron(antwoord)
    norm_antwoord = normalize(antwoord)
    feits = [f.strip() for f in entry["verwacht_antwoord"].split(";") if f.strip()]
    missing = [f for f in feits if not kernfeit_gevonden(f, antwoord)]
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
    ok = bron_ok and agent_ok and not missing and not doorhaal_gevonden and not verboden_gevonden
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
        "agents_laatste_beurt": agents_laatste_beurt,
        # Volledige trace per vraag: wat verwacht werd + wat de agent teruggaf.
        "beurten": entry.get("beurten", []),
        "vraag": entry["vraag"],
        "verwacht_antwoord": entry["verwacht_antwoord"],
        "verwachte_bron": entry.get("bron", ""),
        "versiedatum": entry.get("versiedatum", ""),
        "doorhaal_waarde": entry.get("doorhaal_waarde", ""),
        "niet_in_antwoord": entry.get("niet_in_antwoord", ""),
        "antwoord": antwoord,
        "trace": trace,
    }


def pct(n_ok: int, n_total: int) -> float:
    return round(100.0 * n_ok / n_total, 1) if n_total else 0.0


def main() -> int:
    # override: na create_agents.py --apply staan nieuwe agent-ids in .env, terwijl
    # de shell vaak nog de oude (verwijderde) ids heeft → anders 404 op elke vraag.
    load_dotenv(ENV_PATH, override=True)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY ontbreekt")
    entries = load_evalset(EVAL_DIR / "evalset.yaml")
    today = context.today_in_netherlands()
    rules = knwu_categories.load_rules()
    agent_names = agent_names_from_env()
    results = []
    for entry in entries:
        run = run_conversation(entry, agent_id_for(entry), api_key, today, rules, agent_names)
        result = check_entry(entry, run["antwoord"], run["trace"])
        if run["error"]:
            result["ok"] = False
            result["error"] = run["error"]
        results.append(result)
        print(f"[{'OK ' if result['ok'] else 'FAIL'}] {entry['id']}")

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
    summary = {
        "totaal": total,
        "ok": ok,
        "pct": pct(ok, total),
        "per_categorie": per_categorie,
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
