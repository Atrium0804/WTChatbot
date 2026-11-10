# Contributing

Dit bestand beschrijft **wat** je doet bij een bijdrage. **Hoe** je code schrijft staat in [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md).

## Werkwijze

1. **Issue eerst.** Werk vanuit een GitHub Issue (`gh issue list`). Labels en triage: [docs/agents/triage-labels.md](docs/agents/triage-labels.md).
2. **Branch per issue**, kleine en gerichte commits.
3. **Code volgens [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md).**
4. **Tests toevoegen of bijwerken** en lokaal draaien met de project-venv: `.venv\Scripts\python -m pytest app/tests` vanuit de repo-root. De venv maak je eenmalig aan met `python -m venv .venv` en `.\.venv\Scripts\pip install -r app\requirements-dev.txt` (zonder venv mist de standaard-`python` `fastapi` en `pytest`).
5. **Dependencies** toevoegen in `pyproject.toml` met een versiegrens.
6. **Secrets** alleen in `.env`; nieuwe variabelen ook (leeg) in `.env.example`.
7. **Documentatie bijwerken** waar relevant (zie hieronder).
8. **Pull request** met een verwijzing naar het issue (`Closes #<nr>`).

## Documentatie

- **Ontwikkelaarsdocumentatie** → Diátaxis-map in `docs/` volgens [docs/DOCUMENTATION_GUIDE.md](docs/DOCUMENTATION_GUIDE.md).
- **Architectuurbesluiten** → nieuwe ADR in [docs/adr/](docs/adr/) volgens [TEMPLATE.md](docs/adr/TEMPLATE.md), oplopend genummerd.
- **Nieuwe of gewijzigde domeintermen** → [GLOSSARY.md](GLOSSARY.md).
- **Domeinkennis voor de chatbot** → [docs/knowledge/](docs/knowledge/).
- **Brondocumenten voor de bibliotheken** → `knowledge-documents/`, alleen actuele versies ([ADR-0005](docs/adr/0005-library-bevat-alleen-actuele-versies.md)).

## Checklist vóór merge

- [ ] `.venv\Scripts\python -m pytest app/tests` slaagt (vanuit repo-root)
- [ ] Geen secrets of persoonsgegevens in de diff
- [ ] Nieuwe tools hebben type hints en tests
- [ ] ADR/GLOSSARY bijgewerkt bij een besluit of nieuwe term
