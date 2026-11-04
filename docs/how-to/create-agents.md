# Productie-agents aanmaken of updaten

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je de vijf MVP-agents (router-agent, knwu-agent, regio-agent, club-agent, archief-agent) aanmaakt of bijwerkt op Mistral Studio vanuit `scripts/agents_config.json` en de prompt-bestanden in `scripts/prompts/`. Architectuur en routeringsregels: [docs/system-prompt.md](../system-prompt.md); per-library RAG: [ADR-0003](../adr/0003-rag-over-eigen-documenten-kenniscentrum-autoriteit.md); websearch-scope: [ADR-0004](../adr/0004-websearch-beperkt-tot-kenniscentrum.md).

## Voorwaarden

- Draai met de project-venv: `.venv/Scripts/python scripts/create_agents.py`.
- `MISTRAL_API_KEY` staat in `.env` in de repo-root.
- De libraries moeten remote bestaan: draai eerst `python scripts/sync_libraries.py --apply` (als een library ontbreekt, meldt het script dat met die hint en slaat het de bijbehorende agent over).

## Agents aanmaken/updaten

1. Wijzig indien nodig de config (`scripts/agents_config.json`) of een prompt (`scripts/prompts/*.md`).
2. Draai een dry-run (default, read-only): `python scripts/create_agents.py`
3. Controleer de output: welke agents worden aangemaakt vs geüpdatet, welke tools/handoffs.
4. Voer uit: `python scripts/create_agents.py --apply`
5. Neem de agent-ids uit de summary over in `.env`:
   - `MISTRAL_AGENT_ID` = id van de router-agent (de app praat met de router; handoffs gaan via de Conversations API)
   - `MISTRAL_AGENT_ID_KNWU` / `MISTRAL_AGENT_ID_REGIO` / `MISTRAL_AGENT_ID_CLUB` / `MISTRAL_AGENT_ID_ARCHIEF` = ids van de content-agents (voor `eval/run_eval.py`)

## Controle dat het gelukt is

- De summary print per agent naam → id en de bijbehorende env-var.
- In Mistral Studio: 5 agents; per content-agent precies één `document_library`-tool met de juiste library; `web_search` alleen bij knwu-/regio-/club-agent; `handoffs` alleen op de router-agent.
- Zet géén `tool_configuration.include` op de `web_search`-tool: in `mistralai` 3.6.0 wordt de call dan wel geëmit maar nooit uitgevoerd. De domein-allowlist regelt server-side via org-level `/v1/web-filters` — zie [websearch-allowlist](websearch-allowlist.md).
- Model is `mistral-large-4` met `completion_args` `{"temperature": 0, "top_p": 1, "response_format": {"type": "text"}}` (`top_p=1` is verplicht bij temperature 0).

## Opmerkingen

- Het script is idempotent: een bestaande agent met dezelfde naam wordt geüpdatet (nieuwe versie), een missende aangemaakt. Draai het opnieuw na elke prompt- of configwijziging.
- Handoffs worden in een tweede fase naar agent-ids omgezet; een target die niet in de config staat en niet remote bestaat, is een error.
- Na het aanmaken/updaten van agents: re-run de eval-set (`python eval/run_eval.py`) met de agent-id env-vars gezet.
