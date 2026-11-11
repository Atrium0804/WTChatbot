# Gebruik feedback om prompts te finetunen

Deze how-to beschrijft de hele loop van gebruikersfeedback naar een aantoonbare prompt- of configuratiewijziging: feedback ophalen van de NAS, de negatieve feedback analyseren, een patroon vertalen naar een failing case in de eval-set, de prompt of agent-configuratie aanpassen, de agents deployen en de wijziging toetsen met de eval-gate. Draai de loop na een feedback-triage (zie [raadpleeg-feedback-voor-triage](raadpleeg-feedback-voor-triage.md)) wanneer de counters een negatieve trend laten zien of er terugkerende klachten zijn (issue #55).

## Voorwaarden

- SSH-toegang tot de NAS met een sleutel (voor het ophalen van de feedback) — zie [raadpleeg-feedback-voor-triage](raadpleeg-feedback-voor-triage.md#voorwaarden).
- De repo-venv is geactiveerd (`.venv\Scripts\activate`); draai alles vanuit de repo-root.
- `.env` bevat `MISTRAL_API_KEY` en de agent-ids (`MISTRAL_AGENT_ID`, `MISTRAL_AGENT_ID_KNWU`, `MISTRAL_AGENT_ID_REGIO`, `MISTRAL_AGENT_ID_CLUB`).

## Stappen

1. **Haal het feedback-rapport op.** Counters (per rating, per week) plus de triage-lijst met negatieve feedback, oudste eerst:

   ```bash
   .venv\Scripts\python scripts/feedback_report.py --fetch --nas-host <ssh-target>
   ```

   Procedure, lokale DB en privacy-afspraken: [raadpleeg-feedback-voor-triage](raadpleeg-feedback-voor-triage.md).
2. **Analyseer de negatieve feedback op patronen.** Groepeer op oorzaak: verkeerde agent na handoff, ontbrekend kernfeit, foute bron, strikethrough-waarde die toch in het antwoord staat, overbodige verhelderingsvraag. Bepaal per conversatie welke agent antwoordde:

   ```bash
   .venv\Scripts\python scripts/trace_conversation.py <conversation-id>
   ```

   Alleen conversaties gestart na issue #44 hebben een koppeling; oudere vind je per dag (UTC) met `--date 2026-11-06`.
3. **Reproduceer het patroon in de eval-set.** Voeg de falende vraag toe aan `eval/evalset.yaml` (schema: [eval-set](../reference/eval-set.md)) met `verwacht_antwoord`, `bron` en bij strikethrough `doorhaal_waarde`, en draai de gate — deze run moet rood zijn:

   ```bash
   .venv\Scripts\python eval/run_eval.py
   ```

   De rode run is het bewijs dat het patroon echt bestaat.
4. **Wijzig de prompt of de agent-configuratie.** Pas het bestand aan in `scripts/prompts/` (`_shared.md` geldt voor alle content-agents, de per-agent bestanden voor agent-specifieke regels) of `scripts/agents_config.json` (model, `completion_args`, handoffs, libraries). Wijzig `docs/system-prompt.md` niet — dat is de spec; de werkende kopieën staan in `scripts/prompts/` (zie [maak-of-update-productie-agents](maak-of-update-productie-agents.md)).
5. **Deploy de agents.** Eerst dry-run (default), controleer welke agents worden aangemaakt vs. geüpdatet, voer dan uit:

   ```bash
   .venv\Scripts\python scripts/create_agents.py
   .venv\Scripts\python scripts/create_agents.py --apply
   ```

   Neem de agent-ids uit de summary over in `.env` (zie [maak-of-update-productie-agents](maak-of-update-productie-agents.md)).
6. **Toets de wijziging met de eval-gate.** Draai dezelfde gate opnieuw; deze run moet groen zijn (globaal ≥ 90% en per categorie ≥ 90% correct met correcte bron; `strikethrough` en `websearch` 100%):

   ```bash
   .venv\Scripts\python eval/run_eval.py
   ```

   De gate draait handmatig door de beheerder, nooit in CI. Het volledige resultaat staat in `eval/last_run.json`.
7. **Leg het patroon en de fix vast.** Noteer in [LEARNINGS.md](../../LEARNINGS.md), nieuwste entry bovenaan in het formaat `YYYY-MM-DD — probleem — oorzaak — fix`, geanonimiseerd: patronen zonder ruwe vraag/antwoord/toelichting.

## Privacy-afspraken

Zie [raadpleeg-feedback-voor-triage](raadpleeg-feedback-voor-triage.md#privacy-afspraken). Kort: deze repo is publiek, dus ruwe feedback komt nooit in git, issues of PR's; permanente vastlegging gebeurt alleen geanonimiseerd in `LEARNINGS.md`. Bewaar het feedback-rapport niet in de repo — pipe bij hoge uitzondering naar een bestand buiten de repo en verwijder het na gebruik (retentie 30 dagen).

## Controle

- De eval-gate is groen: `.venv\Scripts\python eval/run_eval.py` geeft exit-code 0 en `eval/last_run.json` toont de nieuwe run.
- `git status` toont geen bestanden met ruwe feedback.
- De geanonimiseerde entry staat bovenaan `LEARNINGS.md`.

## Zie ook

- [Feedback raadplegen voor triage](raadpleeg-feedback-voor-triage.md) — stap 1 en 2 in detail
- [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md) — stap 4 en 5 in detail
- [Eval-set](../reference/eval-set.md) — schema van `eval/evalset.yaml` en de gate-regels
- [LEARNINGS.md](../../LEARNINGS.md) — logboek van patronen en fixes
