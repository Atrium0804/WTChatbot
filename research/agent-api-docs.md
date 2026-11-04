# Research: Mistral Agents API via docs.mistral.ai — library attach, tools, modelstrings/fine-tunes (LeBaron-check)

- Ticket: [Research: Mistral Agents API via docs.mistral.ai — library attach, tools, modelstrings/fine-tunes (LeBaron-check)](https://github.com/Atrium0804/WTChatbot/issues/20)
- Parent map: [Wayfinder map — pilot-agent programmatisch aanmaken & gebruiken met Python (mistralai)](https://github.com/Atrium0804/WTChatbot/issues/18)
- Branch: `research/agent-api-docs` (throwaway — nooit mergen, geen PR)
- Methode: primaire bronnen = docs.mistral.ai (guides + API-reference) + read-only GET-calls tegen `api.mistral.ai` vanuit deze workspace met `mistralai==3.6.0` uit `.venv` (dotenv uit `.env`). Geen agents/libraries/conversations aangemaakt, gewijzigd of verwijderd.

## (a) Library koppelen aan een Agent + RAG-retrieval in conversations

- Er is géén apart `document_library`-veld op de agent. Een Library koppel je via de `tools`-lijst bij `POST /v1/agents` (`client.beta.agents.create(...)`):
  `tools=[{"type": "document_library", "library_ids": ["<library_id>"]}]`.
  Het `tools`-veld accepteert `FunctionTool | WebSearchTool | WebSearchPremiumTool | CodeInterpreterTool | ImageGenerationTool | DocumentLibraryTool | CustomConnector`.
  - Bronnen: https://docs.mistral.ai/agents/tools/built-in/document_library ("Connecting Libraries to agents"), https://docs.mistral.ai/api/endpoint/beta/agents (schema `POST /v1/agents`), https://docs.mistral.ai/agents/agents (`document_library` = "built-in RAG tool for knowledge grounding and search on custom data")
- Library-beheer zelf zit onder Beta Libraries (`POST /v1/libraries`, upload via `client.beta.libraries.documents.upload(library_id=..., file=...)`, processing-status `Running` → `Completed`). Een in Vibe aangemaakte library lees je uit de URL `https://chat.mistral.ai/libraries/<library_id>`.
  - Bronnen: https://docs.mistral.ai/api/endpoint/beta/libraries, https://docs.mistral.ai/agents/tools/built-in/document_library
- RAG-retrieval in conversations: start met `client.beta.conversations.start(agent_id=agent.id, inputs="...")` — bij een agent géén `model` meegeven ("pass `agent_id` instead of `model`. You can't pass both"). Het model bepaalt autonoom wanneer de `document_library`-tool wordt aangeroepen. De response bevat entries:
  - `tool.execution` — de library-zoekactie (name, `created_at`/`completed_at`, id);
  - `message.output` — het antwoord, `content` als list of chunks: `text` (antwoord) en `tool_reference` (citaten naar brondocumenten). `usage` bevat o.a. `connector_tokens` voor de library-search.
  - Bronnen: https://docs.mistral.ai/agents/tools/built-in/document_library ("Conversations with a Document Library agent" / "Understanding the response"), https://docs.mistral.ai/api/endpoint/beta/conversations, https://docs.mistral.ai/studio-api/connectors/conversations
- De Conversations API staat los van de Agents API: je kunt ook direct `POST /v1/conversations` doen met `model` + `tools` (zonder agent). `store=false` slaat de history niet server-side op; `stream=true` geeft SSE-events; `completion_args` overschrijft sampler-args; `inputs` is een string of een list van entries (`MessageInputEntry | ... | AgentHandoffEntry`).
  - Bron: https://docs.mistral.ai/api/endpoint/beta/conversations

## (b) web_search-tool + org-level allowlist (`/v1/web-filters`) — voor later, niet voor de pilot

- Tool attachen: `tools=[{"type": "web_search"}]` (eenvoudige search-engine) of `{"type": "web_search_premium"}` (search engine + nieuws via geïntegreerde news providers, o.a. AFP/AP). Alleen te gebruiken in de Agents/Conversations API (`/v1/conversations`), NIET in Chat Completions (`/v1/chat/completions`), omdat chat-completions geen search-referenties teruggeven.
  - Bronnen: https://docs.mistral.ai/studio/agents/agent-tools/websearch, https://docs.mistral.ai/agents/tools/built-in/websearch, https://docs.mistral.ai/agents/tools
- In de conversation: een `tool.execution` entry (name `web_search`) plus `message.output` met `text`- en `tool_reference`-chunks (`tool`, `title`, `url`, `source`) als citaten.
  - Bron: https://docs.mistral.ai/studio/agents/agent-tools/websearch ("Explanation of the Output")
- Org-level domain filtering: een Organization admin kan een allowlist of blocklist zetten op welke websites `web_search` mag retourneren. Filtering gebeurt vóór de agent de resultaten ziet (ook binnen `web_search_premium`). Gefilterde resultaten worden stilzwijgend verwijderd — niet geretourneerd, niet geciteerd, geen signaal in de response; als alles wordt gedropt, komt er niets terug. Dezelfde lijsten gelden voor `open_url`: een geblokkeerd domain geeft `451 Unavailable For Legal Reasons`. De docs verwijzen voor configuratie naar de admin-guide "Web search domain filtering".
  - Bron: https://docs.mistral.ai/studio/agents/agent-tools/websearch (sectie "Domain filtering")
- `/v1/web-filters` als publiek endpoint: read-only check in deze workspace gaf `GET https://api.mistral.ai/v1/web-filters -> 404 Not Found` (met onze API key). De endpoint zit dus niet op het publieke `/v1`-pad; de allowlist wordt door een org-admin geconfigureerd (console/admin), niet via de publieke API met deze key. Voor een latere fase; de pilot gebruikt géén websearch (library-only, zie de wayfinder-map).
- Indicatief tarief (voor latere budgettering): `web_search` $30 / 1000 calls, `web_search_premium` $50 / 1000 calls, bovenop model tokens.
  - Bron: https://mistral.ai/pricing/api/

## (c) Geldige model-strings in `agents.create` + LeBaron-check

- Schema `POST /v1/agents`: `model` is een required `string`. Geldig = elke model-id uit `GET /v1/models`, inclusief aliases (bijv. `mistral-large-latest`) en fine-tuned model-ids (`ft:<root>:<org>:<datum>:<suffix>`, in de models-list met `type: "fine-tuned"`, `job`, `root`). Docs-voorbeelden gebruiken o.a. `mistral-medium-latest` / `mistral-large-latest`.
  - Bronnen: https://docs.mistral.ai/api/endpoint/beta/agents (veld `model`), https://docs.mistral.ai/api/endpoint/models (model-object), https://docs.mistral.ai/agents/agents
- LeBaron-check (read-only, deze workspace, mistralai 3.6.0):
  - `client.models.list()`: géén model met "LeBaron" in de id en géén enkel `ft:`-model (alle `job: None`). `mistral-large-4` is WEL aanwezig (plus `mistral-large-4-0` en `mistral-large-latest`).
  - `GET /v1/fine_tuning/jobs` -> `410 Gone`: "Fine-tuning training has been deprecated and is no longer available. Existing fine-tuned models and LoRA adapter inference remain supported." → in deze workspace kan geen fine-tune "LeBaron" bestaan. De fine-tuning API is legacy/deprecated.
    - Bronnen: https://docs.mistral.ai/capabilities/finetuning ("Deprecated"), https://docs.mistral.ai/api/endpoint/models
  - Herkomst van "LeBaron": in de API-reference playground-voorbeelden van docs.mistral.ai staat letterlijk `model: "LeBaron"` als placeholder — vandaar `scripts/create_agents.py`. Het is een docs-placeholder, geen echt model.
    - Bron: https://docs.mistral.ai/api/endpoint/beta/agents
  - Conclusie: `mistral-large-4` is de juiste string voor de pilot (aanwezig in `GET /v1/models`; "Mistral Large 4 (`mistral-large-4`) ... Public Preview" volgens de changelog). "LeBaron" is in deze workspace ongeldig.
    - Bronnen: https://docs.mistral.ai/models, https://docs.mistral.ai/resources/changelogs
- SDK 3.6.0-oppervlak (introspectie, geen calls): `client.beta.agents.{create, update, get, list_pages, delete, ...}`, `client.beta.conversations.{start, start_stream, append, get_messages, ...}`, `client.models.{list, retrieve, archive, unarchive, ...}`. Let op: in 3.6.0 bestaat `client.agents` NIET (alleen `client.beta.agents`) en `client.fine_tuning` NIET (alleen `models.archive/unarchive` voor `ft:`-models; het jobs-endpoint is 410).

## (d) Handoffs / multi-agent in de Agents API (conceptueel, voor later)

- Handoffs = een agent kan mid-conversation de taak doorgeven aan een andere agent. Werkwijze: maak eerst alle agents aan en update ze daarna met `handoffs=[<ids van andere agents>]` (`client.beta.agents.update(agent_id=..., handoffs=[...])`). Onbeperkt aantal chained handoffs.
  - Bron: https://docs.mistral.ai/agents/handoffs
- `handoff_execution`: `"server"` (default; de handoff draait intern op Mistral-servers) of `"client"` (bij een trigger krijgt de client direct een response om de handoff zelf af te handelen). In de conversation verschijnen `agent.handoff` entries (`agent_id`, `agent_name`, timestamps); de volgende agent reageert in dezelfde conversation.
  - Bronnen: https://docs.mistral.ai/agents/handoffs, https://docs.mistral.ai/api/endpoint/beta/conversations (`AgentHandoffEntry`)
- Aandachtspunt: de Agents API v1-pagina's dragen de warning "The Agents API v1 is about to be deprecated. Build new agents with the Agents SDK." Voor de pilot met mistralai 3.6.0 blijft `client.beta.agents` het werkende pad; voor nieuw werk op termijn de Agents SDK (v2) bekijken.
  - Bron: https://docs.mistral.ai/agents/handoffs (warning bovenaan)

## Workspace-feiten (read-only GET, mistralai 3.6.0)

- `client.models.list()`: o.a. `mistral-large-4`, `mistral-large-4-0`, `mistral-large-latest`; géén "LeBaron", géén `ft:`-modellen.
- `GET /v1/fine_tuning/jobs` -> 410 (fine-tuning training deprecated; bestaande fine-tuned modellen / LoRA-inference blijven supported).
- `GET /v1/web-filters` -> 404 op het publieke pad.
- `client.beta.libraries.list()`: `club` (id `01a1411f-ea98-70a8-a3af-b9631fd39baa`, 5 docs), `knwu` (id `01a1411d-e9bc-747c-98c8-2808dae2094e`, 3 docs), plus `Data Vault en Data Engineering` (20 docs). `regio` / `archive` / `algemeen` ontbreken (consistent met de wayfinder-map).
- `client.beta.agents.list()`: leeg (0 agents remote).

## Bronnen (URLs waarop dit rapport leunt)

Primaire bronnen (docs.mistral.ai / mistral.ai):

- https://docs.mistral.ai/agents/agents
- https://docs.mistral.ai/agents/tools
- https://docs.mistral.ai/agents/tools/built-in/document_library
- https://docs.mistral.ai/agents/tools/built-in/websearch
- https://docs.mistral.ai/agents/handoffs
- https://docs.mistral.ai/api/endpoint/beta/agents
- https://docs.mistral.ai/api/endpoint/beta/conversations
- https://docs.mistral.ai/api/endpoint/beta/libraries
- https://docs.mistral.ai/api/endpoint/models
- https://docs.mistral.ai/studio/agents/introduction
- https://docs.mistral.ai/studio/agents/agents-api
- https://docs.mistral.ai/studio/agents/agent-tools/websearch
- https://docs.mistral.ai/studio-api/connectors/conversations
- https://docs.mistral.ai/capabilities/finetuning
- https://docs.mistral.ai/models
- https://docs.mistral.ai/resources/changelogs
- https://mistral.ai/news/agents-api/
- https://mistral.ai/pricing/api/

Read-only workspace-checks (geen writes): `GET /v1/models`, `GET /v1/fine_tuning/jobs`, `GET /v1/web-filters`, `client.beta.libraries.list()`, `client.beta.agents.list()` via `mistralai==3.6.0`.

## Consequentie voor de pilot (uit de wayfinder-map)

Voor de pilot-agent `knwu-agent-pilot` volstaat: `client.beta.agents.create(model="mistral-large-4", name=..., instructions=..., tools=[{"type": "document_library", "library_ids": ["01a1411d-e9bc-747c-98c8-2808dae2094e"]}], completion_args={"temperature": 0})`, daarna `client.beta.conversations.start(agent_id=..., inputs="...")` en aan het eind `client.beta.agents.delete(agent_id=...)`. Geen web_search-tool in de pilot; de RAG-citaten zitten in de `tool_reference`-chunks van `message.output`.
