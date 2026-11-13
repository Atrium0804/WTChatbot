"""Create or update the production Mistral agents of the WTChatbot MVP.

Reads agents_config.json: model, completion_args and the agent list (name,
description, prompt files, optional library, websearch flag, handoffs).
Prompt texts live in separate files under prompts_folder (CODING_PRINCIPLES).

An existing remote agent with the same name is updated, a missing one is
created — the script is idempotent. Handoffs are resolved to agent ids in a
second phase, after the target agents exist.

Dry-run by default; pass --apply to execute changes.

The web_search tool is configured as a bare {"type": "web_search"}: domain
filtering is enforced org-wide via /v1/web-filters (docs/how-to/
stel-websearch-allowlist-in.md) — do NOT use tool_configuration.include, it silently
breaks the tool in mistralai 3.6.0.

Usage:
    python scripts/create_agents.py           # dry-run
    python scripts/create_agents.py --apply   # create/update the agents
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TypedDict

try:
    from dotenv import load_dotenv
    from mistralai.client import Mistral
except ModuleNotFoundError:
    raise SystemExit(
        "error: afhankelijkheden niet gevonden — activeer eerst de venv "
        "(.venv\\Scripts\\activate) of draai met .venv\\Scripts\\python"
    )

import sync_libraries

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "agents_config.json"


class AgentConfig(TypedDict, total=False):
    name: str
    description: str
    prompt_files: list[str]
    library: str | None
    websearch: bool
    handoffs: list[str]
    model: str  # optionele per-agent model-override (#83); default = config["model"]


class Config(TypedDict, total=False):
    model: str
    completion_args: dict
    prompts_folder: str
    agents: list[AgentConfig]


class AgentReport(TypedDict):
    created: list[str]
    updated: list[str]
    errors: list[str]
    agent_ids: dict[str, str]


def load_config(path: Path) -> Config:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}")
    for key in ("model", "completion_args", "agents"):
        if key not in data:
            raise SystemExit(f"error: config {path} is missing key '{key}'")
    if not isinstance(data["agents"], list) or not data["agents"]:
        raise SystemExit(f"error: config {path}: 'agents' must be a non-empty list")
    for entry in data["agents"]:
        for key in ("name", "description", "prompt_files"):
            if key not in entry:
                raise SystemExit(f"error: config {path}: agent entry missing '{key}': {entry}")
        if not isinstance(entry["prompt_files"], list) or not entry["prompt_files"]:
            raise SystemExit(f"error: config {path}: 'prompt_files' must be a non-empty list: {entry}")
        # #83: optionele per-agent model-override moet een string zijn
        if "model" in entry and not isinstance(entry["model"], str):
            raise SystemExit(
                f"error: config {path}: per-agent 'model' must be a string: {entry}"
            )
    data.setdefault("prompts_folder", "prompts")
    return data


def build_tools(agent: AgentConfig, library_ids: dict[str, str]) -> list[dict]:
    """Build the tools list for one agent.

    library -> document_library tool with the resolved library id;
    websearch -> bare web_search tool (org-level web-filters enforce domains).
    """
    tools: list[dict] = []
    library_name = agent.get("library")
    if library_name:
        library_id = library_ids.get(library_name)
        if library_id is None:
            raise ValueError(
                f"library '{library_name}' niet gevonden — draai eerst: "
                "python scripts/sync_libraries.py --apply"
            )
        tools.append({"type": "document_library", "library_ids": [library_id]})
    if agent.get("websearch", False):
        tools.append({"type": "web_search"})
    return tools


def load_prompt(prompts_dir: Path, agent: AgentConfig) -> str:
    """Concatenate the agent's prompt files (in order) into one instructions string."""
    parts: list[str] = []
    for file_name in agent["prompt_files"]:
        path = prompts_dir / file_name
        try:
            parts.append(path.read_text(encoding="utf-8").strip())
        except FileNotFoundError:
            raise SystemExit(f"error: prompt file not found: {path}")
    return "\n\n".join(parts)


def list_all_agents(client: Mistral) -> list:
    """List all remote agents via the cursor-paginated list_pages endpoint."""
    agents: list = []
    page = client.beta.agents.list_pages(page_size=100)
    while page is not None:
        agents.extend(page.result.data)
        page = page.next()
    return agents


def env_var_for(agent_name: str) -> str:
    """Env var that holds this agent's id: MISTRAL_AGENT_ID for the router (app),
    MISTRAL_AGENT_ID_<NAME> per content agent (eval)."""
    if agent_name == "router-agent":
        return "MISTRAL_AGENT_ID"
    category = agent_name.removesuffix("-agent")
    return "MISTRAL_AGENT_ID_" + category.upper().replace("-", "_")


