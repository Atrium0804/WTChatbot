---
status: accepted
---

# RAG over eigen documenten; KNWU Kenniscentrum is autoriteit voor versies

De chatbot antwoordt uit de eigen documenten — twee Libraries in Mistral Studio: de WTC/Regio-bibliotheek (club-/regiowedstrijden) en de KNWU-bibliotheek (Titel 20, Nationale Besluiten, Handboek Veldrijden) — met strikte bronvolgorde per vraagtype (regionaal eerst, nationaal alleen KNWU) en altijd bron + versiedatum in het antwoord. Het online KNWU Kenniscentrum (kenniscentrum.knwu.nl) is de autoritatieve bron voor de nieuwste versies, licentiepakketten/tarieven, verzekeringen en wijzigingsmemo's. De system prompt is geport uit de skills `wtc-knwu-kennisroutering` en `taalniveau` (repo WebsiteWTCjeugd).

## Considered options

- **Fine-tuning in plaats van RAG** — verworpen: duur, traag en stilstaand; de regelgeving wisselt elk seizoen (nieuwe Nationale Besluiten, reglementen), en bij RAG is een nieuw document uploaden direct bijgewerkt.
- **Alleen websearch, geen eigen documenten** — verworpen: non-deterministisch, duur per vraag en de "verzin niets"-regel is niet afdwingbaar over het open web.
- **Alleen lokale documenten, zonder Kenniscentrum** — verworpen: licentiepakketten/tarieven, verzekeringsdekking en wijzigingsmemo's staan alléén online op het Kenniscentrum.

## Consequences

- De twee bibliotheken moeten actueel gehouden worden (zie ADR-0005); de bronvolgorde en "verzin niets" leven in de system prompt en zijn via de eval-set te bewaken.
- Zichtbare revisies in de PDF's vereisen de gelaagde aanpak (ADR-0005): opschonen bij ingestie waar mogelijk, harde prompt-regel, onzekerheid signaleren, cron-versiecheck.
- Retrieval is altijd per bibliotheek gescoped — ongescopeerd zoeken over beide libraries is een foutbron.
