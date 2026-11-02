---
status: accepted
---

# Library bevat alleen de meest recente documentversies; oude versies in een aparte archief-library; wijzigingen via Kenniscentrum-memo

Antwoorden over de geldende regels komen alleen uit de actuele documenten in de KNWU- en WTC/Regio-library. Daarnaast is er een aparte archief-library met oude versies, die de router ALLEEN raadpleegt bij "wat is er veranderd?"-vragen — zo kan retrieval nooit per ongeluk een superseded regel citeren uit de actuele library's. Oude versies staan óók in het repo-archief (`knowledge-documents/archive/`, met datum in de bestandsnaam).

"Wat is er veranderd?" heeft een vaste bronvolgorde: (1) de officiële wijzigingsmemo's op het Kenniscentrum per documentversie, (2) de rode zichtbare revisies in het actuele document zelf, (3) als laatste fallback een vergelijking van oude vs nieuwe versie uit de archief-library / het repo-archief. Géén geautomatiseerde lokale PDF-diff (onbetrouwbaar door rode revisies en OCR-ruis) en géén handmatige changelog. Als post-MVP optimalisatie kan bij ingestie de gällende tekst + diffs geëxtraheerd worden naar TXT.

Versiecheck: in de MVP handmatig — bij elke Library-update wordt het document vervangen, de oude versie gearchiveerd, `versions.json` bijgewerkt en de eval-set opnieuw gedraaid (launch-gate ≥90% correct mét correcte bron); verouderde documenten signaleert de chatbot in-chat. De wekelijkse cron-job op de VPS die `versions.json` vergelijkt met het Kenniscentrum en mismatches via ntfy meldt aan de beheerder, is post-MVP.

_Amendment 2026-11-02 (wayfinder-ticket "Beslissing: ADR-0005 herzien — alleen actuele versies, strikethrough, cron", map #2): archief-library toegevoegd voor wijzigingsvragen; bronvolgorde voor wijzigingsvragen vastgelegd; cron-versiecheck verschoven naar post-MVP._

## Considered options

- **Oude versies in de actuele Library voor diffing** — verworpen: retrieval kan dan een superseded regel citeren en het strikethrough-probleem wordt erdoor vermenigvuldigd. Oude versies horen in een aparte archief-library (alleen voor wijzigingsvragen) en in het repo-archief.
- **Lokale PDF's diffen voor "wat is er veranderd"** — verworpen: de PDF's bevatten zichtbare revisies en OCR-ruis, waardoor een automatische diff onbetrouwbaar is.
- **Handmatig bijgehouden changelog** — verworpen: extra proces dat afwijkt van de bron; de Kenniscentrum-memo is al de officiële changelog waar beschikbaar.
- **Cron-versiecheck al in de MVP** — verworpen: extra VPS-werk; in de MVP volstaat de handmatige check bij elke Library-update plus in-chat signalering.

## Consequences

- Seizoenwissel is een kritieke operatie: Library vervangen, oude versie naar archief-library + repo-archief, `versions.json` bijwerken, eval-set her-run, LEARNINGS.md noteren — met een benoemde beheerder + vervanger (zie docs/operations.md).
- Strikethrough-afhandeling is gelaagd: opschonen bij ingestie waar het PDF-formaat het toelaat, harde prompt-regel "doorgestreepte tekst is nooit de huidige regel", expliciete onzekerheidsmelding bij twijfel over de status van een passage, en de versiecheck als vangnet (handmatig in de MVP, cron post-MVP).
- De archief-library is een derde Mistral Library; per-library scoping (ADR-0003) maakt de routering ondubbelzinnig: actuele vragen nooit naar de archief-library, wijzigingsvragen altijd via memo + rode revisies + archief.
- Na elke Library-update wordt de eval-set opnieuw gedraaid; launch-gate is ≥90% correct mét correcte bron.
