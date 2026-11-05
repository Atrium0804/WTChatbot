# WTChatbot MVP — app (FastAPI-proxy + chat-UI)

Productieversie van het #14-prototype. Fase 1 draait op de Synology NAS achter NPM
op `chat.famstieltjes.nl` (zie ADR-0007); einddoel is de VPS achter Caddy
(automatische HTTPS) op `wtchat.famstieltjes.nl`.

```
app/
├── main.py               FastAPI: /chat, /feedback, /healthz + security headers + rate limit
├── config.py             env-config (.env staat ALLEEN op de server, nooit in git)
├── mistral_client.py     dunne laag over de Mistral Conversations API (mockbaar in tests)
├── store.py              SQLite-feedback: content ALLEEN bij duim-omlaag, retentie 30 dagen + purge
├── static/index.html     responsive mobile-first chat-UI (privacy-notitie + feedbackknoppen)
├── static/manifest.webmanifest  PWA-manifest (issue #35)
├── static/sw.js                 service worker — cachet NOOIT /chat, /feedback, /healthz
├── static/icons/                PWA-iconen uit wielie.jpg (scripts/make_icons.py)
├── tests/test_app.py     offline tests (geen live API-calls)
├── Dockerfile
├── docker-compose.yml    app + caddy (VPS)
├── docker-compose.nas.yml  NAS-variant (via NPM, zonder Caddy) — zie scripts/deploy-nas.ps1
├── Caddyfile             HTTPS + headers voor wtchat.famstieltjes.nl
└── requirements.txt / requirements-dev.txt
```

## Lokaal draaien (offline, stub-mode)

```bash
cd app
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
# open http://localhost:8000/
```

Zonder `MISTRAL_API_KEY` + `MISTRAL_AGENT_ID` answered `/chat` met een
duidelijk gemarkeerd STUB-antwoord — geen API-key nodig om te ontwikkelen.

## Tests

```bash
pytest app/tests   # vanuit repo-root; 100% offline
```

## Met echte Mistral-agent

Zet in `app/.env` (lokaal) of `.env` op de server:

```
MISTRAL_API_KEY=...
MISTRAL_AGENT_ID=...        # de router-agent uit docs/system-prompt.md
```

## Deploy op de VPS (Hetzner CX22, ADR-0002)

1. DNS: A-record `wtchat.famstieltjes.nl` -> VPS-IP.
2. `.env` op de server aanmaken (alleen daar), repo clonen.
3. `cd app && docker compose up -d --build`
4. Check: `curl https://wtchat.famstieltjes.nl/healthz` en één testvraag via de UI.
5. Monitoring: UptimeRobot op `/healthz` (zie docs/operations.md).

## Deploy op de Synology NAS (nas.fritz.box)

NAS-variant: `docker-compose.nas.yml` — zonder Caddy, want host-poorten 80/443 zijn daar van NPM
(Fritz!Box forwardt 80/443 -> NAS 8080/8443). De app draait in het externe `cloud`-netwerk,
alleen `expose: 8000`; NPM regelt reverse proxy + HTTPS.

1. `.\scripts\deploy-nas.ps1 -Apply -Up` (vanuit repo-root) — kopieert `app/docker-compose.nas.yml`
   + de app-source naar `/volume1/docker/wtchatbot/` en buildt/start de container op de NAS
   (de build op de NAS kan een paar minuten duren).
2. `.env` op de NAS aanmaken in `/volume1/docker/wtchatbot/` (alleen daar, nooit in git):
   `MISTRAL_API_KEY` + `MISTRAL_AGENT_ID`.
3. NPM proxy host: `chat.famstieltjes.nl` -> `http://wtchatbot:8000` (Let's Encrypt, Force SSL).
4. Check: `curl https://chat.famstieltjes.nl/healthz` en één testvraag via de UI.

## Security/privacy-headers

- CSP incl. `worker-src 'self'` + `manifest-src 'self'` (PWA, issue #35), `frame-ancestors 'self'` + `X-Content-Type-Options: nosniff`; expres géén
  `X-Frame-Options`. Post-MVP iframe-embed (#14): `FRAME_ANCESTORS` in config
  verbreden naar de clubsite-origin.
- Rate limiting: 10 vragen/uur per anonieme client-ID (in-memory), max. 1000
  tekens per vraag. Er worden géén IP-adressen opgeslagen.
- Feedback: bij duim-omlaag slaan we vraag+antwoord+bronnen op (30 dagen,
  automatische purge); bij duim-omhoog alleen een teller.
