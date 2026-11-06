# Operations

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Runbook voor het beheer van de WTChatbot-MVP: wie waarvoor verantwoordelijk is en welke procedures gelden voor meldingskanalen, API-keys, monitoring, websearch-allowlist en seizoenwissel. Termen volgen [GLOSSARY.md](../GLOSSARY.md); de onderliggende architectuurbesluiten staan in de [ADR's](adr/).

## Beheerder en vervanger

De **beheerder** is de benoemde eindverantwoordelijke voor ntfy-alerts, feedback-triage, library-updates bij seizoenstart en het archief van oude versies (zie [GLOSSARY.md](../GLOSSARY.md)). De vervanger neemt over bij afwezigheid.

| Rol | Naam en rol binnen WTC Woerden |
| --- | --- |
| Beheerder | Botty mc Botface — botbeheerder |
| Vervanger | _Vacant — nog te benoemen_ |

## ntfy versiecheck-meldingen (post-MVP)

De post-MVP cron-job op de VPS vergelijkt `knowledge-documents/versions.json` met het Kenniscentrum en meldt mismatches via ntfy aan de beheerder ([ADR-0005](adr/0005-library-bevat-alleen-actuele-versies.md)).

- Server + topic: `https://ntfy.sh/wtchat-beheer-a6b2zaq7d7i2svcf1c86qpae`
- Het topic is geheim: iedereen met het topic kan lezen en posten. Deel het alleen met beheerder en vervanger.

## Mistral API-key rotatie

De Mistral API-key is een volledige factureerbare sleutel en staat daarom **alleen in `.env` op de server** (fase 1: de NAS — zie [ADR-0007](adr/0007-fase-1-op-nas-achter-npm.md); einddoel: de VPS) — nooit in code of git (gedekt door de gitleaks-secrets-scan in CI, `.github/workflows/secrets-scan.yml`; `.env` is geverifieerd niet getrackt). Zie [ADR-0002](adr/0002-vps-met-eigen-proxy.md) voor de afweging.

Rotatieprocedure:

1. Maak een nieuwe key aan in de Mistral Console (workspace-gescopet, met spend cap).
2. Vervang de key in `.env` op de server (SSH).
3. Herstart de proxy: `docker compose up -d --build`.
4. Controleer `/healthz` en stel één testvraag via de chat-UI.
5. Revoke de oude key in de Mistral Console.

Blast radius van een gelekte key: de key is direct factureerbaar. In fase 1 bestaat de key alleen op de NAS (`/volume1/docker/wtchatbot/.env`, ADR-0007) en wordt alleen door de FastAPI-proxy gebruikt; de workspace spend cap en rate limiting (ADR-0002) beperken de schade. Rotate bij vermoeden van een lek direct, volg bovenstaande stappen.

## Monitoring en VPS-toegang

Bij een browsergebonden chatfout: volg [chatdiagnostiek tonen op een telefoon](how-to/chatdiagnostiek-tonen.md).

- De FastAPI-proxy exposet een `/healthz` endpoint (controleert onder andere de bereikbaarheid van de Mistral API).
- Externe monitoring: UptimeRobot (of een alternatief — nog te beslissen) checkt elke 5 minuten `https://chat.famstieltjes.nl/healthz` (fase 1, NAS; fase 2 op de VPS: `https://wtchat.famstieltjes.nl/healthz`) en alert bij failure. Accountgegevens staan in de password manager van de club, nooit in git.
- Deploy fase 1 (NAS): `.\scripts\deploy-nas.ps1 -Apply -Up` vanuit de repo-root; NPM proxy host `chat.famstieltjes.nl` -> `http://wtchatbot:8000` (Let's Encrypt, Force SSL). Zie [ADR-0007](adr/0007-fase-1-op-nas-achter-npm.md) en [app/README.md](../app/README.md).
- VPS: Hetzner CX22 (±€ 4/maand), Docker + Caddy. Toegang via SSH met keys (geen wachtwoordlogin), firewall via `ufw` en `fail2ban` (zie [ADR-0002](adr/0002-vps-met-eigen-proxy.md)).

## Websearch-allowlist

De websearch-tool van de agent is beperkt tot de gezaghebbende domeinen `knwu.nl` (inclusief kenniscentrum.knwu.nl), `knwumidden.nl` en `wtcwoerden.nl` — nooit het open web. Afdwinging: system prompt + eval-set, en optioneel server-side via een org-level allowlist (`/v1/web-filters`) — maar die filter is **org-breed** en treft álle applicaties in de Organization, dus alleen toe te passen als de org dedicated is voor de WTChatbot (ADR-0004, amendment 2026-11-04; in een gedeelde org: prompt-only). Zie [ADR-0004](adr/0004-websearch-beperkt-tot-kenniscentrum.md) voor de beslissing en [how-to: websearch-allowlist configureren](how-to/websearch-allowlist.md) voor de exacte endpoints, payloads en matchregels.

## Seizoenwissel-procedure

Seizoenwissel is een kritieke operatie (zie [ADR-0005](adr/0005-library-bevat-alleen-actuele-versies.md) en [project_description.md](project_description.md)):

1. Vervang het document in de lokale bronmap: oude versie naar `knowledge-documents/archive/` (met datum in de bestandsnaam), nieuwe versie in `knowledge-documents/<library>/`. Bevat de nieuwe PDF doorhalingen of rode revisies (KNWU-reglementen), zet dan niet de PDF maar de opgeschoonde markdown in de library en het originele PDF in het archief (ADR-0005, amendment 2026-11-05):
   `.venv/Scripts/python scripts/clean_pdf.py knowledge-documents/knwu/<document>.pdf --out knowledge-documents/knwu`
   Het script schrijft ook een [opschoonrapport](../GLOSSARY.md) naar `knowledge-documents/review/<document>.md` (andere map: `--review <map>`), met bovenaan de twijfelgevallen. Een mens vinkt die af vóór de sync; rapport en opgeschoonde versie gaan samen in één commit (zie [how-to: libraries synchroniseren](how-to/sync-libraries.md)).
   Draai daarna de library-sync (zie [how-to: libraries synchroniseren](how-to/sync-libraries.md)) — die zet de nieuwe versie in de actieve library en de oude versie in de archief-library.
2. Werk `knowledge-documents/versions.json` bij (documentnaam → versiedatum).
3. Re-run de eval-set (`eval/run_eval.py`); launch-gate is ≥90% correct mét correcte bron.
4. Noteer wat er gewijzigd is in [LEARNINGS.md](../LEARNINGS.md).

In de MVP is de versiecheck handmatig (bij elke library-update); de automatische cron-check via ntfy is post-MVP (zie boven).
