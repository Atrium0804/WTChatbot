---
status: accepted
---

# Library bevat alleen de meest recente documentversies; wijzigingen via Kenniscentrum-memo

Antwoorden komen alleen uit de actuele documenten. Oude versies staan nooit in de Library — wel in het repo-archief (`knowledge-documents/archive/`, met datum in de bestandsnaam). "Wat is er veranderd?" wordt beantwoord uit de officiële wijzigingsmemo's op het Kenniscentrum, niet door lokale PDF's te diffen. Een wekelijkse cron-job op de VPS vergelijkt de versiedata in `versions.json` met de Kenniscentrum-regelgevingpagina en meldt mismatches via ntfy aan de beheerder; desgewenst aanvullend in-chat detectie via een `report_outdated_document`-tool. Na elke Library-update wordt de eval-set opnieuw gedraaid; launch-gate is ≥90% correct mét correcte bron.

## Considered options

- **Oude versies in de Library houden voor diffing** — verworpen: retrieval kan dan een supersede regel citeren; het strikethrough-probleem (zichtbare revisies) wordt erdoor vermenigvuldigd. Als de gebruiker expliciet vraagt wat er veranderd is, moet dat uit de autoriteit (Kenniscentrum-memo), niet uit een lokale diff.
- **Lokale PDF's diffen voor "wat is er veranderd"** — verworpen: de PDF's bevatten zichtbare revisies en OCR-ruis, waardoor een automatische diff onbetrouwbaar is.
- **Handmatig bijgehouden changelog** — verworpen: extra proces dat afwijkt van de bron; de Kenniscentrum-memo is al de officiële changelog.

## Consequences

- Seizoenwissel is een kritieke operatie: Library vervangen, oude versie archiveren, `versions.json` bijwerken, eval-set her-run, LEARNINGS.md noteren — met een benoemde beheerder + vervanger (zie leerplan).
- De cron-check dekt ook periodes zonder bezoekersvragen (passieve melding), de tool-laag dekt het moment zelf.
- Strikethrough-afhandeling is gelaagd: opschonen bij ingestie waar het PDF-formaat het toelaat, harde prompt-regel "doorgestreepte tekst is nooit de huidige regel", expliciete onzekerheidsmelding bij twijfel over de status van een passage, en de cron-versiecheck als vangnet.
