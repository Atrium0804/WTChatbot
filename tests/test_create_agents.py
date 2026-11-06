import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import create_agents


def write_json(folder: Path, name: str, data: dict) -> Path:
    path = folder / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def minimal_config() -> dict:
    return {
        "model": "mistral-large-4",
        "completion_args": {"temperature": 0, "top_p": 1},
        "agents": [
            {
                "name": "knwu-agent",
                "description": "KNWU-agent",
                "prompt_files": ["knwu-agent.md"],
                "library": "knwu",
                "websearch": True,
            }
        ],
    }


class LoadConfigTests(unittest.TestCase):
    def test_minimal_config_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_json(Path(tmp), "agents_config.json", minimal_config())
            config = create_agents.load_config(path)
            self.assertEqual(config["model"], "mistral-large-4")
            self.assertEqual(config["agents"][0]["name"], "knwu-agent")
            self.assertEqual(config["prompts_folder"], "prompts")

    def test_missing_model_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = minimal_config()
            del data["model"]
            path = write_json(Path(tmp), "agents_config.json", data)
            with self.assertRaises(SystemExit) as ctx:
                create_agents.load_config(path)
            self.assertIn("model", str(ctx.exception))

    def test_agent_missing_prompt_files_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = minimal_config()
            del data["agents"][0]["prompt_files"]
            path = write_json(Path(tmp), "agents_config.json", data)
            with self.assertRaises(SystemExit) as ctx:
                create_agents.load_config(path)
            self.assertIn("prompt_files", str(ctx.exception))

    def test_invalid_json_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents_config.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(SystemExit):
                create_agents.load_config(path)


class BuildToolsTests(unittest.TestCase):
    def test_library_and_websearch_produce_expected_tools(self) -> None:
        agent = {"name": "knwu-agent", "library": "knwu", "websearch": True}
        tools = create_agents.build_tools(agent, {"knwu": "lib-knwu-1"})

        self.assertEqual(
            tools,
            [
                {"type": "document_library", "library_ids": ["lib-knwu-1"]},
                {"type": "web_search"},
            ],
        )

    def test_websearch_tool_has_no_tool_configuration(self) -> None:
        # docs/how-to/websearch-allowlist.md: tool_configuration.include breekt de
        # web_search-tool in mistralai 3.6.0 — de org-level web-filters regelen de scope.
        agent = {"name": "club-agent", "websearch": True}
        tools = create_agents.build_tools(agent, {})
        self.assertEqual(tools, [{"type": "web_search"}])
        self.assertNotIn("tool_configuration", tools[0])

    def test_no_library_no_websearch_gives_empty_list(self) -> None:
        agent = {"name": "router-agent"}
        self.assertEqual(create_agents.build_tools(agent, {}), [])

    def test_missing_library_raises_with_sync_hint(self) -> None:
        agent = {"name": "knwu-agent", "library": "knwu", "websearch": False}
        with self.assertRaises(ValueError) as ctx:
            create_agents.build_tools(agent, {})
        self.assertIn("sync_libraries.py --apply", str(ctx.exception))


class LoadPromptTests(unittest.TestCase):
    def test_concatenates_prompt_files_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "_shared.md").write_text("GEDEELDE KERN", encoding="utf-8")
            (folder / "knwu-agent.md").write_text("KNWU ADDENDUM", encoding="utf-8")
            agent = {"name": "knwu-agent", "prompt_files": ["_shared.md", "knwu-agent.md"]}
            prompt = create_agents.load_prompt(folder, agent)
            self.assertEqual(prompt, "GEDEELDE KERN\n\nKNWU ADDENDUM")

    def test_missing_prompt_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = {"name": "x", "prompt_files": ["bestaat-niet.md"]}
            with self.assertRaises(SystemExit) as ctx:
                create_agents.load_prompt(Path(tmp), agent)
            self.assertIn("bestaat-niet.md", str(ctx.exception))


