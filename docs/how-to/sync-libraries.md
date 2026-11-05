# Libraries synchroniseren met knowledge-documents

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je de lokale bronmap `knowledge-documents/` synchroniseert met de Mistral-libraries. Elke submap is één library; de submapnaam is gelijk aan de librarynaam (lowercase). Zie [GLOSSARY.md](../../GLOSSARY.md) (termen "Knowledge-documents" en "Sync") en [ADR-0005](../adr/0005-library-bevat-alleen-actuele-versies.md).

## Voorwaarden

- Draai met de project-venv: activeer `.venv` of gebruik `.venv/Scripts/python`. Zonder venv zijn `mistralai`/`dotenv` niet beschikbaar (het script geeft dan een hint).
- Maakt niet uit vanuit welke map je draait: het pad naar `knowledge-documents/` wordt relatief aan het configbestand omgezet.
- `MISTRAL_API_KEY` staat in `.env` in de repo-root (wordt automatisch gevonden).
- Libraries staan in `scripts/libraries_config.json`; een nieuwe submap in `knowledge-documents/` hoort daar ook in.

## Synchronisatie draaien

1. Draai een dry-run (default, read-only): `python scripts/sync_libraries.py`
2. Controleer de output: welke libraries worden aangemaakt, welke documenten worden geüpload of verwijderd.
3. Voer uit: `python scripts/sync_libraries.py --apply`
4. Eén library만: `python scripts/sync_libraries.py --library knwu`

## Document vervangen (seizoenwissel)

Zie ook de [seizoenwissel-procedure](../operations.md):

1. Zet de oude versie in `knowledge-documents/archive/` met de datum in de bestandsnaam (bijv. `Nationale_Besluiten_20260918_2026-09-18.pdf`).
2. Plaats de nieuwe versie in `knowledge-documents/<library>/`. Een KNWU-PDF met doorhalingen of rode revisies gaat er als opgeschoonde versie in: `python scripts/clean_pdf.py knowledge-documents/knwu/<document>.pdf --out knowledge-documents/knwu` (zie [operations.md](../operations.md)).
3. Loop het opschoonrapport na: `knowledge-documents/review/<document>.md`. Vink elk twijfelgeval bovenaan af nadat je het in de PDF hebt gecontroleerd; de lijst met weggehaalde stukken eronder hoef je alleen te raadplegen. Commit het afgevinkte rapport samen met de opgeschoonde versie.
4. Werk `knowledge-documents/versions.json` handmatig bij (documentnaam → versiedatum).
5. Draai de sync (eerst dry-run, dan `--apply`). De map `review/` wordt nooit gesynct.
6. Re-run de eval-set (`eval/run_eval.py`); launch-gate ≥90% correct mét correcte bron.

## Controle dat het gelukt is

- De summary onderaan de script-output toont per categorie de aantallen; bij fouten tijdens `--apply` is de exit-code 1 en staan de fouten in de summary.
- Bekijk de remote inhoud los van de sync: `python scripts/list_libraries.py` (tabel) of `--json` — zie [reference](../reference/libraries-sync.md).
- In Mistral Studio kun je per library het documentenaantal vergelijken met de lokale submap.
