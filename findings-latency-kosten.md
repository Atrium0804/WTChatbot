# Findings: latency en kosten — huidige topologie vs optie A/B (issue #89)

Datum: 2026-11-13. Alle prijzen in USD per 1M tokens tenzij anders vermeld.
Primaire bronnen: `mistral.ai/pricing/api/` (API pricing, geraadpleegd 2026-11-13), `docs.mistral.ai` (models overview, websearch, handoffs, conversations), eigen repo (`scripts/agents_config.json`, `app/mistral_client.py`, `eval/last_run.json`).

## 1. Prijzen per model (per 1M tokens, input / output)

Bron: `https://mistral.ai/pricing/api/` (officiële pricingpagina, geraadpleegd 2026-11-13); lifecycle via docs.mistral.ai models overview + deprecationmeldingen.

| Model (zoals in repo) | Resolves naar (eind 2026) | Input | Cached input | Output | Opmerking |
|---|---|---|---|---|---|
| `mistral-large-latest` | Mistral Large 4 | $0.70 | $0.07 | $2.10 | 1M context; GA-prijs sinds 2026-10-29 (preview was $1.36/$4.18) |
| `mistral-medium-latest` | Mistral Medium 3.5 | $1.50 | $0.15 | $7.50 | **Deprecated 2026-10-31, retire 2027-04-30**; staat niet meer op de pricingpagina (laatst bevestigde prijs) |
| `mistral-small-latest` | Mistral Small 4 | $0.15 | $0.015 | $0.60 | 256K context |
| (alternatief klein) | Ministral 3 3B / 8B / 14B | $0.10 / $0.15 / $0.20 | 10% thereof | $0.10 / $0.15 / $0.20 | Laagste TTFT (~1.5s voor 3B, bron: Artificial Analysis) |

Belangrijk: `mistral-medium-latest` is **duurder per output-token dan `mistral-large-latest`** ($7.50 vs $2.10 per MTok) en is deprecated. De `-latest`-aliases kunnen van gedag/prijs veranderen zonder aankondiging (model lifecycle policy).

Aanvullende meters (bovenop tokenprijs, bron: Mistral agent-tools pricing zoals gedocumenteerd bij La Plateforme):
- `web_search` tool: **$30 per 1.000 calls** ($0.03/call); `web_search_premium` nieuws $50/1.000.
- `document_library` (RAG) tool: **$1 per MTok geïndexeerd + $0.01 per call**.
- Prompt caching: cached input kost **10%** van de normale inputprijs (opt-in via `prompt_cache_key`).
- Batch processing: 50% korting; Priority tier: 1.75x.

## 2. Latency per handoff en per websearch/RAG-call

- Elke handoff is een **volledige nieuwe model-call met de hele conversatiegeschiedenis als input** (conversation entries worden server-side bewaard; zie docs.mistral.ai handoffs/conversations). Dat betekent: nieuwe TTFT (prefill schaalt met promptlengte; decode ~10–50 ms/token afhankelijk van model) + volledige generatie, én de hele history wordt opnieuw als input gefactureerd.
- Elke `web_search`/RAG-call is een extra tool-roundtrip (seconden) gevolgd door nóg een model-call met de toolresultaten in context.
- Bewijs uit eigen repo: `app/mistral_client.py` had de timeout moeten verhogen van 60s naar **180s** "omdat websearch/handoff-runs in een timeout liepen" — de multi-agent loop is traag zat om de standaard timeout te raken.
- De app gebruikt **niet-streaming** `POST /v1/conversations` (`mistral_client.py`); de Conversations API ondersteunt wel streaming (`stream: true` / `startStream`, SSE) — dat verlaagt de *waargenomen* latency (TTFT zichtbaar) zonder kosten te veranderen.
- Kleinste modellen hebben de laagste TTFT (Ministral 3 3B ~1.5s, Small 4 ~1.6s; Large-modellen hoger).

## 3. Wat kost een "gemakkelijke" vraag nu (eigen eval-data)

Bron: `eval/last_run.json` (28 eval-vragen): in totaal **90 agent-calls ≈ 3,2 per vraag**. Verdeling: 2 calls ×10 vragen, 3×2, 4×6, 5×4, 6×2, 7×1, 1×1, 0×2. Per agent: knwu-agent 49, regio-agent 19, club-agent 17, router-agent 5.

Een gemakkelijke vraag (categorie/verzet) = **minimaal 2 LLM-calls**: router-agent (medium) → handoff → expert (large) + 1 RAG-call (`document_library`, $0.01); bij websearch-vragen loopt dit op tot 5–7 calls (10/28 vragen hadden exact 2 calls; websearch-type 14 calls over 7 vragen). De app injecteert bovendien per beurt contextregels (`app/context.py` CONTEXT_HEADER) — extra input-tokens per call.

