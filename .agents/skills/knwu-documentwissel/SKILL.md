---
name: knwu-documentwissel
description: 'Verwerk een nieuwe versie van een KNWU-document (Titel 20, Nationale Besluiten, Handboek Veldrijden) in de hele repo: bibliotheek, categorie-lookup, prompts, eval-set en GLOSSARY. Gebruik bij een seizoenwissel, een nieuwe Titel 20 of een versiecheck-melding.'
---

# KNWU-documentwissel

Een nieuwe KNWU-versie raakt meer dan de bibliotheek: de app, de eval-set en de GLOSSARY bevatten waarden uit de reglementen. Titel 20 is leidend voor de inhoud van een regel ([ADR-0003](../../../docs/adr/0003-rag-over-eigen-documenten-kenniscentrum-autoriteit.md), amendment 2026-11-09). Werk de stappen in volgorde af; elke stap eindigt op zijn criterium.

## 1. Document vervangen

Volg [sync-libraries.md](../../../docs/how-to/sync-libraries.md), sectie "Document vervangen (seizoenwissel)", stappen 1–4 (archiveren, opgeschoonde versie, opschoonrapport, `versions.json`).

**Klaar als:** de oude versie staat in `knowledge-documents/archive/`, de nieuwe in `knowledge-documents/knwu/`, elk twijfelgeval in het opschoonrapport is afgevinkt en `versions.json` noemt de nieuwe versiedatum.

## 2. Regelwijzigingen inventariseren

Lees in de nieuwe versie de `[GEWIJZIGD]`-passages van de artikelen die de regels definiëren, en vergelijk ze met de gearchiveerde versie:

| Document | Artikel | Regel |
| --- | --- | --- |
| Titel 20 | 20.0.002 | Licenties (naam, leeftijdsgrenzen) |
| Titel 20 | 20.0.004 | Leeftijdscategorieën + veldritseizoen-zin |
| Titel 20 | 20.0.005 | Dispensatie |
| Titel 20 | 20.1.007 | Maximaal verzet per leeftijdscategorie |
| Nationale Besluiten | — | Licentie- en NK-bepalingen die de eval-set noemt |

Zijn artikelnummers verschoven, zoek dan op de kop ("Categorie-indeling", "Categorieën Jeugdlicenties").

**Klaar als:** je per artikel een regel hebt: de oude en nieuwe waarde, of "ongewijzigd". Een artikel zonder regel in die lijst is niet gecontroleerd.

## 3. Categorie-lookup bijwerken

Werk `app/knwu_categories.json` bij: `bron` (nieuwe bestandsnaam), `versie`, `leeftijdscategorieen` en `licenties`.

**Klaar als:** `python -m pytest tests/test_knwu_categories.py -q` groen is.

## 4. Kopieën van oude waarden opruimen

Zoek elke oude waarde uit stap 2 en de oude bestandsnaam van het document (bv. `TITEL_20-Jeugdwielrennen_20260921`) in `GLOSSARY.md`, `scripts/prompts/`, `docs/` en `eval/evalset.yaml`. Per vindplaats:

- **Prompts** (`scripts/prompts/`, gespiegeld in `docs/system-prompt.md`): alleen artikelnummers, geen waarden. Staat er een waarde, vervang die door een artikelverwijzing.
- **Eval-set**: `verwacht_antwoord`, `bron`, `versiedatum` en `doorhaal_waarde` krijgen de nieuwe waarden; de oude waarde is vaak de nieuwe `doorhaal_waarde`. Zie [eval-set.md](../../../docs/reference/eval-set.md).
- **GLOSSARY.md**: werk termen als licentie, leeftijdscategorie en veldritseizoen bij met de skill `domain-modeling`.

**Klaar als:** de zoekactie op elke oude waarde en de oude bestandsnaam alleen nog treffers geeft in `knowledge-documents/archive/`, `knowledge-documents/review/` en git-historie.

## 5. Kenniscentrum vergelijken

Lees de licentiepagina's op kenniscentrum.knwu.nl (`/knwu-licenties/jeugd-u13`, `/knwu-licenties/knwu-wedstrijdlicentie-u17`, `/knwu-licenties/knwu-wedstrijdlicentie`) en vergelijk namen, leeftijdsgrenzen en licentiepakketten met stap 2.

**Klaar als:** elk verschil als bronconflict genoteerd staat in de PR-beschrijving, met de waarde uit Titel 20 als de waarde die de repo gebruikt.

## 6. Valideren en uitrollen

1. `python -m pytest -q`
2. Prompts gewijzigd? `python scripts/create_agents.py`, controleer, dan `--apply` ([create-agents.md](../../../docs/how-to/create-agents.md)).
3. Sync-libraries stappen 5–7: `app/knwu_categories.json` is al gedaan, dan de sync en de eval-set.

**Klaar als:** de eval-gate gehaald is (`eval/last_run.json`, `gate_gehaald: true`) en de wijzigingen in één PR staan, met de lijst uit stap 2 en de bronconflicten uit stap 5 in de beschrijving.
