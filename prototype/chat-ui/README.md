# Prototype: chat-UI + iframe-embedding (issue #14)

**Wegwerp-prototype — geen productiecode, geen PR naar main.** Branch: `prototype/chat-ui`.

## Vraag die dit prototype beantwoordt

Kan de clubsite (AllUnited, wtcwoerden.nl) onze chatpagina embedden via een iframe
(CSP `frame-ancestors` / CORS), en werkt een minimale responsive chat-UI die de
FastAPI-proxy `/chat` aanroept — ook op mobiel?

*Aanname (per issue #14): één minimale pagina, niet meerdere UI-varianten — de issue vraagt
expliciet om een "minimale chat-webapp" om delivery-risico's te testen, geen design-exploratie.*

## Wat er in zit

```
prototype/chat-ui/
├── app.py                  FastAPI-proxy: serves static/, POST /chat, POST /feedback, GET /healthz
│                           + security headers (CSP frame-ancestors, expres GEEN X-Frame-Options)
│                           + rate limit (10 vragen/uur per IP-hash) + max. vraaglengte (1000)
├── static/
│   ├── index.html          responsive mobile-first chat-UI (vanilla JS, geen build step)
│   │                       incl. privacy-notitie + feedbackknoppen (goed/niet goed + optioneel tekstveld)
│   └── embed-test.html     testpagina die de chat in een iframe embedt (zoals een clubsite-artikel)
├── Caddyfile               header-config voor wtchat.famstieltjes.nl (CSP frame-ancestors clubsite)
├── check_clubsite_csp.sh   empirische check: stuurt wtcwoerden.nl CSP/X-Frame-Options?
├── requirements.txt
└── README.md
```

State is expres alleen in-memory (geen DB, geen logging naar productie) — dit is een prototype.

**Privacy-afspraak (HITL-beslissing na #14):** er worden geen IP-adressen gelogd. Rate limiting werkt
in-memory per anonieme client-ID (random UUID in `sessionStorage`). De vraag + het antwoord worden
**alleen** opgeslagen bij een duim-omlaag (`POST /feedback` met `rating=negative` koppelt de laatste
uitwisseling aan de `conversation_id`); bij een duim-omhoog slaan we alleen een teller op (timestamp +
rating, geen tekst). In productie: retentie 30 dagen met automatische purge; learnings geanonimiseerd
permanent in `LEARNINGS.md`; out-of-scope/missende vragen alleen als categorie zonder vraagtekst.

## Lokaal draaien

```bash
cd prototype/chat-ui
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# open http://localhost:8000/  (chat) en http://localhost:8000/embed-test.html (iframe-test)
```

Zonder `MISTRAL_API_KEY` + `MISTRAL_AGENT_ID` in de env geeft `/chat` een stub-antwoord
(duidelijk gemarkeerd), dus je hebt geen API-key nodig om de UI/embedding te testen.
Met beide env-vars gezet, verbindt `/chat` met de Mistral Conversations API (zelfde
aanroep als `eval/run_eval.py`). De key staat in `.env` op de server, nooit in git.

## Embedding testen

1. **Lokaal:** `http://localhost:8000/embed-test.html` — iframe rendert door `frame-ancestors 'self'`.
2. **Tegen de clubsite (de eigenlijke test uit #14):**
   - Deploy op `wtchat.famstieltjes.nl` (Docker + Caddy, zie `Caddyfile`) — óf draai locaal met een
     publieke tunnel.
   - Maak een concept-artikel op wtcwoerden.nl, plak via het `<>`-icoon:
     `<iframe src="https://wtchat.famstieltjes.nl/" width="100%" height="600" title="WTC Woerden chatbot"></iframe>`
   - Publiceer en check in de browserconsole: `Refused to frame ...` = geblokkeerd door CSP van
     ófwel wtcwoerden.nl (frame-src) ófwel onze eigen origin (frame-ancestors / X-Frame-Options).
   - De parent kan de iframe-hoogte niet dynamisch meeveranderen (externe scripts worden door
     AllUnited gestript), dus de chat scrollt intern bij vaste hoogte.
3. **CSP van de clubsite checken:** `bash check_clubsite_csp.sh`

## Headers die wijzelf sturen (app.py zet ze, Caddyfile herhaalt ze)

- `Content-Security-Policy: ... frame-ancestors 'self' https://wtcwoerden.nl https://www.wtcwoerden.nl`
- **Geen `X-Frame-Options`** — anders blokkeert de browser het iframe zelf.
- UI en proxy zitten op dezelfde origin → de `/chat`-calls vanuit de iframe zijn same-origin,
  dus voor de MVP is **geen CORS-configuratie nodig**.

## Bevindingen (ingevuld na test — zie ook comment op issue #14)

- wtcwoerden.nl stuurt op de geteste pagina's **geen CSP-header en geen CSP-meta-tag** en geen
  `X-Frame-Options` (zie `check_clubsite_csp.sh`; CloudFront geeft wel 403 op robot-achtige
  requests zonder browser-User-Agent, maar met een browser-UA zijn pagina's 200).
  → Parent-side blokkeert niets; iframe-embed zou moeten werken zodra onze eigen origin
  `frame-ancestors` (clubsite) toestaat en geen `X-Frame-Options` stuurt. Dit is hier geïmplementeerd.
- Privacy (HITL-review): zie de privacy-afspraak hierboven — `app.py` logt geen IP, `/feedback` slaat
  content alleen op bij `negative`. Geverifieerd: positive feedback = alleen `{timestamp, rating}` in
  `feedback.log`; negative feedback = inclusief `question` + `answer`.
- Nog te verifiëren in een echt AllUnited-artikel: console-melding `Refused to frame ...`
  (echte artikel-pagina's kunnen afwijken van de geteste pagina's).
