---
status: accepted
---

# Websearch-tool aan, scope = allowlist van de gezaghebbende domeinen (KNWU, regio, club)

De agent mag het live web raadplegen via de websearch-tool, maar alleen via een org-level allowlist van precies drie domeinen: `knwu.nl` (inclusief kenniscentrum.knwu.nl), `knwumidden.nl` en `wtcwoerden.nl` — nooit het open web (subdomeinen matchen automatisch). Websearch is een fallback: pas als de bibliotheken geen sluitend antwoord geven. Licentievragen raadplegen sowieso altijd óók het Kenniscentrum; verzekeringsvragen primair via de sectie Verzekeringen van het Kenniscentrum.

_Amendment 2026-11-02 (wayfinder-ticket "Beslissing: ADR-0004 herzien — websearch-scope", map #2): scope verruimd van KNWU-only naar de drie gezaghebbende domeinen, consistent met de bronvolgorde KNWU > regio > club (GLOSSARY)._

## Considered options

- **Websearch uit** — verworpen: de bot zou licentie-, verzekerings- en actuele-versievragen niet kunnen beantwoorden uit alleen de documenten; de versiecontrole loopt al via de cron-job, maar de content zelf ontbreekt lokaal.
- **Open web (ongescopet)** — verworpen: breekt de "eigen documenten + gezaghebbende bronnen"-belofte, drijft de kosten per vraag op (elke websearch kost extra), en maakt de eval-set non-deterministisch omdat antwoorden van het live web kunnen afwijken.
- **Strikt KNWU-only (oorspronkelijke versie van deze ADR)** — verworpen bij herziening: live regio- en clubinformatie (bijvoorbeeld knwumidden.nl/competities) is via websearch dan onbereikbaar, terwijl die bronnen al gezaghebbend zijn in de bronvolgorde.
- **Allowlist KNWU + regio + club (gekozen)** — server-side afdwingbaar via de org-web-filter, volgt dezelfde trust-laag als de bronvolgorde en houdt het open web buiten de deur.

## Consequences

- Afdwinging in drie lagen: (1) org-level web-filter allowlist via `/v1/web-filters` (server-side; filtering geldt voor `web_search`-resultaten én `open_url`, geblokkeerd domein geeft 451), (2) system prompt als tweede laag, (3) eval-set met web-geanimeerde vragen (licenties, verzekeringen) met Verwachte bron. Als de web-filter bij implementatie niet beschikbaar blijkt: prompt-only, géén open web.
- Meer kosten per vraag waar websearch wordt getriggerd — tool-API's worden per call gefactureerd; afgedekt door het spend-limiet en rate limiting (ADR-0002).
- De eval-set moet ook web-geanimeerde vragen bevatten (licenties, verzekeringen) met expected bron = Kenniscentrum.
- De allowlist wordt geconfigureerd via de Mistral API (`/v1/web-filters`, API-only, nog geen Admin Panel-pagina) en gedocumenteerd in `docs/operations.md`.
- `web_search` werkt alleen met de Conversations/Agents API, niet met de Chat Completions API — relevant voor de dunne FastAPI-proxy (ADR-0002).
