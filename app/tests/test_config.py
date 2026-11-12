"""Tests voor ENV_FILE: een alternatieve env-file zoals .env.local (issue #59) — offline."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def test_env_file_relatief_aan_repo_root_wordt_geladen(tmp_path, monkeypatch):
    # setenv + delenv: monkeypatch herstelt na de test de oorspronkelijke waarde.
    monkeypatch.setenv("MISTRAL_AGENT_ID", "")
    monkeypatch.delenv("MISTRAL_AGENT_ID")
    (tmp_path / ".env.local").write_text("MISTRAL_AGENT_ID=test-router-id\n", encoding="utf-8")

    config.load_env_file(".env.local", tmp_path)

    assert config.os.environ["MISTRAL_AGENT_ID"] == "test-router-id"


def test_ontbrekende_env_file_geeft_duidelijke_fout(tmp_path):
    with pytest.raises(RuntimeError, match="ENV_FILE bestaat niet"):
        config.load_env_file(".env.local", tmp_path)
