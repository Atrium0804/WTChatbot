---
status: accepted
---

# Fase 1 op de Synology NAS achter NPM; de VPS uit ADR-0002 blijft het einddoel

Amendeert [ADR-0002](0002-vps-met-eigen-proxy.md) voor de deployment-locatie in fase 1: de chatbot draait eerst op de eigen NAS, publiek ontsloten via NPM (nginx-proxy-manager) met een Let's Encrypt-certificaat op `chat.famstieltjes.nl`. Later migreert de dienst naar de VPS uit ADR-0002. De webapp-installatie (PWA, issue #35) vereist HTTPS — een service worker registreert alleen op een beveiligde origin — en dat levert NPM op de NAS al.

## Considered options

- **Direct op de VPS (ADR-0002)** — uitgesteld, niet verworpen: blijft het einddoel; de Caddy-variant (`app/docker-compose.yml` + `app/Caddyfile`) ligt klaar.
- **NAS via Cloudflare Tunnel** — verworpen in ADR-0002 (security-risico voor de thuisomgeving). De NAS draait inmiddels al publiek via NPM-poortforwarding voor eigen diensten; de club accepteert dat voor fase 1.
- **LAN-only over plain HTTP** — verworpen voor de webapp: zonder HTTPS geen service worker, dus geen Android-installatieprompt en geen app-shell. LAN-HTTP blijft alleen testpad.

## Consequences

- Beschikbaarheid: een clubdienst op een thuisnetwerk is onbetrouwbaar (stroomuitval, NAS-updates, dynamisch IP) — bewust geaccepteerd voor fase 1.
- De Mistral API-key staat in fase 1 in `.env` op de NAS (nooit in git; rotatieprocedure ongewijzigd, zie [docs/operations.md](../operations.md)). De blast radius van een gelekte key is daarmee de NAS.
- Deploy: `scripts/deploy-nas.ps1` kopieert `app/docker-compose.nas.yml` + app-source naar `/volume1/docker/wtchatbot/`; NPM proxy host `chat.famstieltjes.nl` -> `http://wtchatbot:8000` op het externe `cloud`-netwerk. `.env` en `data/` blijven NAS-only.
- Exit naar de VPS: DNS verleggen; `start_url`/`scope` in het manifest zijn relatief, dus de app zelf wijzigt niet mee.
- PWA: `app/static/manifest.webmanifest` + `sw.js` + `icons/`; de service worker cachet nooit `/chat`, `/feedback` of `/healthz` (privacy-afspraak).
