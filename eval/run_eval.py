"""Eval-runner: launch-gate van de MVP.

Leest eval/evalset.yaml, stelt per vraag een nieuwe conversation met de
bijbehorende agent via de Mistral Conversations API (zelfde agent-instructies
als productie, offline — niet tegen de draaiende bot) en checkt:

- bron: de "Bron:"-regel in het antwoord matcht (na normalisatie) de `bron`
- kernfeiten: elk item van `verwacht_antwoord` (gescheiden door ";") komt in
  het antwoord voor (case-insensitive, komma/punt genormaliseerd)
- strikethrough: `doorhaal_waarde` (indien opgegeven) mag NIET voorkomen

Gate: globaal >= 90% en per categorie >= 90% correct met correcte bron;
type `strikethrough` en `websearch` zijn een harde 100%-gate. Resultaat
naar eval/last_run.json; exit-code 0 bij halen van de gate, anders 1.

Draai handmatig door de beheerder na elke library-update — NOOIT in CI
(geen live API-calls in CI). Zie docs/reference/eval-set.md.

Environment:
- MISTRAL_API_KEY               (verplicht)
- MISTRAL_AGENT_ID_KNWU / MISTRAL_AGENT_ID_REGIO / MISTRAL_AGENT_ID_CLUB
  (agent per categorie; fallback: MISTRAL_AGENT_ID)

Afhankelijkheden: pip install requests pyyaml
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
import yaml

API_URL = "https://api.mistral.ai/v1/conversations"
GATE_PCT = 90.0
HARD_GATE_TYPES = {"strikethrough", "websearch"}

EVAL_DIR = Path(__file__).parent


def normalize(text: str) -> str:
    """Lowercase en normaliseer decimale notatie voor matching."""
    return text.lower().replace(".", ",").strip()


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
    outputs = resp.json().get("outputs", [])
    texts = []
    for out in outputs:
        content = out.get("message", {}).get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    texts.append(chunk.get("text", ""))
    return "\n".join(texts)


def extract_bron(antwoord: str) -> str:
    """Geef de laatste 'Bron: ...'-regel uit het antwoord."""
    matches = re.findall(r"^\s*Bron:\s*(.+)$", antwoord, flags=re.MULTILINE)
    return matches[-1].strip() if matches else ""


def bron_match(expected: str, bron_line: str) -> bool:
    exp = normalize(expected)
    line = normalize(bron_line)
    if not exp or not line:
        return False
    if exp in line or line in exp:
        return True
    # URL zonder query of www. vergelijken
    exp_host = re.sub(r"^https?://(www\.)?", "", exp).split("?")[0]
    line_host = re.sub(r"^https?://(www\.)?", "", line).split("?")[0]
    return exp_host in line_host or line_host in exp_host


def check_entry(entry: dict, antwoord: str) -> dict:
    bron_line = extract_bron(antwoord)
    norm_antwoord = normalize(antwoord)
    feits = [f.strip() for f in entry["verwacht_antwoord"].split(";") if f.strip()]
    missing = [f for f in feits if normalize(f) not in norm_antwoord]
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
    }


def pct(n_ok: int, n_total: int) -> float:
    return round(100.0 * n_ok / n_total, 1) if n_total else 0.0


def main() -> int:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY ontbreekt")
    entries = load_evalset(EVAL_DIR / "evalset.yaml")
    results = []
    for entry in entries:
        antwoord = call_agent(entry["vraag"], agent_id_for(entry["categorie"]), api_key)
        results.append(check_entry(entry, antwoord))
        print(f"[{'OK ' if results[-1]['ok'] else 'FAIL'}] {entry['id']}")

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
