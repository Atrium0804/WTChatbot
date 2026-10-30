---
status: proposed | accepted | deprecated | superseded by ADR-NNNN
---

# {Korte titel van de beslissing}

{1-3 alinea's: wat is de context, wat is besloten, en waarom.}

## Considered options

- **{Alternatief}** — verworpen: {waarom}.
- **{Alternatief}** — verworpen: {waarom}.

## Consequences

- {Niet-voor-de-hand-liggend gevolg, incl. operationele afwegingen die een toekomstige lezer moet kennen.}

---

## Regels

Dit bestand (`docs/adr/TEMPLATE.md`) is de canonical template voor dit repo. De gekopieerde skill-versie staat ook in `.agents/skills/domain-modeling/ADR-FORMAT.md`, maar voor dit project geldt: wat in `docs/` staat is leidend.

- ADR's staan in `docs/adr/` met opeenvolgende nummering: `0001-slug.md`, `0002-slug.md`, …
- Een ADR legt **vast** dat er besloten is en **waarom** — geen uitgebreide secties nodig.
- `Considered options` alleen als de verworpen alternatieven het onthouden waard zijn (anders: weglaten).
- `Consequences` alleen als er niet-voor-de-hand-liggende downstream-effecten zijn.
- Maak een ADR alleen als álle drie true zijn: (1) moeilijk te herzien, (2) verrassend zonder context, (3) resultaat van een echte afweging.
