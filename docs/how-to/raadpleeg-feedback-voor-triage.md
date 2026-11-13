# Feedback raadplegen voor triage

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Haal de feedback die gebruikers in de chat gaven (duim omhoog/omlaag, bij omlaag met toelichting) op van de NAS en toon een rapport op scherm: eerst counters, daarna de triage-lijst. Er wordt niets in de repo opgeslagen.

## Voorwaarden

- SSH-toegang tot de NAS met een sleutel (werkt zonder wachtwoord); bij een afwijkende poort: `--nas-port <poort>` meegeven (anders evt. een alias in `~/.ssh/config`).
- `sqlite3` op de NAS (aanwezig op `nas.fritz.box`) — voor een consistente server-side snapshot.
- De repo-venv is geactiveerd (`.venv\Scripts\activate`), gedraaid vanuit de repo-root.

## Stappen

1. Draai vanuit de repo-root:

   ```
   .venv\Scripts\python scripts/feedback_report.py --fetch --nas-host <ssh-target> [--nas-port <poort>]
   ```

   Het script haalt via **ssh** (niet scp — de sftp-service van de Synology ziet `/volume1` niet) een snapshot op: de NAS maakt met `sqlite3` een `.backup`-kopie (`.feedback-snapshot.db` naast de DB), het script streamt die naar een lokaal tempfile, checkt de integriteit (`PRAGMA quick_check` — bij een corrupte kopie stopt het met een foutmelding), print het rapport en verwijdert daarna zowel de remote snapshot (in dezelfde ssh-call) als het lokale tempfile.
2. Voor een lokale DB (development) gebruik je `--db` in plaats van `--fetch`:

   ```
   .venv\Scripts\python scripts/feedback_report.py --db app\data\wtchat.db
   ```
3. Lees het rapport: eerst **counters** (aantal per rating, plus per week), daarna **triage** — de negatieve feedback, oudste eerst, met timestamp, conversation-ID, de **feedbackgeschiedenis** (de laatste turns van de conversatie, oudste eerst, de laatste gemarkeerd), de laatste vraag/antwoord en de toelichting. Daarna de sectie **Bronconflicten** (#47): identieke conflicten gegroepeerd op de `[BRONCONFLICT]`-marker, met aantal en laatste melding — deze rows tellen niet mee als negatieve feedback.
4. Wil je weten welke agent een fout antwoord gaf (bijvoorbeeld om een conversatie te vinden die na een handoff bij de verkeerde agent bleef, issue #44)? Draai het trace-commando dat het rapport achter de conversation-ID zet. Daarvoor is `MISTRAL_API_KEY` in `.env` nodig:

   ```
   .venv\Scripts\python scripts/trace_conversation.py <conversation-id>
   ```

   Per beurt zie je de vraag, de handoffs (`router-agent -> knwu-agent`), de gebruikte tools en de agent die antwoordde. Alleen conversaties die na #44 zijn gestart hebben een koppeling (`metadata.app_conversation_id`). Oudere conversaties vind je per dag (UTC) met `--date 2026-11-06`, of met `--mistral-id <id>` als je de Mistral-id al hebt. De output bevat vragen van gebruikers: bekijk hem alleen lokaal.
5. Bepaal aan de hand van het rapport of er tickets aangemaakt moeten worden. Maak tickets aan met alleen **geanonimiseerde patronen** — nooit ruwe vraag/antwoord/toelichting (deze repo is publiek).
6. Leg terugkerende problemen en toegepaste fixes geanonimiseerd vast in [LEARNINGS.md](../../LEARNINGS.md).

## Output bewaren?

Standaard wordt niets opgeslagen. Wil je de output toch bewaren (bijvoorbeeld om samen te vatten), pipe dan zelf naar een file **buiten de repo** en verwijder die na de triage, consistent met de retentie van 30 dagen:

```
.venv\Scripts\python scripts/feedback_report.py --fetch --nas-host <ssh-target> | tee C:\temp\feedback-rapport.md
```

## Privacy-afspraken

- In de DB staat bij duim-omlaag de feedbackgeschiedenis (JSON in de `history`-kolom: de laatste 10 turns vraag/antwoord, met de laatste turn ook los in `question`/`answer`) plus de toelichting (maximaal 30 dagen, daarna automatische purge); bij duim-omhoog alleen een teller. Er worden geen IP-adressen opgeslagen. Zie [project_description.md](../project_description.md) (Privacy en retentie), ADR-0008 en de privacy-notitie in de chat-UI.
- Bronconflicten (#47) staan als `bronconflict`-row in de DB: alléén de `[BRONCONFLICT]`-marker in `text` plus conversation-ID — géén vraag/antwoord/history (zelfde privacy-precedent als out-of-scope). De markerregel is door de proxy al uit het antwoord gestript vóórdat de gebruiker hem zag, ook uit de feedbackgeschiedenis.
- Deze repo is publiek: ruwe feedback komt nooit in git, issues of PR's.
- Permanente vastlegging gebeurt alleen geanonimiseerd in `LEARNINGS.md`.
- `/admin/feedback` (beheerder-only, basic auth) is de geplande permanente triage-oplossing; dit CLI-script is de tussenoplossing (issue #42).

## Controle

- `python -m pytest tests/test_feedback_report.py -q` — tests voor counters, week-buckets, sortering (oudste eerst), integriteitscheck, scp-foutafhandeling en het opruimen van het temp-bestand.
- `python -m pytest tests/test_trace_conversation.py -q` — tests voor het groeperen van de Mistral-geschiedenis per beurt en het zoeken op `app_conversation_id`.

## Zie ook

- [Gebruik feedback om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md) — van feedback naar een aantoonbare prompt-/config-wijziging met eval-gate als controle (issue #55)
