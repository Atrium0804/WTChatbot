# How-to guides

Stappenplannen voor concrete taken. Zie de [documentatiegids](../DOCUMENTATION_GUIDE.md).

- [Libraries synchroniseren met knowledge-documents](synchroniseer-libraries.md) — dry-run/`--apply` van de sync tussen `knowledge-documents/` en de Mistral-libraries (`scripts/sync_libraries.py`), en Website-teksten importeren in de Club-library (`scripts/import_website_texts.py`)
- [Websearch-allowlist configureren](stel-websearch-allowlist-in.md) — org-level domeinfilter via `/v1/web-filters` (`knwu.nl`, `knwumidden.nl`), zie ADR-0004
- [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md) — dry-run/`--apply` van de zes agents vanuit de actieve variant `scripts/architectures/active` + `scripts/prompts/` (`scripts/create_agents.py`)
- [Feedback raadplegen voor triage](raadpleeg-feedback-voor-triage.md) — counters + negatieve feedback uit de SQLite-DB op de NAS tonen via `scripts/feedback_report.py` (geen opslag in de repo), zie issue #42; per conversatie de antwoordende agent tonen via `scripts/trace_conversation.py` (issue #44)
- [Lokale routing-traces bekijken](bekijk-lokale-routing-traces.md) — terminalevents en een uitsluitend lokaal debugpaneel voor bypasses, intake en agent-routing
- [Zet het verzetadvies aan](zet-het-verzetadvies-aan.md) — verzet-agent aanmaken, `MISTRAL_AGENT_ID_VERZET` zetten en de routes `verzetadvies_vraag` en `verzet_offer_accepted` controleren (ADR-0010)
- [Feedback gebruiken om prompts te finetunen](gebruik-feedback-om-prompts-te-finetunen.md) — de hele loop van feedback ophalen en analyseren naar een prompt-/config-wijziging: failing case in de eval-set, agents deployen, eval-gate draaien, patronen vastleggen in `LEARNINGS.md` (issue #55)
- [Doorloop een reviewronde](doorloop-een-reviewronde.md) — de scenario's uit `eval/reviewvragen.md` lokaal stellen tegen de bot, beoordelen met de feedbackknop, AI-analyse van het rapport en goedgekeurde wijzigingen doorvoeren; per ronde een eigen database (issue #63)
