---
status: accepted
---

# RAG over eigen documenten; KNWU Kenniscentrum is autoriteit voor versies

De chatbot antwoordt uit de eigen documenten — twee Libraries in Mistral Studio: de WTC/Regio-bibliotheek (club-/regiowedstrijden) en de KNWU-bibliotheek (Titel 20, Nationale Besluiten, Handboek Veldrijden) — met strikte bronvolgorde per vraagtype (regionaal eerst, nationaal alleen KNWU) en altijd bron + versiedatum in het antwoord. Het online KNWU Kenniscentrum (kenniscentrum.knwu.nl) is de autoritatieve bron voor de nieuwste versies, licentiepakketten/tarieven, verzekeringen en wijzigingsmemo's. De system prompt is geport uit de skills `wtc-knwu-kennisroutering` en `taalniveau` (repo WebsiteWTCjeugd).

_Amendment 2026-11-02 (wayfinder-ticket "Grilling: MVP system prompt / routeringsregels specificeren", map #2 issue #12): de WTC/Regio-bibliotheek is gesplitst in een Regio-library (MNC, Hans van den Hengel) en een Club-library (ZMC, clubreglementen, WTC-jeugddocumenten); de routering is drie-wegs (KNWU / regio / club) met één agent per library (plus archief-agent, ADR-0005); fallback naar KNWU alléén bij MNC/HvH-vragen; de system prompt is gespecificeerd in `docs/system-prompt.md`._

_Amendment 2026-11-09 (grilling bij issue #44): het Kenniscentrum blijft autoriteit voor **welke versie** van een reglement de nieuwste is, en voor licentiepakketten, tarieven en verzekeringen. Voor de **inhoud** van een regel is de reglementstekst leidend (Titel 20, Nationale Besluiten), ook boven de uitlegpagina's van het Kenniscentrum. Aanleiding: de licentiepagina's van het Kenniscentrum noemen U16 en U17 als aparte leeftijdscategorieën, Titel 20 (2026-09-21) noemt beide "U17 Nieuweling". Overwogen: het Kenniscentrum volgen (verworpen: uitlegpagina's zijn niet versiebeheerd en we kunnen ze niet jaarlijks reviewen) en beide noemen in de contextregel (verworpen: geen eenduidig antwoord). Bij een verschil antwoordt de bot volgens de reglementstekst, noemt hij het verschil kort en signaleert hij een bronconflict aan de beheerder (zie GLOSSARY.md)._

## Considered options

- **Fine-tuning in plaats van RAG** — verworpen: duur, traag en stilstaand; de regelgeving wisselt elk seizoen (nieuwe Nationale Besluiten, reglementen), en bij RAG is een nieuw document uploaden direct bijgewerkt.
- **Alleen websearch, geen eigen documenten** — verworpen: non-deterministisch, duur per vraag en de "verzin niets"-regel is niet afdwingbaar over het open web.
- **Alleen lokale documenten, zonder Kenniscentrum** — verworpen: licentiepakketten/tarieven, verzekeringsdekking en wijzigingsmemo's staan alléén online op het Kenniscentrum.

## Consequences

- De twee bibliotheken moeten actueel gehouden worden (zie ADR-0005); de bronvolgorde en "verzin niets" leven in de system prompt en zijn via de eval-set te bewaken.
- Zichtbare revisies in de PDF's vereisen de gelaagde aanpak (ADR-0005): opschonen bij ingestie waar mogelijk, harde prompt-regel, onzekerheid signaleren, cron-versiecheck.
- Retrieval is altijd per bibliotheek gescoped — ongescopeerd zoeken over beide libraries is een foutbron.
