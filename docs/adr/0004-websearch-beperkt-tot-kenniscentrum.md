---
status: accepted
---

# Websearch-tool aan, maar scope beperkt tot het KNWU Kenniscentrum

De agent mag het live web raadplegen via de websearch-tool, maar alleen kenniscentrum.knwu.nl (en KNWU-eigen pagina's). Sommige informatie is alleen daar te vinden: licentiepakketten en tarieven (Basis/Plus/Premium), verzekeringsdekking, en de officiële wijzigingsmemo's per reglementsversie. Licentievragen raadplegen sowieso altijd óók het Kenniscentrum, ook als de KNWU-bibliotheek al antwoord lijkt te geven.

## Considered options

- **Websearch uit** — verworpen: de bot zou licentie-, verzekerings- en actuele-versievragen niet kunnen beantwoorden uit alleen de documenten; de versiecontrole loopt al via de cron-job, maar de content zelf ontbreekt lokaal.
- **Open web (ongescopet)** — verworpen: breekt de "eigen documenten + Kenniscentrum"-belofte, drijft de kosten per vraag op (elke websearch kost extra), en maakt de eval-set non-deterministisch omdat antwoorden van de live webestand kunnen afwijken.

## Consequences

- Meer kosten per vraag waar websearch wordt getriggerd — afgedekt door het spend-limiet en rate limiting (ADR-0002).
- De eval-set moet ook web-geanimeerde vragen bevatten (licenties, verzekeringen) met expected bron = Kenniscentrum.
- **Te valideren bij implementatie:** of de websearch-tool op agentniveau domain-restrictie ondersteunt. Zo niet, afdwingbaar via system prompt + verificatie in de eval-set — geen open web.
