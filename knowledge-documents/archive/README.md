# Archief van oude documentversies

Bij vervanging van een document in een Mistral Studio Library wordt de oude
versie hier gearchiveerd (zie `docs/project_description.md`, "Documentbeheer
bij updates").

Regels:

- Bestandsnaam = originele naam + versiedatum achteraan in formaat `YYYY-MM-DD`,
  bijvoorbeeld `Nationale_Besluiten_20260918_2026-09-18.pdf`.
- Werk `knowledge-documents/versions.json` bij naar de nieuwe versiedatum.
- KNWU-reglementen met doorhalingen of rode revisies staan in de actuele
  library als opgeschoonde markdown (`scripts/clean_pdf.py`); het originele
  PDF staat hier, ook als het de actuele versie is (ADR-0005, amendment
  2026-11-05).
- PDF's en gegenereerde markdown in de librarymappen worden niet getrackt
  (zie `.gitignore`); deze README en `versions.json` wel.
