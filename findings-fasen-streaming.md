# Findings: zichtbare fasen — streaming/events van de Conversations API vs poll-only (issue #90)

Datum: 2026-11-14.
Primaire bronnen: `docs.mistral.ai/api/endpoint/beta/conversations` (API-reference, geraadpleegd 2026-11-14), `docs.mistral.ai/agents/agents` + `docs.mistral.ai/agents/handoffs/`, en de officiële SDK-definities `github.com/mistralai/client-python` (`src/mistralai/client/models/conversationevents.py`, `ssetypes.py`, `toolexecutionstartedevent.py`, `agenthandoffstartedevent.py`, `conversationhistory.py`, `builtinconnectors` — geraadpleegd 2026-11-14). Eigen repo: `app/mistral_client.py`, `app/main.py` (#85), `app/static/index.html` (#84), `scripts/trace_conversation.py`, `scripts/agents_config.json`.

## 1. Ja — POST /v1/conversations ondersteunt streaming (SSE)

- `POST /v1/conversations` en `POST /v1/conversations/{conversation_id}` accepteren `"stream": true` in de body (standaard `false` op de gewone operatie; de aparte `#stream`-operatie op hetzelfde pad heeft `stream` default `true`). Bij `stream: true` is het 200-antwoord `text/event-stream` (`event-stream<ConversationEvents>`), niet één JSON-blob. Bron: API-reference "Beta Conversations" (`docs.mistral.ai/api/endpoint/beta/conversations`).
- SDK-equivalent: `mistral.beta.conversations.start_stream(...)` / `.append_stream(...)`; de loop eindigt wanneer de server de stream sluit. In de repo gebruiken we plain `requests` (`app/mistral_client.py`), dus: `requests.post(..., stream=True)` + `resp.iter_lines()` parsen als SSE — geen nieuwe dependency nodig.
- Wire-format: elke SSE-event is `data: {"event": "<type>", "data": { ... }}` (velden `event` + `data` op `ConversationEvents`, zie SDK-model).

## 2. De exacte event-types (10 stuks) — genoeg voor fase-teksten

Volledige lijst uit `SSETypes` (SDK, `docs/models/ssetypes.md`):

| Event | Belangrijkste velden in `data` | Fase die we hieruit kunnen afleiden |
|---|---|---|
| `conversation.response.started` | `conversation_id` | job kan direct het Mistral-conversation-id opslaan (nu pas bekend aan het einde) |
| `conversation.response.done` | `usage` | einde van de hele run |
| `conversation.response.error` | `message`, `code` | foutafhandeling |
| `message.output.delta` | `content` (chunks), `agent_id`, `model`, `role: "assistant"`, `content_index`/`output_index` | live antwoordtekst + welke agent_id antwoordt |
| `tool.execution.started` | `name`, `arguments` (JSON-string), `agent_id`, `model` | **welke tool draait nu** |
| `tool.execution.delta` | `name`, `arguments` | tool-args streamen (niet nodig voor fasen) |
| `tool.execution.done` | `name`, `info` | tool klaar |
| `agent.handoff.started` | `previous_agent_id`, `previous_agent_name` | "router-agent geeft door…" |
| `agent.handoff.done` | `next_agent_id`, `next_agent_name` | **naar welke agent** (knwu-agent / regio-agent / club-agent) |
| `function.call.delta` | `name`, `arguments`, `tool_call_id`, `confirmation_status` | custom function-calls (wij gebruiken geen eigen functions) |

- `tool.execution.*` `name` is een enum van built-in connectors: `web_search`, `web_search_premium`, `code_interpreter`, `image_generation`, `document_library`, `mistral_mcp` (bron: SDK `BuiltInConnectors`). De **library-naam zit niet in het event** — alleen `document_library` + `agent_id`. De koppeling agent→library staat in onze eigen config (`scripts/agents_config.json`: knwu-agent→library `knwu`, regio-agent→`regio`, club-agent→`club`, archief-agent→`archive`), en de handoff-events dragen wél agent-**namen**. agent_id→naam mapping is dus te bouwen uit de handoff-events (of eenmalig via `GET /v1/agents`).
- Mapping naar de gewenste fase-teksten: `agent.handoff.done(next_agent_name="knwu-agent")` → "Ik ga naar de KNWU-agent…"; `tool.execution.started(name="document_library", agent_id=<knwu>)` → "Ik doorzoek de KNWU-regelgeving…"; `tool.execution.started(name="web_search")` → "Ik raadpleeg kenniscentrum.knwu.nl…" (websearch zit alleen op knwu/regio/club, zie `scripts/agents_config.json`).
- Let op: in de **non-streaming** response heten de entries `agent.handoff`, `tool.execution`, `message.output` (zie `extract_text` in `app/mistral_client.py` en `scripts/trace_conversation.py`); in de **stream** zijn het aparte `.started/.delta/.done`-events. `extract_text`'s "tekst vóór de laatste agent.handoff telt niet mee"-regel heeft in streaming zijn equivalent: `message.output.delta`s met een `agent_id` vóór de laatste `agent.handoff.done` negeren.

## 3. Poll-only (`/chat/status` + Mistral `/history`) is niet genoeg voor live fasen

- De non-streaming `POST /v1/conversations` returnt pas als de héle run klaar is — onze `/chat/status/{job_id}` (#85, `app/main.py`) pollt dáár de job-state van, dus zonder streaming blijft `phase` tot het einde "Wielie denkt na…". Poll-only levert dus géén tussenstadia.
- `GET /v1/conversations/{id}/history` geeft wél entries (`message.input`, `message.output`, `function.call`, `function.result`, `tool.execution`, `agent.handoff` — bron: SDK `ConversationHistory`; dit is wat `scripts/trace_conversation.py` leest), maar de docs garanderen niet dat entries mid-run al zichtbaar zijn; wij lezen ze nu alleen ná afronding.Conclusie: voor live fasen is **streaming nodig**; poll van `/history` is hooguit een ongedocumenteerde fallback.
- Praktisch voor de app: laat de background job (#85) de SSE server-side consumeren (`requests` met `stream=True` in de threadpool), vertaal events naar `job["phase"]` in `state["jobs"]`, en laat de frontend simpelweg blijven pollen op `/chat/status` (reeds geïmplementeerd in `index.html`, 500 ms). Browser→Mistral directe SSE is geen optie: CSP is `default-src 'self'` (`app/main.py`), dus server-side streamen is de juiste seam.
- Timeout-opmerking: `DEFAULT_TIMEOUT = 180` in `mistral_client.py` is nu een read-timeout op de hele call; bij streaming is een (connect, read)-tuple verstandig zodat een stille stream niet 180s hangt.

## 4. Staged fallback-tijdmeldingen (#84) blijven nodig

- `app/static/index.html` (#84) toont timer-gebaseerde berichten (direct "Wielie denkt na…", ~15s "Ik zoek in de reglementen…", ~45s "Dit duurt langer…"), een `AbortController` na ~120s en max. één retry bij netwerkfout. #85 voegt daar het echte `phase`-veld uit `/chat/status` aan toe, met de staged berichten als terugval (zie acceptatiecriterium #85: "bij wegvallen van de status blijven de staged-tijdmeldingen werken").
- Met streaming wordt `phase` gevuld uit echte events; de #84-timers blijven als fallback relevant voor: stub-mode, SSE-fouten, proxy-buffering, of als de stream wegvalt — kortom: ja, houden.

## Aanbeveling (samenvatting)

Voeg `stream: true` toe aan de calls in `app/mistral_client.py`, consume de SSE in de #85-background-job, en leid `phase` af uit `agent.handoff.done` (next_agent_name) + `tool.execution.started` (name + agent_id→library via `scripts/agents_config.json`). `/chat/status` en de typing-bubble in `index.html` hoeven daarvoor niet te wijzigen; de #84-staged-berichten blijven als fallback.
