# Productie-agents aanmaken of updaten

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je de vijf MVP-agents (router-agent, knwu-agent, regio-agent, club-agent, archief-agent) aanmaakt of bijwerkt op Mistral Studio vanuit de actieve architectuur-variant (`scripts/architectures/active` wijst naar `scripts/architectures/<naam>.json`, standaard `huidig.json`) en de prompt-bestanden in `scripts/prompts/`. Architectuur en routeringsregels: [docs/system-prompt.md](../system-prompt.md) en [ADR-0009](../adr/0009-agent-architectuur-snelheid.md); per-library RAG: [ADR-0003](../adr/0003-rag-over-eigen-documenten-kenniscentrum-autoriteit.md); websearch-scope: [ADR-0004](../adr/0004-websearch-beperkt-tot-kenniscentrum.md).

## Voorwaarden

- Draai met de project-venv: `.venv/Scripts/python scripts/create_agents.py`.
- `MISTRAL_API_KEY` staat in `.env` in de repo-root.
- De libraries moeten remote bestaan: draai eerst `python scripts/sync_libraries.py --apply` (als een library ontbreekt, meldt het script dat met die hint en slaat het de bijbehorende agent over).

## Agents aanmaken/updaten

1. Wijzig indien nodig de actieve variant (`scripts/architectures/huidig.json`) of een prompt (`scripts/prompts/*.md`).
2. Draai een dry-run (default, read-only): `python scripts/create_agents.py`
3. Controleer de output: welke agents worden aangemaakt vs geüpdatet, welke tools/handoffs.
4. Voer uit: `python scripts/create_agents.py --apply`
5. Neem de agent-ids uit de summary over in `.env`:
   - `MISTRAL_AGENT_ID` = id van de router-agent (de app praat met de router; handoffs gaan via de Conversations API)
   - `MISTRAL_AGENT_ID_KNWU` / `MISTRAL_AGENT_ID_REGIO` / `MISTRAL_AGENT_ID_CLUB` / `MISTRAL_AGENT_ID_ARCHIEF` = ids van de content-agents (voor direct-to-expert in de app en voor `eval/run_eval.py`)

## Architectuur switchen (#95)

De agent-architectuur is switchbaar via de `active`-pointer; agent-namen zijn identiek over varianten heen, dus `create_agents.py` update de remote agents in-place en de `.env`-ids blijven geldig.

1. Kies de variant: zet de naam in `scripts/architectures/active` (bv. `huidig` -> `scripts/architectures/huidig.json`; een nieuwe variant maak je als kopie van een bestaande `<naam>.json`).
2. Dry-run: `python scripts/create_agents.py` (leest automatisch via de pointer; `--config <pad>` override't).
3. Voer uit: `python scripts/create_agents.py --apply`.
4. Check in de summary en in `.env` dat `MISTRAL_AGENT_ID` (en de expert-ids) nog kloppen — de namen zijn gelijk, de ids kunnen per variant verschillen als een agent opnieuw is aangemaakt.
5. Controleer: `/healthz` van de app + eval draaien (`python eval/run_eval.py`).

## Controle dat het gelukt is

- De summary print per agent naam -> id en de bijbehorende env-var.
- In Mistral Studio: 5 agents; per content-agent precies één `document_library`-tool met de juiste library; `web_search` alleen bij knwu-/regio-/club-agent; `handoffs` op de router-agent (naar knwu/regio/club) en direct expert-naar-expert (ADR-0009, geen return-handoff naar de router).
- Zet géén `tool_configuration.include` op de `web_search`-tool: in `mistralai` 3.6.0 wordt de call dan wel geëmit maar nooit uitgevoerd. De domein-allowlist regelt server-side via org-level `/v1/web-filters` — zie [websearch-allowlist](stel-websearch-allowlist-in.md).
- Model is `mistral-large-latest` voor de content-agents en `mistral-small-latest` voor de router-agent (ADR-0009), met `completion_args` `{"temperature": 0, "top_p": 1, "response_format": {"type": "text"}, "reasoning_effort": "medium"}` (`top_p=1` is verplicht bij temperature 0). Beide modellen redeneren: zonder `reasoning_effort` redeneert Mistral Large 4 op `high`, wat een antwoord ruim een minuut trager maakt (#144). De router-agent overschrijft dit met een eigen `completion_args` `{"reasoning_effort": "none"}`, want `mistral-small` kent alleen `none` en `high`. Per-agent `completion_args` worden per sleutel over de globale heen gelegd.

## Opmerkingen

- Het script is idempotent: een bestaande agent met dezelfde naam wordt geüpdatet (nieuwe versie), een missende aangemaakt. Draai het opnieuw na elke prompt- of variantwijziging.
- Handoffs worden in een tweede fase naar agent-ids omgezet; een target die niet in de variant staat en niet remote bestaat, is een error.
- Een `active`-pointer die naar een onbestaande variant wijst, is een harde error (het script weigert te draaien) — check de naam vóór `--apply`.
- Na het aanmaken/updaten van agents: re-run de eval-set (`python eval/run_eval.py`) met de agent-id env-vars gezet.
- Van feedback naar een prompt-wijziging: zie [gebruik feedback om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md) (issue #55).
