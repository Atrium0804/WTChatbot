# Contributing

Dit bestand beschrijft **wat** je doet bij een bijdrage. **Hoe** je code schrijft staat in [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md).

## Werkwijze

1. **Issue eerst.** Werk vanuit een GitHub Issue (`gh issue list`). Labels en triage: [docs/agents/triage-labels.md](docs/agents/triage-labels.md).
2. **Branch per issue**, kleine en gerichte commits.
3. **Code volgens [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md).**
4. **Tests toevoegen of bijwerken** en lokaal draaien met de project-venv; zie [Tests draaien](#tests-draaien).
5. **Dependencies** toevoegen in `requirements.txt` (scripts), `app/requirements.txt` (app) of `app/requirements-dev.txt` (tests en tooling), met een versiegrens.
6. **Secrets** alleen in `.env`; nieuwe variabelen ook (leeg) in `.env.example`.
7. **Documentatie bijwerken** waar relevant (zie hieronder).
8. **Pull request** met een verwijzing naar het issue (`Closes #<nr>`).

## Werkwijze per agentsessie

Elke agentsessie werkt op een **featurebranch**. Nooit werken of committen op `main`. Staat de checkout op `main`, maak dan eerst een branch aan:

```powershell
git switch -c issue-<nr>-<korte-naam> main
```

- De agent maakt zelf geen worktrees aan. Wil je sessies parallel laten draaien, start de agent dan zelf vanuit een eigen worktree (`git worktree add ..\WTChatbot-<issue> -b issue-<nr>-<korte-naam> main`); die deelt de `.git`-config, maar niet `.venv` of `.env`.
- Eenmalig per clone: `git config core.hooksPath .githooks`. De hook `.githooks/pre-commit` weigert dan commits op `main`. Dit dekt alleen lokaal werk; `main` is op GitHub al beschermd.

## Flowkeuze per issue

Er is geen vaste drempel; de keuze volgt per issue uit een afweging:

- **grill → implement**: het werk past in één sessie en één context, en is te overzien (bijv. #99).
- **to-spec → to-tickets → implement per ticket**: het werk raakt meerdere lagen (data, renderer, eval, docs), wijzigt een datamodel, introduceert een nieuwe seam, of dreigt de context te vullen (bijv. #102: 23 bestanden, late reviewgaten).

Bij twijfel kies je de zwaardere flow. Een agent die aan een issue begint, **adviseert de gebruiker voordat hij bouwt**: welke flow (grill → implement of to-spec → to-tickets) en welk modelformaat (klein voor afgebakend, mechanisch werk; groot voor ontwerp, datamodel of werk over meerdere lagen), met een korte reden. De gebruiker beslist.

## Documentatie

- **Ontwikkelaarsdocumentatie** → Diátaxis-map in `docs/` volgens [docs/DOCUMENTATION_GUIDE.md](docs/DOCUMENTATION_GUIDE.md).
- **Architectuurbesluiten** → nieuwe ADR in [docs/adr/](docs/adr/) volgens [TEMPLATE.md](docs/adr/TEMPLATE.md), oplopend genummerd.
- **Nieuwe of gewijzigde domeintermen** → [GLOSSARY.md](GLOSSARY.md).
- **Domeinkennis voor de chatbot** → [docs/knowledge/](docs/knowledge/).
- **Brondocumenten voor de bibliotheken** → `knowledge-documents/`, alleen actuele versies ([ADR-0005](docs/adr/0005-library-bevat-alleen-actuele-versies.md)).

## Tests draaien

Alle commando's draai je vanuit de repo-root met de project-venv. De venv maak je eenmalig aan:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r app\requirements-dev.txt
.\.venv\Scripts\python -m playwright install chromium webkit   # alleen voor de browsertests
```

| Doel | Commando | Duur (lokaal) |
| --- | --- | --- |
| Snel | `.venv\Scripts\python -m pytest app/tests tests -m "not browser and not pdf"` | ± 40 s |
| Alleen browsertests (Playwright) | `.venv\Scripts\python -m pytest app/tests -m browser` | ± 20 s |
| Alleen echte-PDF-tests | `.venv\Scripts\python -m pytest tests -m pdf` | ± 3 min |
| Volledig | `.venv\Scripts\python -m pytest app/tests tests` | 3–5 min |
| DOM-tests (Node) | `node --test "app/tests/*.cjs"` | < 1 s |
| Typecheck (`app/` zonder tests, `eval/`) | `.venv\Scripts\pyright --pythonpath .venv\Scripts\python.exe` | ± 10 s |

De markers staan in `pytest.ini`:

- `browser`: Playwright-tests. Markeer een nieuwe module met `pytestmark = pytest.mark.browser`. Ze draaien standaard in Chromium; voor Safari-gedrag voeg je `--browser chromium --browser webkit` toe.
- `pdf`: tests die de echte KNWU-PDF's uit `knowledge-documents/` opschonen. Die PDF's staan niet in git, dus in CI slaan deze tests over.

CI (`.github/workflows/tests.yml`) draait bij elke push en pull request de jobs `pytest` (alles behalve `browser`), `browser`, `node` en `pyright`. Stel deze vier in als verplichte statuschecks in de branch protection van `main`.

## Checklist vóór merge

- [ ] De volledige testrun en `pyright` slagen lokaal, of de CI-jobs zijn groen
- [ ] Geen secrets of persoonsgegevens in de diff
- [ ] Nieuwe tools hebben type hints en tests
- [ ] Verandert de route van een bericht? Dan staat er een regel in het routecontract (`app/tests/fixtures/routecontract.yaml`)
- [ ] ADR/GLOSSARY bijgewerkt bij een besluit of nieuwe term
