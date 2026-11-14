"""Tests voor de SSE-event -> fase mapping (#93/#90) — offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import phases  # noqa: E402


def test_handoff_naar_knwu_agent_zet_knwu_fase():
    assert phases.phase_for_event(
        "agent.handoff.done", {"next_agent_name": "knwu-agent"}, "router-agent"
    ) == (phases.PHASE_KNWU, "knwu-agent")


def test_handoff_naar_regio_of_club_zet_regio_club_fase():
    for naam in ("regio-agent", "club-agent", "archief-agent"):
        fase, agent = phases.phase_for_event("agent.handoff.done", {"next_agent_name": naam}, "router-agent")
        assert fase == phases.PHASE_REGIO_CLUB
        assert agent == naam


def test_document_library_bij_knwu_is_knwu_fase():
    assert phases.phase_for_event(
        "tool.execution.started", {"name": "document_library"}, "knwu-agent"
    ) == (phases.PHASE_KNWU, "knwu-agent")


def test_document_library_bij_club_is_regio_club_fase():
    assert phases.phase_for_event(
        "tool.execution.started", {"name": "document_library"}, "club-agent"
    ) == (phases.PHASE_REGIO_CLUB, "club-agent")


def test_web_search_zet_web_fase():
    assert phases.phase_for_event(
        "tool.execution.started", {"name": "web_search"}, "knwu-agent"
    ) == (phases.PHASE_WEB, "knwu-agent")


def test_eerste_delta_zet_opstellen_fase():
    assert phases.phase_for_event(
        "message.output.delta", {"content": "Hallo"}, "knwu-agent"
    ) == (phases.PHASE_OPSTELLEN, "knwu-agent")


def test_overige_events_geven_geen_wijziging():
    assert phases.phase_for_event("tool.execution.done", {"name": "web_search"}, "knwu-agent") is None
    assert phases.phase_for_event("conversation.response.started", {}, "router-agent") is None


def test_fase_voor_startagent_direct_to_expert():
    assert phases.fase_voor_startagent("knwu-agent") == phases.PHASE_KNWU
    assert phases.fase_voor_startagent("club-agent") == phases.PHASE_REGIO_CLUB
    assert phases.fase_voor_startagent("router-agent") == phases.PHASE_LEES
    assert phases.fase_voor_startagent("onbekend") == phases.PHASE_LEES