Rekenvoorbeeld (aannames: per LLM-call ~4k input-tokens incl. RAG-chunks, ~400 output-tokens):

| Scenario | Calls | Kosten per vraag (indicatief) |
|---|---|---|
| Huidig: router medium + expert large + RAG | 2 LLM + 1 RAG | router: 4k×$1.50 + 0.4k×$7.50 ≈ $0.009; expert: 4k×$0.70 + 0.4k×$2.10 ≈ $0.0036; RAG $0.01 → **≈ $0.023** |
| + websearch (moeilijke vraag) | +1–5 calls | +$0.03 per web_search + extra expert-calls à ~$0.004 → **≈ $0.04–0.06** |
| Optie A: router large + kleine zoek-agents + expert | router large ≈ $0.0036/call | Router-call is **goedkoper dan vandaag** (medium $7.50 out > large $2.10 out), maar TTFT hoger dan small |
| Optie B: router medium + expert large + zoek-agents small | zoek-call small: 4k×$0.15 + 0.4k×$0.60 ≈ $0.0008 | Zoek/RAG-reasoning op small ≈ **90% goedkoper** dan large; router-call even duur als vandaag |

## 4. Goedkoper pad binnen de Conversations API — en wat je mist

- **Conversatie direct starten bij de expert-agent** (`agent_id` van bv. knwu-agent i.p.v. de router) en routing in de app doen — de repo heeft al categorie-lookup (`app/knwu_categories.json`). Bespaart 1 LLM-call per vraag. Wat je mist: semantische routing bij vage vragen en handoff-terug naar de router.
- **Router op een klein model** (small-latest of Ministral 8B): classificatie is een makkelijke taak; small kost $0.15/$0.60 vs medium $1.50/$7.50. Grootste kostenhefboom in de huidige topologie.
- **Prompt caching** (`prompt_cache_key`): 90% korting op cached input — relevant omdat elke handoff de hele history opnieuw stuurt.
- **Streaming** (`stream: true` op `/v1/conversations`): geen kostenvoordeel, wel veel betere perceived latency bij multi-agent runs.
- **Buiten de Conversations API** (Chat Completions + eigen RAG): `web_search` en `document_library` werken **alleen** in Conversations/Agents API (docs.mistral.ai websearch: "aren't supported in the Chat Completions API"), net als handoffs en tool-references/citaties. Daar vallen dus de ingebouwde websearch-citaties en RAG weg; je moet zelf search + retrieval bouwen en de resultaten in de prompt injecteren.

## 5. Conclusie (huidig vs A vs B)

- De duurste schakel is vandaag **niet** de expert (large $2.10 out) maar de **router op deprecated medium-latest ($7.50 out)** plus het aantal calls (gem. 3,2/vraag, tot 7 bij websearch).
- Optie B (router klein/medium + expert large + kleine zoek-agents) is de sterkste kosten-/latency-winst: zoekstappen naar small/Ministral, expert blijft large voor kwaliteit.
- Optie A (router large) is qua tokenkosten vergelijkbaar met vandaag (large < medium per token), maar qua latency slechter (hogere TTFT router) — alleen zinvol als de router complexere reasoning nodig heeft.
- Ongeacht A/B: direct starten bij de expert waar de app zelf kan routeren, prompt caching aan, en streaming aan — drie hefbomen zonder architectuurwijziging.

## Bronnen

- `https://mistral.ai/pricing/api/` — officiële API-prijzen per 1M tokens (geraadpleegd 2026-11-13)
- `https://docs.mistral.ai/getting-started/models/models_overview` — modeloverzicht (Large 4, Small 4, Ministral 3)
- `https://docs.mistral.ai/studio/agents/agent-tools/websearch` — web_search alleen in Conversations/Agents API
- `https://docs.mistral.ai/studio/agents/handoffs` — handoff-architectuur (server-side, history behouden)
- Mistral agent-tools pricing (web_search $30/1.000 calls; document_library $1/MTok index + $0.01/call; prompt caching 10%)
- Mistral model lifecycle: Medium 3.5 deprecated 2026-10-31, retire 2027-04-30
- Artificial Analysis — TTFT per model (Ministral 3 3B ~1.5s, Small 4 ~1.6s)
- Repo: `scripts/agents_config.json`, `app/mistral_client.py` (timeout 180s), `app/context.py`, `eval/last_run.json` (90 agent-calls / 28 vragen)
