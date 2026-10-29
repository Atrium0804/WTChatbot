---
status: accepted
---

# VPS met eigen FastAPI-proxy — API-key server-side

De Mistral API-key staat nooit in de browser: een dunne FastAPI-proxy op een eigen VPS (Hetzner CX22, Docker + Caddy met automatische HTTPS) roept de Mistral API aan. De proxy is de enige plek met rate limiting, logging, feedback-opslag en retentie-purge.

## Considered options

- **Direct vanuit de browser naar Mistral** — verworpen: de API-key is een volledige factureerbare sleutel en in de browser leesbaar voor elke bezoeker; geen rate limiting of logging mogelijk.
- **NAS thuis met Cloudflare Tunnel** — verworpen: een 24/7-clubdienst op een thuisnetwerk is onbetrouwbaar (stroomuitval, NAS-updates, dynamisch IP) en een security-risico voor de thuisomgeving. (Poortforwarding zonder tunnel is sowieso uitgesloten.)
- **PaaS free-tier** — verworpen: free-tiers slapen na ~15 minuten in, waardoor de eerste vraag van een ouder 10–30 seconden duurt.

## Consequences

- Kosten ±€ 3,79 p/m (CX22) plus operationele verantwoordelijkheid: OS-updates, firewall (ufw), fail2ban, monitoring (`/healthz` + UptimeRobot).
- Deploy: fase 1 via SSH/GitHub Actions (`docker compose up -d --build`), fase 2 via geteste images in ghcr.io. `.env` bestaat alleen op de server, nooit in git (gitleaks in CI). De VPS beperkt de blast radius van een gelekte key: rotatieprocedure staat in `docs/operations.md`.
