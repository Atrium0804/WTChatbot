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
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

API_URL = "https://api.mistral.ai/v1/conversations"
GATE_PCT = 90.0
HARD_GATE_TYPES = {"strikethrough", "websearch"}

EVAL_DIR = Path(__file__).parent
ENV_PATH = EVAL_DIR.parent / ".env"


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


def agent_id_for(categorie: str) -> str:
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


def call_agent(vraag: str, agent_id: str, api_key: str, timeout: int = 180) -> str:
    """Stuur de vraag naar een nieuwe conversation en geef de antwoordtekst."""
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"agent_id": agent_id, "inputs": vraag},
        timeout=timeout,
    )
    resp.raise_for_status()
    return extract_text(resp.json().get("outputs", []))


TIMEOUT_EN_POGINGEN = {"websearch": (300, 3)}
STANDAARD_TIMEOUT_EN_POGINGEN = (180, 2)


def ask_with_retry(
    vraag: str, agent_id: str, api_key: str, vraagtype: str = "standaard", attempts: int | None = None
) -> tuple[str, str]:
    """Stel de vraag met retry bij netwerkfouten; geef (antwoord, error).

    Websearch-vragen draaien langer (meerdere tool-calls), dus ruimere timeout
    en een extra poging.
    """
    timeout, default_attempts = TIMEOUT_EN_POGINGEN.get(vraagtype, STANDAARD_TIMEOUT_EN_POGINGEN)
    error = ""
    for _ in range(attempts or default_attempts):
        try:
            return call_agent(vraag, agent_id, api_key, timeout=timeout), ""
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
    return "", error


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


def check_entry(entry: dict, antwoord: str) -> dict:
    bron_line = extract_bron(antwoord)
    norm_antwoord = normalize(antwoord)
    feits = [f.strip() for f in entry["verwacht_antwoord"].split(";") if f.strip()]
    missing = [f for f in feits if not kernfeit_gevonden(f, antwoord)]
    doorhaal = entry.get("doorhaal_waarde")
    doorhaal_gevonden = bool(doorhaal) and normalize(doorhaal) in norm_antwoord
    ok = bron_match(entry["bron"], bron_line) and not missing and not doorhaal_gevonden
    return {
        "id": entry["id"],
        "categorie": entry["categorie"],
        "type": entry["type"],
        "ok": ok,
        "bron_gevonden": bron_line,
        "bron_ok": bron_match(entry["bron"], bron_line),
        "missende_kernfeiten": missing,
        "doorhaal_waarde_gevonden": doorhaal_gevonden,
        # Volledige trace per vraag: wat verwacht werd + wat de agent teruggaf.
        "vraag": entry["vraag"],
        "verwacht_antwoord": entry["verwacht_antwoord"],
        "verwachte_bron": entry["bron"],
        "versiedatum": entry.get("versiedatum", ""),
        "doorhaal_waarde": entry.get("doorhaal_waarde", ""),
        "antwoord": antwoord,
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
    results = []
    for entry in entries:
        antwoord, error = ask_with_retry(
            entry["vraag"], agent_id_for(entry["categorie"]), api_key, vraagtype=entry["type"]
        )
        result = check_entry(entry, antwoord)
        if error:
            result["ok"] = False
            result["error"] = error
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
