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
3. Loop het [opschoonrapport](../../GLOSSARY.md) na: `knowledge-documents/review/<document>.md`. Vink elk twijfelgeval bovenaan af nadat je het in de PDF hebt gecontroleerd; de lijst met weggehaalde stukken eronder hoef je alleen te raadplegen. Commit het afgevinkte rapport samen met de opgeschoonde versie. Let op: opnieuw `clean_pdf.py` draaien overschrijft het rapport en dus je vinkjes; controleer met `git diff` voordat je commit.
4. Werk `knowledge-documents/versions.json` handmatig bij (documentnaam → versiedatum).
5. Nieuwe Titel 20? Gebruik dan de skill `knwu-documentwissel`. Die werkt onder meer `app/knwu_categories.json` bij (bron, versie, leeftijdscategorieën en licenties uit artikel 20.0.004 en 20.0.002); de app berekent daarmee de categorie per geboortejaar. `python -m pytest tests/test_knwu_categories.py -q` faalt zolang het bestand niet overeenkomt met de Titel 20 in `knowledge-documents/knwu/`.
6. Draai de sync (eerst dry-run, dan `--apply`). De map `review/` wordt nooit gesynct.
7. Re-run de eval-set (`eval/run_eval.py`); launch-gate ≥90% correct mét correcte bron.

## Website-teksten importeren in de Club-library

De pagina's van de jeugdsite (Website-teksten, zie [GLOSSARY.md](../../GLOSSARY.md)) staan als markdown in de WebsiteWTCjeugd-repo. `scripts/import_website_texts.py` kopieert ze naar `knowledge-documents/club/` en haalt het CMS-paginanummer uit de bestandsnaam (`Trainingen - 1014.md` wordt `Trainingen.md`). De website geldt als actueel: een gewijzigde tekst overschrijft de kopie. Een bestand dat al gelijk is, wordt niet opnieuw geschreven.

1. Haal de laatste versie van de WebsiteWTCjeugd-repo op (`git pull` in die clone).
2. Draai een dry-run: `python scripts/import_website_texts.py`. De default bronmap is de naastgelegen clone `..\WebsiteWTCjeugd\websiteteksten\website_teksten md`; geef een ander pad mee met `--source "<pad>"` (bijvoorbeeld vanuit een git-worktree).
3. Controleer de output: welke teksten nieuw of gewijzigd zijn.
4. Schrijf de bestanden: `python scripts/import_website_texts.py --apply`.
5. Commit de gewijzigde Website-teksten. Ze staan in git; de overige clubdocumenten (`WTC Woerden - ...`) blijven lokaal.
6. Sync de Club-library: `python scripts/sync_libraries.py --library club` (eerst dry-run, dan `--apply`).

Het script verwijdert niets: is een pagina van de website verdwenen, verwijder de kopie dan zelf uit `knowledge-documents/club/`.

## Controle dat het gelukt is

- De summary onderaan de script-output toont per categorie de aantallen; bij fouten tijdens `--apply` is de exit-code 1 en staan de fouten in de summary.
- Bekijk de remote inhoud los van de sync: `python scripts/list_libraries.py` (tabel) of `--json` — zie [reference](../reference/libraries-sync.md).
- In Mistral Studio kun je per library het documentenaantal vergelijken met de lokale submap.
