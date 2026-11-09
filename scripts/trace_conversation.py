"""Conversatie-trace: welke agent beantwoordde elke beurt van een conversatie?

Bewijs voor de architectuurvraag in issue #44: blijft een conversatie na een
handoff bij één sub-agent hangen ("sticky handoff")? Per beurt toont het
script de vraag, de handoffs, de gebruikte tools en de agent die antwoordde.

Usage:
    python scripts/trace_conversation.py <app-conversation-id>   # uit het feedback-rapport
    python scripts/trace_conversation.py --mistral-id <conv_id>  # direct op Mistral-id
    python scripts/trace_conversation.py --date 2026-11-06       # conversaties van die dag

De app zet sinds #44 `metadata.app_conversation_id` op elke nieuwe
Mistral-conversatie; oudere conversaties vind je via --date.

Environment (.env in de repo-root): MISTRAL_API_KEY.
Privacy: de output bevat vragen van gebruikers — alleen lokaal bekijken, nooit
in git of tickets (zie scripts/feedback_report.py).
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "app"))

import context  # noqa: E402  (app-module, pas na sys.path)

API_BASE = "https://api.mistral.ai/v1"
TIMEOUT = 30
MAX_LIST_PAGES = 10
QUESTION_PREVIEW = 100


def api_get(path: str, api_key: str, params: dict | None = None) -> dict | list:
    resp = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        params=params,
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Mistral API {path}: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def find_by_app_id(app_conversation_id: str, api_key: str) -> list[dict]:
    metadata = json.dumps({"app_conversation_id": app_conversation_id})
    return api_get("/conversations", api_key, {"metadata": metadata})


def list_on_date(day: date, api_key: str) -> list[dict]:
    """Conversaties die op `day` (UTC) zijn aangemaakt, oudste eerst."""
    found = []
    for page in range(MAX_LIST_PAGES):
        conversations = api_get("/conversations", api_key, {"page": page, "page_size": 100})
        if not conversations:
            break
        found += [c for c in conversations if c.get("created_at", "").startswith(day.isoformat())]
    return sorted(found, key=lambda c: c["created_at"])


def fetch_entries(mistral_id: str, api_key: str) -> list[dict]:
    return api_get(f"/conversations/{mistral_id}/history", api_key).get("entries", [])


def fetch_agent_names(api_key: str) -> dict[str, str]:
    agents = api_get("/agents", api_key, {"page_size": 100})
    return {agent["id"]: agent["name"] for agent in agents}


def text_of(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return "".join(chunk.get("text", "") for chunk in content if isinstance(chunk, dict))


def summarize_turns(entries: list[dict], agent_names: dict[str, str]) -> list[dict]:
    """Groepeer history-entries per gebruikersbericht (beurt)."""
    turns: list[dict] = []
    for entry in entries:
        kind = entry.get("type")
        if kind == "message.input":
            question, _, injected = text_of(entry.get("content", "")).partition(context.CONTEXT_HEADER)
            turns.append({
                "question": question.strip(),
                "context_lines": bool(injected),
                "handoffs": [],
                "tools": [],
                "answered_by": [],
            })
        elif not turns:
            continue
        elif kind == "agent.handoff":
            turns[-1]["handoffs"].append(f"{entry['previous_agent_name']} -> {entry['next_agent_name']}")
        elif kind == "tool.execution":
            turns[-1]["tools"].append(str(entry.get("name", "?")))
        elif kind == "message.output":
            agent_id = entry.get("agent_id") or "?"
            turns[-1]["answered_by"].append(agent_names.get(agent_id, agent_id))
    return turns


def format_turns(turns: list[dict]) -> str:
    lines = []
    for number, turn in enumerate(turns, start=1):
        question = turn["question"][:QUESTION_PREVIEW]
        marker = " (+ contextregels)" if turn["context_lines"] else ""
        lines.append(f"Beurt {number}: {question}{marker}")
        for handoff in turn["handoffs"]:
            lines.append(f"  handoff: {handoff}")
        if turn["tools"]:
            lines.append(f"  tools: {', '.join(turn['tools'])}")
        lines.append(f"  antwoord door: {', '.join(turn['answered_by']) or '-'}")
    return "\n".join(lines)


def print_trace(mistral_id: str, api_key: str, agent_names: dict[str, str]) -> None:
    print(f"== Mistral-conversatie {mistral_id}")
    print(format_turns(summarize_turns(fetch_entries(mistral_id, api_key), agent_names)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Toon per beurt welke agent antwoordde.")
    parser.add_argument("app_conversation_id", nargs="?", help="conversation-id uit het feedback-rapport")
    parser.add_argument("--mistral-id", help="Mistral conversation-id")
    parser.add_argument("--date", type=date.fromisoformat, help="alle conversaties van die dag (UTC)")
    args = parser.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env", override=True)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        parser.error("MISTRAL_API_KEY ontbreekt; zet die in .env in de repo-root")

    if args.mistral_id:
        mistral_ids = [args.mistral_id]
    elif args.app_conversation_id:
        mistral_ids = [c["id"] for c in find_by_app_id(args.app_conversation_id, api_key)]
    elif args.date:
        mistral_ids = [c["id"] for c in list_on_date(args.date, api_key)]
    else:
        parser.error("geef een app-conversation-id, --mistral-id of --date")

    if not mistral_ids:
        print("Geen Mistral-conversatie gevonden. Conversaties van vóór #44 hebben geen "
              "app_conversation_id; zoek ze met --date.")
        return 1
    agent_names = fetch_agent_names(api_key)
    for mistral_id in mistral_ids:
        print_trace(mistral_id, api_key, agent_names)
    return 0


if __name__ == "__main__":
    sys.exit(main())
