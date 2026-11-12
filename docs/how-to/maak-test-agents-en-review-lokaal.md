# Test-agents aanmaken en de bot lokaal reviewen

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Hoe je een eigen set test-agents op `mistral-medium-latest` aanmaakt, de bot lokaal tegen die agents draait en de lokale feedback als rapport ophaalt. Dit is de testomgeving voor een [reviewronde](../../GLOSSARY.md); de productie-agents en de productie-`.env` blijven onaangeroerd (issue #59).

## Voorwaarden

- De project-venv bestaat (zie [CONTRIBUTING.md](../../CONTRIBUTING.md)); alle commando's draaien vanuit de repo-root, tenzij anders vermeld.
- `MISTRAL_API_KEY` staat in `.env` in de repo-root; `scripts/create_agents.py` leest de key daar.
- De libraries bestaan remote. De test-agents gebruiken dezelfde libraries als productie, zie [libraries synchroniseren](synchroniseer-libraries.md).

## Stappen

1. Bekijk eerst wat het script zou doen (dry-run, verandert niets):

   ```powershell
   .venv\Scripts\python scripts\create_agents.py --prefix test- --model mistral-medium-latest
   ```

   Elke agent krijgt het prefix, ook de doelen van de handoffs: `test-router-agent` stuurt door naar `test-knwu-agent`, `test-regio-agent` en `test-club-agent`. Het model uit `scripts/agents_config.json` wordt overschreven.

2. Maak de test-agents aan of werk ze bij:

   ```powershell
   .venv\Scripts\python scripts\create_agents.py --prefix test- --model mistral-medium-latest --apply
   ```

   Het script matcht op naam en is idempotent: draai je het opnieuw na een promptwijziging, dan worden de bestaande `test-`-agents bijgewerkt.

3. Maak `.env.local` aan in de repo-root. Neem `MISTRAL_API_KEY` over en zet de ID's uit de summary van stap 2 (onder `agent ids (zet in .env.local)`) erin:

   ```dotenv
   MISTRAL_API_KEY=...
   MISTRAL_AGENT_ID=...            # test-router-agent (de app)
   MISTRAL_AGENT_ID_KNWU=...       # test-knwu-agent (eval)
   MISTRAL_AGENT_ID_REGIO=...      # test-regio-agent (eval)
   MISTRAL_AGENT_ID_CLUB=...       # test-club-agent (eval)
   MISTRAL_AGENT_ID_ARCHIEF=...    # test-archief-agent (eval)
   ```

   Met `ENV_FILE` laden app en eval **alleen** deze file, niet ook `.env`. Daarom moet `MISTRAL_API_KEY` er ook in staan. `.env.local` staat in `.gitignore`.

4. Start de app lokaal tegen de test-agents. Een relatief pad in `ENV_FILE` geldt vanaf de repo-root:

   ```powershell
   $env:ENV_FILE = ".env.local"
   cd app
   ..\.venv\Scripts\python -m uvicorn main:app --port 8000
   ```

   Open `http://localhost:8000` en geef je beoordeling met de feedbackknop. De feedback komt in de lokale database `app/data/wtchat.db`, gescheiden van productie.

5. Draai desgewenst de eval-set tegen de test-agents (vanuit de repo-root, met `ENV_FILE` nog gezet):

   ```powershell
   .venv\Scripts\python eval\run_eval.py
   ```

6. Maak een rapport van de lokale feedback:

   ```powershell
   .venv\Scripts\python scripts\feedback_report.py --db app\data\wtchat.db
   ```

7. Ben je klaar, verwijder dan `ENV_FILE` uit je shell, zodat volgende commando's weer `.env` gebruiken:

   ```powershell
   Remove-Item Env:ENV_FILE
   ```

## Controle dat het gelukt is

- In Mistral Studio staan de vijf `test-`-agents naast de productie-agents, met model `mistral-medium-latest`. De handoffs wijzen naar `test-`-agents.
- De app start niet in stub-mode: een vraag in de lokale bot geeft een echt antwoord van Mistral.
- Wijst `ENV_FILE` naar een file die niet bestaat, dan stoppen app en eval met `ENV_FILE bestaat niet: <pad>`.

## Zie ook

- [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md): dezelfde procedure zonder `--prefix` en `--model`.
- [Feedback gebruiken om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md): wat je met het feedbackrapport doet.
- [Eval-set](../reference/eval-set.md): de variabelen die `eval/run_eval.py` leest.
