# Doorloop een reviewronde

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je één [reviewronde](../../GLOSSARY.md) doorloopt: de vaste scenario's uit [eval/reviewvragen.md](../../eval/reviewvragen.md) zelf stellen aan de lokaal draaiende bot, ze beoordelen met de feedbackknop, de feedback door een AI laten analyseren en de goedgekeurde verbeteringen doorvoeren. Herhaal rondes tot een ronde geen enkele duim omlaag meer oplevert (issue #63).

## Voorwaarden

- `.env` in de repo-root is gevuld (key + agent-ID's van de productie-agents); de agents zijn gedeployed: zie [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md).
- De libraries zijn gesynct met `knowledge-documents/`: zie [Libraries synchroniseren](synchroniseer-libraries.md).
- Alle commando's draaien vanuit de repo-root, tenzij anders vermeld.

## Stappen

1. **Start de app lokaal, met een eigen database voor deze ronde.** Zo staat in de database alleen de feedback van deze ronde. De standaardlimiet van 10 berichten per uur is te laag voor een ronde, dus zet die tijdelijk hoger. Vervang `1` door het nummer van de ronde:

   ```powershell
   $env:DATABASE_PATH = "data\reviewronde-1.db"
   $env:RATE_LIMIT_PER_HOUR = "500"
   cd app
   ..\.venv\Scripts\python -m uvicorn main:app --port 8000 --relo
   ```

   `DATABASE_PATH` is relatief aan `app/`; `app/data/` staat in `.gitignore`.

2. **Doorloop de scenario's.** Open [http://localhost:8000](http://localhost:8000) en volg [eval/reviewvragen.md](../../eval/reviewvragen.md): per scenario een nieuwe conversatie, de beurten in volgorde. Geef bij elk antwoord een duim omhoog of omlaag. Noem bij een duim omlaag in de toelichting het scenario-ID en het controlepunt, bijvoorbeeld `S09: oude categorie niet vertaald`.

3. **Maak het feedbackrapport, buiten de repo.** Open een tweede terminal in de repo-root:

   ```powershell
   .venv\Scripts\python scripts\feedback_report.py --db app\data\reviewronde-1.db > $env:TEMP\reviewronde-1.md
   ```

   Het rapport bevat ruwe vragen en antwoorden. Zet het niet in de repo, een issue of een PR (zie [privacy-afspraken](raadpleeg-feedback-voor-triage.md#privacy-afspraken)).

4. **Laat een AI het rapport analyseren.** Geef het rapport aan een AI-agent (bijvoorbeeld Copilot in deze repo) met de opdracht om per duim omlaag te bepalen:
   - de oorzaak: prompt (`scripts/prompts/`), ontbrekend of verouderd document (`knowledge-documents/`), routing (verkeerde agent of handoff) of de app (contextregels in `app/context.py`);
   - een concreet voorstel voor de wijziging.

   De AI wijzigt nog niets. Bij twijfel over de antwoordende agent: zie [Feedback raadplegen voor triage](raadpleeg-feedback-voor-triage.md) voor `scripts/trace_conversation.py`.

5. **Keur de voorstellen goed of af.** Alleen goedgekeurde voorstellen worden doorgevoerd, op een branch per ronde met een PR die naar issue #58 verwijst.

6. **Werk de agents en libraries bij.** Na een promptwijziging (agents worden in place geüpdatet, de ID's in `.env` blijven gelijk):

   ```powershell
   .venv\Scripts\python scripts\create_agents.py --apply
   ```

   Na een documentwijziging: sync de betreffende library (zie [Libraries synchroniseren](synchroniseer-libraries.md)).

7. **Leg de ronde vast.** Vul een regel in de rondelog onderaan [eval/reviewvragen.md](../../eval/reviewvragen.md): datum, model, scenario-ID's met duim omlaag en de doorgevoerde wijzigingen. Zet terugkerende patronen geanonimiseerd in [LEARNINGS.md](../../LEARNINGS.md). Verwijder daarna het rapport uit `$env:TEMP`.

8. **Start de volgende ronde** bij stap 1, met een nieuw rondenummer.

## Stopcriterium

Levert een ronde geen enkele duim omlaag meer op, dan worden de scenario's cases in de [Eval-set](../reference/eval-set.md).

## Controle dat het gelukt is

- `app\data\reviewronde-<n>.db` bevat alleen de feedback van ronde `<n>`.
- De rondelog in [eval/reviewvragen.md](../../eval/reviewvragen.md) heeft een regel voor de ronde.
- `git status` toont geen feedbackrapport of database.

## Zie ook

- [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md)
- [Feedback gebruiken om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md): dezelfde loop met de productiefeedback en de eval-set
- [Feedback raadplegen voor triage](raadpleeg-feedback-voor-triage.md)
