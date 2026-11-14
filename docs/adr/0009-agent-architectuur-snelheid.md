---
status: accepted
---

# Agent-architectuur voor snelheid: kleine router, geen zoek-agents, geen return-handoff, deterministische bypass

Wielie stuurde elke vraag via een `router-agent` (mistral-medium-latest) naar een
domeinexpert (knwu/regio/club, mistral-large-latest) die weer terug-handoffde naar de
router. Elke handoff is een volledige nieuwe model-call met de hele conversatiegeschiedenis
als input; de eval mat gemiddeld 3,2 agent-calls per vraag (tot 7 bij websearch) en een
gemakkelijke lookup-vraag kostte 2 LLM-calls. `mistral-medium-latest` is bovendien sinds
2026-10-31 deprecated en per output-token duurder dan large ($7.50 vs $2.10 per MTok).

Besluit (wayfinder-map #86, tickets #88/#91/#93/#95): de router draait op
`mistral-small-latest` en is alléén de voordeur; de app start bij hoge intake-confidence
direct een conversatie bij de juiste expert (direct-to-expert). Er komen geen aparte
kleine zoek-agents: RAG (`document_library`) blijft in de domeinexperts, omdat een extra
zoek-agent een extra handoff toevoegt zonder de antwoord-call te besparen. Experts
handoffen bij onderwerpwissel direct naar elkaar, niet meer terug naar de router. Pure
lookup-vragen (leeftijdscategorie, licentie, maximaal verzet per discipline, oude
categorie-indeling — alles in `app/knwu_categories.json`) beantwoordt de app
deterministisch zonder LLM; de library wordt pas geraadpleegd bij vervolg- of
uitlegvragen. De app streamt de run (SSE) zodat de gebruiker de fase ziet
("Ik doorzoek de KNWU-regelgeving…", "Ik raadpleeg kenniscentrum.knwu.nl…"), en zet
prompt caching aan (cached input = 10% van de prijs). De architectuur is switchbaar via
`scripts/architectures/active` (zie #95).

## Considered options

- **Router large + aparte kleine zoek-agents (optie A)** — verworpen: de router heeft geen
  zware reasoning nodig; large heeft een hogere time-to-first-token dan small, en de
  zoek-agents voegen hops toe.
- **Router medium + KNWU-expert large + kleine zoek-agents (optie B)** — gedeeltelijk
  overgenomen (expert blijft large); medium-router verworpen (deprecated en duurst per
  output), zoek-agents verworpen (extra handoff per vraag).
- **Volledige migratie naar Mistral Managed Agents (#70)** — out of scope voor deze
  effort; `web_search`/`document_library`/handoffs zitten alleen in de Conversations API.

## Consequences

- Een makkelijke lookup-vraag kost 0 LLM-calls (was 2); overige vragen gaan van 3,2
  naar ca. 2 calls (router small + expert, zonder return-handoff).
- Router-call is ~90% goedkoper per token dan de oude medium-router.
- Trade-off: een small router is zwakker bij vage vragen — gecompenseerd door de
  light-model intake in de app (#91) die bij lage confidence de router inschakelt.
- `agents_config.json` wordt bij de implementatie gemigreerd naar
  `scripts/architectures/huidig.json`; de prompts in `scripts/prompts/` zijn al
  aangepast (geen return-handoff, direct expert→expert, lookups via de contextregel).
- ADR-0006 (verzettencalculator, post-MVP) raakt de deterministische max-verzet-lookup
  (#94) maar niet deze architectuur.
