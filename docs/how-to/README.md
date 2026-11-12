# How-to guides

Stappenplannen voor concrete taken. Zie de [documentatiegids](../DOCUMENTATION_GUIDE.md).

- [Libraries synchroniseren met knowledge-documents](synchroniseer-libraries.md) — dry-run/`--apply` van de sync tussen `knowledge-documents/` en de Mistral-libraries (`scripts/sync_libraries.py`)
- [Websearch-allowlist configureren](stel-websearch-allowlist-in.md) — org-level domeinfilter via `/v1/web-filters` (`knwu.nl`, `knwumidden.nl`, `wtcwoerden.nl`), zie ADR-0004
- [Zet de chatbot op je beginscherm (webapp/PWA)](zet-chatbot-op-je-beginscherm.md) — Android Chrome en iPhone Safari, via `https://chat.famstieltjes.nl`
- [Chatdiagnostiek tonen op een telefoon](toon-chatdiagnostiek-op-je-telefoon.md) — opt-in browserdiagnostiek zonder chatinhoud, via `?debug=1`
- [Chatlayout testen](test-chatlayout.md) — echte browserlayout en aanvullende apparaatcontroles
- [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md) — dry-run/`--apply` van de vijf MVP-agents vanuit `scripts/agents_config.json` + `scripts/prompts/` (`scripts/create_agents.py`)
- [Feedback raadplegen voor triage](raadpleeg-feedback-voor-triage.md) — counters + negatieve feedback uit de SQLite-DB op de NAS tonen via `scripts/feedback_report.py` (geen opslag in de repo), zie issue #42; per conversatie de antwoordende agent tonen via `scripts/trace_conversation.py` (issue #44)
- [Feedback gebruiken om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md) — de hele loop van feedback ophalen en analyseren naar een prompt-/config-wijziging: failing case in de eval-set, agents deployen, eval-gate draaien, patronen vastleggen in `LEARNINGS.md` (issue #55)
- [Test-agents aanmaken en de bot lokaal reviewen](maak-test-agents-en-review-lokaal.md) — `test-`-agents op `mistral-medium-latest` via `create_agents.py --prefix/--model`, hun ID's in `.env.local` (`ENV_FILE`), de app lokaal starten en een rapport van de lokale feedback maken (issue #59)
