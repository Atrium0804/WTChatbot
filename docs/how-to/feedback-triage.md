# Feedback raadplegen voor triage

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Haal de feedback die gebruikers in de chat gaven (duim omhoog/omlaag, bij omlaag met toelichting) op van de NAS en toon een rapport op scherm: eerst counters, daarna de triage-lijst. Er wordt niets in de repo opgeslagen.

## Voorwaarden

- SSH-toegang tot de NAS met een sleutel (werkt zonder wachtwoord); evt. een alias in `~/.ssh/config` voor host/poort.
- `sqlite3` op de NAS (aanwezig op `nas.fritz.box`) — voor een consistente server-side snapshot.
- De repo-venv is geactiveerd (`.venv\Scripts\activate`), gedraaid vanuit de repo-root.

## Stappen

1. Draai vanuit de repo-root:

   ```
   .venv\Scripts\python scripts/feedback_report.py --fetch --nas-host <ssh-target>
   ```

   Het script haalt via **ssh** (niet scp — de sftp-service van de Synology ziet `/volume1` niet) een snapshot op: de NAS maakt met `sqlite3` een `.backup`-kopie (`.feedback-snapshot.db` naast de DB), het script streamt die naar een lokaal tempfile, checkt de integriteit (`PRAGMA quick_check` — bij een corrupte kopie stopt het met een foutmelding), print het rapport en verwijdert daarna zowel de remote snapshot (in dezelfde ssh-call) als het lokale tempfile.
2. Voor een lokale DB (development) gebruik je `--db` in plaats van `--fetch`:

   ```
   .venv\Scripts\python scripts/feedback_report.py --db app\data\wtchat.db
   ```
3. Lees het rapport: eerst **counters** (aantal per rating, plus per week), daarna **triage** — de negatieve feedback, oudste eerst, met timestamp, conversation-ID, de **feedbackgeschiedenis** (de laatste turns van de conversatie, oudste eerst, de laatste gemarkeerd), de laatste vraag/antwoord en de toelichting.
4. Bepaal aan de hand van het rapport of er tickets aangemaakt moeten worden. Maak tickets aan met alleen **geanonimiseerde patronen** — nooit ruwe vraag/antwoord/toelichting (deze repo is publiek).
5. Leg terugkerende problemen en toegepaste fixes geanonimiseerd vast in [LEARNINGS.md](../../LEARNINGS.md).

## Output bewaren?

Standaard wordt niets opgeslagen. Wil je de output toch bewaren (bijvoorbeeld om samen te vatten), pipe dan zelf naar een file **buiten de repo** en verwijder die na de triage, consistent met de retentie van 30 dagen:

```
.venv\Scripts\python scripts/feedback_report.py --fetch --nas-host <ssh-target> | tee C:\temp\feedback-rapport.md
```

## Privacy-afspraken

- In de DB staat bij duim-omlaag de feedbackgeschiedenis (JSON in de `history`-kolom: de laatste 10 turns vraag/antwoord, met de laatste turn ook los in `question`/`answer`) plus de toelichting (maximaal 30 dagen, daarna automatische purge); bij duim-omhoog alleen een teller. Er worden geen IP-adressen opgeslagen. Zie [project_description.md](../project_description.md) (Privacy en retentie), ADR-0008 en de privacy-notitie in de chat-UI.
- Deze repo is publiek: ruwe feedback komt nooit in git, issues of PR's.
- Permanente vastlegging gebeurt alleen geanonimiseerd in `LEARNINGS.md`.
- `/admin/feedback` (beheerder-only, basic auth) is de geplande permanente triage-oplossing; dit CLI-script is de tussenoplossing (issue #42).

## Controle

- `python -m pytest tests/test_feedback_report.py -q` — tests voor counters, week-buckets, sortering (oudste eerst), integriteitscheck, scp-foutafhandeling en het opruimen van het temp-bestand.