def print_summary(report: AgentReport, apply: bool) -> None:
    mode = "apply" if apply else "dry-run"
    print(f"\n--- summary ({mode}) ---")
    print(f"agents created: {len(report['created'])} {report['created']}")
    print(f"agents updated: {len(report['updated'])} {report['updated']}")
    if report["errors"]:
        print(f"errors ({len(report['errors'])}):")
        for error in report["errors"]:
            print(f"  - {error}")
    if report["agent_ids"]:
        print("agent ids (zet in .env):")
        for name, agent_id in report["agent_ids"].items():
            print(f"  {env_var_for(name)}={agent_id}  # {name}")


def handoff_order(agents: list[AgentConfig]) -> list[AgentConfig]:
    """Config order, but every agent after the in-config agents it hands off to.

    Targets outside the config (remote or unknown) don't constrain the order;
    a cycle falls back to config order and surfaces as a handoff error.
    """
    names = {a["name"] for a in agents}
    ordered: list[AgentConfig] = []
    placed: set[str] = set()
    pending = list(agents)
    while pending:
        ready = [
            a for a in pending if all(t in placed or t not in names for t in a.get("handoffs", []))
        ] or pending
        ordered += ready
        placed |= {a["name"] for a in ready}
        pending = [a for a in pending if a["name"] not in placed]
    return ordered


def run_create(
    client: Mistral,
    config: Config,
    apply: bool,
    report: AgentReport,
    config_path: Path | None = None,
) -> int:
    prompts_dir = Path(config["prompts_folder"])
    if not prompts_dir.is_absolute() and config_path is not None:
        prompts_dir = config_path.parent / prompts_dir
    prompts_dir = prompts_dir.resolve()

    libraries = sync_libraries.list_all_libraries(client)
    library_ids = {lib.name: lib.id for lib in libraries}
    existing = list_all_agents(client)
    id_by_name: dict[str, str] = {a.name: a.id for a in existing}
    report["agent_ids"] = id_by_name

    # Handoff targets are resolved in config order; a target that is in the
    # config but not created yet (a cycle, e.g. knwu <-> club) is deferred and
    # set by an update after all agents exist.
    ordered = handoff_order(config["agents"])
    config_names = {a["name"] for a in config["agents"]}
    deferred: dict[str, list[str]] = {}

    for agent in ordered:
        name = agent["name"]
        try:
            tools = build_tools(agent, library_ids)
            instructions = load_prompt(prompts_dir, agent)
        except (ValueError, SystemExit) as exc:
            report["errors"].append(f"agent {name}: {exc}")
            print(f"error: agent {name}: {exc}", file=sys.stderr)
            continue

        handoff_ids: list[str] | None = None
        if agent.get("handoffs"):
            handoff_ids = []
            for target in agent["handoffs"]:
                target_id = id_by_name.get(target)
                if target_id is None and target in config_names:
                    deferred.setdefault(name, []).append(target)
                    continue
                if target_id is None:
                    report["errors"].append(
                        f"agent {name}: handoff target '{target}' is niet in de config en niet remote"
                    )
                    print(f"error: agent {name}: handoff target '{target}' not found", file=sys.stderr)
                    handoff_ids = None
                    break
                handoff_ids.append(target_id)
            if handoff_ids is None:
                deferred.pop(name, None)
                continue

        payload: dict = {
            # #83: per-agent model-override; default is de globale config["model"]
            "model": agent.get("model", config["model"]),
            "name": name,
            "description": agent["description"],
            "instructions": instructions,
            "tools": tools,
            "completion_args": config["completion_args"],
        }
        if handoff_ids is not None:
            payload["handoffs"] = handoff_ids

        existing_agent = next((a for a in existing if a.name == name), None)
        if not apply:
            action = "update" if existing_agent else "create"
            print(f"[dry-run] would {action} agent '{name}'")
            report["updated" if existing_agent else "created"].append(name)
            if not existing_agent:
                id_by_name[name] = f"<new-{name}>"
            continue
        if existing_agent:
            result = client.beta.agents.update(agent_id=existing_agent.id, **payload)
            report["updated"].append(name)
            print(f"updated agent '{name}' ({result.id})")
        else:
            result = client.beta.agents.create(**payload)
            report["created"].append(name)
            print(f"created agent '{name}' ({result.id})")
        id_by_name[name] = result.id

    if apply:
        for agent in ordered:
            targets = deferred.get(agent["name"])
            agent_id = id_by_name.get(agent["name"])
            if not targets or agent_id is None:
                continue
            handoff_ids = [id_by_name[t] for t in agent["handoffs"] if t in id_by_name]
            client.beta.agents.update(agent_id=agent_id, handoffs=handoff_ids)
            print(f"set handoffs of agent '{agent['name']}' (cycle): {agent['handoffs']}")

    print_summary(report, apply)
    return 1 if report["errors"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/update the production Mistral agents.")
    parser.add_argument("--apply", action="store_true", help="execute changes (default: dry-run)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path to config JSON")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("error: MISTRAL_API_KEY is not set; check .env", file=sys.stderr)
        return 2
    client = Mistral(api_key=api_key)
    config = load_config(args.config)
    report: AgentReport = {"created": [], "updated": [], "errors": [], "agent_ids": {}}
    return run_create(client, config, apply=args.apply, report=report, config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
