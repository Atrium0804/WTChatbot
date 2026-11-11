# How-to guides

Stappenplannen voor concrete taken. Zie de [documentatiegids](../DOCUMENTATION_GUIDE.md).

- [Libraries synchroniseren met knowledge-documents](sync-libraries.md) — dry-run/`--apply` van de sync tussen `knowledge-documents/` en de Mistral-libraries (`scripts/sync_libraries.py`)
- [Websearch-allowlist configureren](websearch-allowlist.md) — org-level domeinfilter via `/v1/web-filters` (`knwu.nl`, `knwumidden.nl`, `wtcwoerden.nl`), zie ADR-0004
- [Zet de chatbot op je beginscherm (webapp/PWA)](zet-chatbot-op-je-beginscherm.md) — Android Chrome en iPhone Safari, via `https://chat.famstieltjes.nl`
- [Chatdiagnostiek tonen op een telefoon](chatdiagnostiek-tonen.md) — opt-in browserdiagnostiek zonder chatinhoud, via `?debug=1`
- [Chatlayout testen](test-chatlayout.md) — echte browserlayout en aanvullende apparaatcontroles
- [Productie-agents aanmaken of updaten](create-agents.md) — dry-run/`--apply` van de vijf MVP-agents vanuit `scripts/agents_config.json` + `scripts/prompts/` (`scripts/create_agents.py`)
- [Feedback raadplegen voor triage](feedback-triage.md) — counters + negatieve feedback uit de SQLite-DB op de NAS tonen via `scripts/feedback_report.py` (geen opslag in de repo), zie issue #42; per conversatie de antwoordende agent tonen via `scripts/trace_conversation.py` (issue #44)
