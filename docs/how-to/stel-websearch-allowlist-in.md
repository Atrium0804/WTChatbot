# Websearch-allowlist configureren via org-level web-filters

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je de domeinen beperkt die de `web_search`-tool mag raadplegen. De beslissing en scope (allowlist: `knwu.nl`, `knwumidden.nl`, `wtcwoerden.nl`) staan in [ADR-0004](../adr/0004-websearch-beperkt-tot-kenniscentrum.md); deze pagina beschrijft alleen de configuratie.

Mistral domeinfiltering is een **org-level** governance-control, geconfigureerd via de REST-endpoints onder `https://api.mistral.ai/v1/web-filters`. Er is (nog) geen Admin Panel-pagina voor — API-only — en de endpoints zitten (nog) niet in de `mistralai`-SDK (getest met 3.6.0), dus gebruik `curl` of `httpx` uit de project-venv.

> De web-filters zijn **org-breed**: één setting en twee lijsten per Organization, toegepast op álle keys en applicaties in die org — niet per workspace of agent. Schakel de allowlist daarom alleen in als deze Mistral-Organization exclusief voor de WTChatbot is gereserveerd; in een gedeelde org niet gebruiken en de scope via het system prompt afdwingen. Zie [ADR-0004](../adr/0004-websearch-beperkt-tot-kenniscentrum.md) (amendment 2026-11-04).

## Voorwaarden

- `MISTRAL_API_KEY` in `.env` in de repo-root. De key moet bij de Organization horen; bij een user-key heeft die user de Organization admin-rol nodig. Geverifieerd met de project-key: `GET /v1/web-filters/config` geeft `200`.
- `curl`, of Python met `httpx` (zit in `.venv` als dependency van `mistralai`).

## Huidige configuratie lezen

```bash
export MISTRAL_API_KEY="..."  # of lees uit .env
curl "https://api.mistral.ai/v1/web-filters/config" \
  -H "Authorization: Bearer $MISTRAL_API_KEY"
# -> {"block_by_default": null}   (null = nog geen filtering geconfigureerd)

curl "https://api.mistral.ai/v1/web-filters/domains/allowed" \
  -H "Authorization: Bearer $MISTRAL_API_KEY"
curl "https://api.mistral.ai/v1/web-filters/domains/blocked" \
  -H "Authorization: Bearer $MISTRAL_API_KEY"
# -> {"domains": [...]}
```

Python-equivalent:

```python
import os, httpx
from dotenv import load_dotenv
load_dotenv()
h = httpx.Client(base_url="https://api.mistral.ai", timeout=20,
                 headers={"Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}"})
print(h.get("/v1/web-filters/config").json())          # {"block_by_default": ...}
print(h.get("/v1/web-filters/domains/allowed").json())  # {"domains": [...]}
```

Huidige state van onze org (gelezen met de project-key): `block_by_default` is `null` en beide lijsten zijn leeg — filtering staat nog **uit**.

## Allowlist instellen (knwu.nl, knwumidden.nl, wtcwoerden.nl)

1. Zet de default-actie op block (allowlist-modus):
   `curl -X PUT "https://api.mistral.ai/v1/web-filters/config" -H "Authorization: Bearer $MISTRAL_API_KEY" -H "Content-Type: application/json" -d '{"block_by_default": true}'`
2. Voeg de gezaghebbende domeinen toe aan de allowlist:
   `curl -X POST "https://api.mistral.ai/v1/web-filters/domains/allowed" -H "Authorization: Bearer $MISTRAL_API_KEY" -H "Content-Type: application/json" -d '{"domains": ["knwu.nl", "knwumidden.nl", "wtcwoerden.nl"]}'`
3. Controleer: herhaal de GET-calls uit "Huidige configuratie lezen" — `block_by_default` moet `true` zijn en de drie domeinen in `allowed` staan.

## Domeinen beheren

Per lijst (`allowed` of `blocked`):

- Domeinen toevoegen: `POST /v1/web-filters/domains/<lijst>` met `{"domains": [...]}` — 1 tot 1000 per request, idempotent (opnieuw toevoegen doet niets), `422` bij ongeldige hostname (geen IP-adressen, TLD verplicht).
- Eén domein checken: `GET /v1/web-filters/domains/<lijst>/<domein>` — `404` als het er niet in staat.
- Eén domein verwijderen: `DELETE /v1/web-filters/domains/<lijst>/<domein>` — `204` (ook als het er niet in stond).
- Meerdere verwijderen: `POST /v1/web-filters/domains/<lijst>/batch-delete` met `{"domains": [...]}` — `204` (`POST` omdat er een body meegaat; sommige proxies droppen de body van een `DELETE`).

Matchregels:

- Je stuurt een kale hostname of een volledige URL; Mistral normaliseert naar een lowercase bare hostname (`https://Example.com/path` → `example.com`).
- Een entry matcht het domein zelf **en alle subdomeinen**: `knwu.nl` dekt dus `kenniscentrum.knwu.nl` en `www.knwu.nl`. `www.` als losse entry wordt wel bewaard, maar is overbodig als je het apex-domein al hebt.
- Staat een host op beide lijsten, dan wint de **meeste specifieke** entry. `block_by_default` geldt alleen als niets matcht.

## Waar filtering geldt

- `web_search` én `web_search_premium`-resultaten op de Conversations/Agents API (`/v1/conversations`, inclusief agent-handoffs).
- `open_url`: een geblokkeerd domein wordt geweigerd met `451 Unavailable For Legal Reasons`.
- Website-libraries (crawls): een crawl van een geblokkeerd domein wordt geweigerd.

Filtering is **stilzwijgend**: gefilterde resultaten worden vóór de agent verwijderd — niet geretourneerd, niet geciteerd, geen signaal in de response. Als alles wordt gedropt, retourneert de search niets; in een conversation zie je dan een lege `outputs: []` zonder foutmelding.

## Filtering uitzetten

Zet beide stappen, want entries matchen in beide modi:

1. `PUT /v1/web-filters/config` met `{"block_by_default": false}`
2. Lees beide lijsten en leeg ze met `batch-delete`.

## Controle dat het gelukt is

- De GET-calls tonen `block_by_default: true` en de drie domeinen in `allowed`.
- Stel via een agent met de `web_search`-tool een vraag waarvan je weet dat het open web ook resultaten geeft (bijvoorbeeld "Wanneer is WTC Woerden opgericht?"). In de `tool_reference`-chunks van de `message.output` mogen alleen `knwu.nl`, `knwumidden.nl` en `wtcwoerden.nl` (en subdomeinen) voorkomen.

## Let op: geen per-tool `include` gebruiken

Zet **geen** `tool_configuration: {"include": [...]}` op de `web_search`-tool in `agents.create()` of `conversations.start()`. In `mistralai` 3.6.0 wordt de tool-call dan wel geëmit maar nooit uitgevoerd: de response bevat `outputs: []` (wel `completion_tokens` voor de call-argumenten) en er verschijnt geen `tool.execution`-entry. Geverifieerd in deze workspace. Gebruik in plaats daarvan de org-level web-filters hierboven.

## Bronnen

- Admin-guide: https://docs.mistral.ai/admin/identity-access/web-search-domain-filtering
- Websearch-tool: https://docs.mistral.ai/agents/tools/built-in/websearch (sectie "Domain filtering")
- Beslissing: [ADR-0004](../adr/0004-websearch-beperkt-tot-kenniscentrum.md)
