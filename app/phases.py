"""Fase-teksten voor de typing-indicator (#93, events uit #90).

Zes vaste fasen; de #85-background-job vertaalt SSE-events van de Mistral
Conversations API (stream: true) naar job["phase"] via phase_for_event().
De UI pollt /chat/status en toont de fase; de staged-tijdmeldingen (#84)
blijven als fallback. Bij een deterministische bypass (#91) is er géén
fase — het antwoord verschijnt direct.
"""

PHASE_LEES = "Ik lees je vraag…"
PHASE_BEREKEN = "Ik bereken de leeftijdscategorie…"
PHASE_KNWU = "Ik doorzoek de KNWU-regelgeving…"
PHASE_REGIO_CLUB = "Ik doorzoek de regio-/clubdocumenten…"
PHASE_WEB = "Ik raadpleeg kenniscentrum.knwu.nl…"
PHASE_OPSTELLEN = "Ik stel je antwoord op…"
PHASE_KLAAR = "Klaar"
PHASE_FOUT = "Fout"

# agent-naam -> fase bij handoff/tool-call
AGENT_FASE = {
    "knwu-agent": PHASE_KNWU,
    "regio-agent": PHASE_REGIO_CLUB,
    "club-agent": PHASE_REGIO_CLUB,
    "archief-agent": PHASE_REGIO_CLUB,
    "router-agent": PHASE_LEES,
}


def fase_voor_startagent(agent_naam: str) -> str:
    """Beginfase als de conversatie direct bij een expert start (direct-to-expert)."""
    return AGENT_FASE.get(agent_naam, PHASE_LEES)


def phase_for_event(event: str, data: dict, current_agent: str) -> tuple[str, str] | None:
    """Map één SSE-event naar (nieuwe fase, nieuwe current_agent).

    Geef None als het event geen fase-wijziging oplevert. `current_agent`
    is de agent-naam van de lopende beurt (uit agent.handoff.done of de
    start-agent); document_libraryCalls van de knwu-agent -> KNWU-fase,
    van regio/club/archief -> regio-/club-fase.
    """
    if event == "agent.handoff.done":
        next_agent = str(data.get("next_agent_name") or current_agent)
        return AGENT_FASE.get(next_agent, PHASE_LEES), next_agent
    if event == "tool.execution.started":
        name = str(data.get("name") or "")
        if name == "document_library":
            return (PHASE_KNWU if current_agent == "knwu-agent" else PHASE_REGIO_CLUB), current_agent
        if name.startswith("web_search"):
            return PHASE_WEB, current_agent
        return None
    if event == "message.output.delta":
        return PHASE_OPSTELLEN, current_agent
    return None