def make_client(remote_agents=(), remote_libraries=()) -> MagicMock:
    client = MagicMock()
    client.beta.libraries.list.return_value = SimpleNamespace(
        data=list(remote_libraries), next_page_token=None
    )
    first_page = SimpleNamespace(
        result=SimpleNamespace(data=list(remote_agents)), next=lambda: None
    )
    client.beta.agents.list_pages.return_value = first_page
    client.beta.agents.create.side_effect = (
        lambda **kwargs: SimpleNamespace(id=f"agent-{kwargs['name']}", name=kwargs["name"])
    )
    client.beta.agents.update.side_effect = (
        lambda agent_id, **kwargs: SimpleNamespace(id=agent_id, name=kwargs.get("name"))
    )
    return client


def make_lib(name: str, lib_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=lib_id, name=name)


def make_agent(name: str, agent_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=agent_id, name=name)


class RunCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        prompts = self.root / "prompts"
        prompts.mkdir()
        (prompts / "_shared.md").write_text("GEDEELDE KERN", encoding="utf-8")
        (prompts / "knwu-agent.md").write_text("KNWU ADDENDUM", encoding="utf-8")
        (prompts / "router-agent.md").write_text("ROUTERPROMPT", encoding="utf-8")

    def make_config(self, agents: list[dict]) -> Path:
        config = {
            "model": "mistral-large-4",
            "completion_args": {"temperature": 0, "top_p": 1},
            "prompts_folder": "prompts",
            "agents": agents,
        }
        return write_json(self.root, "agents_config.json", config)

    def knwu_agent(self) -> dict:
        return {
            "name": "knwu-agent",
            "description": "KNWU-agent",
            "prompt_files": ["_shared.md", "knwu-agent.md"],
            "library": "knwu",
            "websearch": True,
        }

    def router_agent(self) -> dict:
        return {
            "name": "router-agent",
            "description": "Router-agent",
            "prompt_files": ["router-agent.md"],
            "handoffs": ["knwu-agent"],
        }

    def empty_report(self) -> create_agents.AgentReport:
        return {"created": [], "updated": [], "errors": [], "agent_ids": {}}

    def test_dry_run_makes_no_mutations(self) -> None:
        config_path = self.make_config([self.knwu_agent(), self.router_agent()])
        client = make_client(remote_libraries=[make_lib("knwu", "lib-knwu-1")])
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=False, report=report, config_path=config_path
        )

        self.assertEqual(rc, 0)
        client.beta.agents.create.assert_not_called()
        client.beta.agents.update.assert_not_called()
        self.assertEqual(sorted(report["created"]), ["knwu-agent", "router-agent"])
        self.assertEqual(report["errors"], [])

    def test_apply_creates_agents_and_resolves_handoffs_to_ids(self) -> None:
        config_path = self.make_config([self.knwu_agent(), self.router_agent()])
        client = make_client(remote_libraries=[make_lib("knwu", "lib-knwu-1")])
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
        )

        self.assertEqual(rc, 0)
        self.assertEqual(report["created"], ["knwu-agent", "router-agent"])
        self.assertEqual(report["errors"], [])

        knwu_call = client.beta.agents.create.call_args_list[0].kwargs
        self.assertEqual(knwu_call["model"], "mistral-large-4")
        self.assertEqual(knwu_call["name"], "knwu-agent")
        self.assertEqual(
            knwu_call["tools"],
            [{"type": "document_library", "library_ids": ["lib-knwu-1"]}, {"type": "web_search"}],
        )
        self.assertEqual(knwu_call["completion_args"], {"temperature": 0, "top_p": 1})
        self.assertEqual(knwu_call["instructions"], "GEDEELDE KERN\n\nKNWU ADDENDUM")
        self.assertNotIn("handoffs", knwu_call)

        router_call = client.beta.agents.create.call_args_list[1].kwargs
        self.assertEqual(router_call["name"], "router-agent")
        self.assertEqual(router_call["tools"], [])
        self.assertEqual(router_call["handoffs"], ["agent-knwu-agent"])

    def test_apply_updates_existing_agent_instead_of_creating(self) -> None:
        config_path = self.make_config([self.knwu_agent()])
        client = make_client(
            remote_agents=[make_agent("knwu-agent", "agent-old-1")],
            remote_libraries=[make_lib("knwu", "lib-knwu-1")],
        )
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
        )

        self.assertEqual(rc, 0)
        client.beta.agents.create.assert_not_called()
        client.beta.agents.update.assert_called_once()
        self.assertEqual(client.beta.agents.update.call_args.kwargs["agent_id"], "agent-old-1")
        self.assertEqual(report["updated"], ["knwu-agent"])
        self.assertEqual(report["agent_ids"]["knwu-agent"], "agent-old-1")

    def test_missing_library_is_error_and_skips_agent(self) -> None:
        config_path = self.make_config([self.knwu_agent()])
        client = make_client(remote_libraries=[])
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
        )

        self.assertEqual(rc, 1)
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("sync_libraries.py --apply", report["errors"][0])
        client.beta.agents.create.assert_not_called()

    def test_env_var_names_match_app_and_eval_convention(self) -> None:
        # app/config.py leest MISTRAL_AGENT_ID (router); eval/run_eval.py leest
        # MISTRAL_AGENT_ID_<CATEGORIE> per evalset-categorie (knwu/regio/club).
        self.assertEqual(create_agents.env_var_for("router-agent"), "MISTRAL_AGENT_ID")
        self.assertEqual(create_agents.env_var_for("knwu-agent"), "MISTRAL_AGENT_ID_KNWU")
        self.assertEqual(create_agents.env_var_for("archief-agent"), "MISTRAL_AGENT_ID_ARCHIEF")

    def test_handoff_keten_wordt_opgelost_ongeacht_volgorde_in_config(self) -> None:
        # router -> regio -> knwu: de regio-agent heeft zelf ook een handoff.
        (self.root / "prompts" / "regio-agent.md").write_text("REGIO ADDENDUM", encoding="utf-8")
        regio = {
            "name": "regio-agent",
            "description": "Regio-agent",
            "prompt_files": ["_shared.md", "regio-agent.md"],
            "handoffs": ["knwu-agent"],
        }
        router = self.router_agent()
        router["handoffs"] = ["regio-agent"]
        config_path = self.make_config([router, regio, self.knwu_agent()])
        client = make_client(remote_libraries=[make_lib("knwu", "lib-knwu-1")])
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
        )

        self.assertEqual(report["errors"], [])
        self.assertEqual(rc, 0)
        calls = {c.kwargs["name"]: c.kwargs for c in client.beta.agents.create.call_args_list}
        self.assertEqual(calls["regio-agent"]["handoffs"], ["agent-knwu-agent"])
        self.assertEqual(calls["router-agent"]["handoffs"], ["agent-regio-agent"])

    def test_unknown_handoff_target_is_error(self) -> None:
        router = self.router_agent()
        router["handoffs"] = ["bestaat-niet"]
        config_path = self.make_config([router])
        client = make_client()
        report = self.empty_report()

        rc = create_agents.run_create(
            client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
        )

        self.assertEqual(rc, 1)
        self.assertTrue(any("bestaat-niet" in e for e in report["errors"]))
        client.beta.agents.create.assert_not_called()


class ProductieConfigTests(unittest.TestCase):
    """De echte agents_config.json + prompts, met een fake client."""

    def test_club_agent_zet_licentievragen_door_naar_knwu_agent(self) -> None:
        config_path = create_agents.DEFAULT_CONFIG_PATH
        client = make_client(
            remote_libraries=[make_lib(n, f"lib-{n}") for n in ("knwu", "regio", "club", "archive")]
        )
        report: create_agents.AgentReport = {"created": [], "updated": [], "errors": [], "agent_ids": {}}

        with redirect_stdout(io.StringIO()):
            rc = create_agents.run_create(
                client, create_agents.load_config(config_path), apply=True, report=report, config_path=config_path
            )

        self.assertEqual(rc, 0, report["errors"])
        calls = {c.kwargs["name"]: c.kwargs for c in client.beta.agents.create.call_args_list}
        self.assertEqual(calls["club-agent"]["handoffs"], ["agent-knwu-agent"])


if __name__ == "__main__":
    unittest.main()
