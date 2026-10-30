# KNWU-kennischatbot voor de website van WTC Woerden — bijgewerkt ontwerp

**Project:** een publieke chatbot op de clubwebsite die vragen over KNWU-regelgeving, licenties, MNC/ZMC-wedstrijden en jeugdwielrennen beantwoordt op basis van de eigen documenten (RAG), met het KNWU Kenniscentrum als online autoriteit. Andere wielrenclubs mogen de bot **as-is** gebruiken (ADR-0001).

**Doel van dit document:** je bouwt het zelf in VS Code, van nul tot productie, en doet onderweg de kennis op. De documentatie is ingedeeld volgens het **Diataxis**-model:

| Quadrant | Voor wie | Vraag die het beantwoordt |
| --- | --- | --- |
| 🎓 **Tutorial** | nieuw in het onderwerp | *"Ik leer dit — neem me bij de hand"* |
| 🛠 **How-to** | kent de basis | *"Ik wil taak X klaar hebben"* |
| 📚 **Reference** | weet wat hij doet | *"Ik wil dit even opzoeken"* |
| 💡 **Explanation** | wil het begrijpen | *"Waarom is het zo ontworpen?"* |

**Vastgelegde beslissingen:** zie `docs/adr/0001` t/m `0006`. **Begrippen:** zie `GLOSSARY.md` (Kenniscentrum, bibliotheken, bronvolgorde, zichtbare revisies, wijzigingsmemo, taalniveau B1/B2, Ontwicklung, eval-set, beheerder).

**Architectuur in één oogopslag**

```
Bezoeker (publiek, anoniem) → clubsite (AllUnited) — iframe / ClubApp-webview naar chat.wtcwoerden.nl
  → VPS (Hetzner CX22) — Caddy (HTTPS) + FastAPI-proxy in Docker (API-key server-side, rate limiting, logging)
  → Mistral Conversations API → Agent (system prompt = wtc-knwu-kennisroutering + taalniveau)
  → Library (RAG): alleen ACTUELE documenten — WTC/Regio-bibliotheek + KNWU-bibliotheek
  → websearch-tool: AAN, scope beperkt tot kenniscentrum.knwu.nl (ADR-0004)
  → (post-MVP) calculator-tool voor verzettenadvies (ADR-0006)
```

---

## 🎓 1. Tutorial — van nul tot werkend prototype (dag 1–3)

*Learning-oriented: elke stap heeft één gegarandeerd resultaat. Niet afwijken, eerst laten werken, dan verbeteren.*

### Stap 1 — Studio-account en API-key (±15 min)

1. Ga naar [console.mistral.ai](https://console.mistral.ai) met je Mistral-account.
2. Activeer Studio en genereer een API-key. Volg: [Studio activeren en API-key genereren](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key).
3. Zet de key in een `.env`-bestand (`.env` in `.gitignore`!), nooit hardcoden.
4. **Stel meteen een spend-limiet in** via [Usage limits](https://docs.mistral.ai/admin/billing-usage/usage-limits) — je betaalt per API-aanroep.

✅ *Resultaat: een werkende key in een environment variable.*

### Stap 2 — Eerste API-request vanuit VS Code (±30 min)

1. Maak een projectmap, `python -m venv .venv`, activeer.
2. `pip install mistralai` — SDK-overzicht: [Mistral SDK's](https://docs.mistral.ai/resources/sdks).
3. Schrijf een script `hello.py` dat één chat-completion-request doet. Volg: [Send your first API request](https://docs.mistral.ai/getting-started/quickstarts/developer/first-api-request).
4. Start klein en goedkoop: kies een fast/flash-model uit de [Model selection guide](https://docs.mistral.ai/inference/model-selection-guide).

✅ *Resultaat: lokaal antwoord van het model in je terminal.*

### Stap 3 — Documenten uploaden en RAG bevragen (±1 uur)

1. Maak **twee** Libraries in Studio aan: **"WTC en regio kennis"** (ZMC, MNC Veldrijden 2025, MNC 2026 Hans vd Hengel, NRC-artikel) en **"KNWU-kennis"** (Titel 20 Jeugdwielrennen, Nationale Besluiten, Handboek Veldrijden Jeugd). Upload alleen de **actuele** versies (ADR-0005); oude versies horen in het repo-archief `knowledge-documents/archive/`, nooit in de Library.
2. Volg: [Set up RAG with document search](https://docs.mistral.ai/getting-started/quickstarts/developer/rag-document-search).
3. Test met vragen waarvan je het antwoord al kent ("Wat is de minimale leeftijd voor categorie U13?") — controleer of retrieval het juiste document pakt.

✅ *Resultaat: antwoorden met bronvermelding uit je eigen documenten.*

### Stap 4 — Agent met de routeringsregels (±1 uur)

1. Maak een agent (server-side) met de [Agents & Conversations API](https://docs.mistral.ai/studio/agents/agents-api).
2. System prompt = de skills uit `WebsiteWTCjeugd/.vibe/skills/` — **`wtc-knwu-kennisroutering`** (bronvolgorde, versiecontrole, zichtbare revisies, licentie-/NK-/verzekeringsregels, verhelderingsvragen, "verzin niets") en **`taalniveau`** (B1 standaard, B2 op verzoek, B1-aanbod bij B2, controleronde). Neem ze integraal over.
3. Zet de RAG-koppeling aan, **per bibliotheek gescoped** (nooit ongescopeerd over beide).
4. Zet de **websearch-tool aan met domain-restriction op `kenniscentrum.knwu.nl`** (ADR-0004).
5. De ontwerpbeslissingen (ADR-0001–0005) die niet in de skills staan, voeg je toe aan de system prompt:
   - Publiek & anoniem; off-topic (geen wielrennen/KNWU/club) → beleefd weigeren en doorverwijzen.
   - Altijd bron + versiedatum vermelden; bij conflicten/onzekerheid expliciet signaleren + KNWU-contact (+31 (0)85 070 1900, di–vr 8.30–12.00).
   - Nederlands; standaard B1, B2 via UI-toggle of verzoek; bij elk B2-antwoord aanbieden om (deel) naar B1 om te zetten.
   - Max. 4 verhelderingsvragen tegelijk, in één bericht, alleen als het antwoord erdoor verandert.
   - "Doorgestreepte tekst is nooit de huidige regel" + bij twijfel over de status van een passage: expliciet melden.
6. Volg zo nodig: [Build an agent with tools](https://docs.mistral.ai/getting-started/quickstarts/developer/build-an-agent).

✅ *Resultaat: een agent-id die antwoordt volgens jouw regels.*

### Stap 5 — Lokale chatloop (±30 min)

1. Schrijf een CLI-chatloop (`while True: input() → conversations start → print antwoord`) met streaming.
2. Test met echte clubvragen: licenties (Basis/Plus/Premium + startrecht vs. pakket), NK-eisen per discipline/categorie, MNC/ZMC-regels, verzekeringen.
3. Test de eval-set (zie How-to E): ±20 vragen met verwacht antwoord/bron.

✅ *Resultaat: werkend lokaal prototype. Nu pas doorgaan naar de how-to's.*

---

## 🛠 2. How-to — van prototype naar productie

- [ ] **How-to A: VPS inrichten met Docker + Caddy**
- [ ] **How-to B: chatbot op de AllUnited-clubsite plaatsen (iframe + ClubApp-webview)**
- [ ] **How-to: misbruik beperken** — rate limiting (IP-hash, bijv. 10 vragen/uur), maximale vraaglengte, max. 4 verhelderingsvragen per bericht
- [ ] **How-to: documenten verversen bij seizoenwissel** — incl. archief en eval-set her-run
- [ ] **How-to: versiecheck tegen het Kenniscentrum** — cron + ntfy (ook in-chat detectie via function calling)
- [ ] **How-to: websearch-tool configureren** — scope beperken tot kenniscentrum.knwu.nl
- [ ] **How-to: privacy & retentie** — 90 dagen, gehashte IP's, privacy-notitie in de UI
- [ ] **How-to: feedback- en learnings-loop**
- [ ] **How-to: ontwikkelomgeving — branching, tests, CI, deployment**
- [ ] **How-to F (post-MVP): verzettenadvies bouwen**

### How-to A: VPS inrichten met Docker + Caddy (Hetzner)

1. **Server aanmaken** — Hetzner Cloud, type CX22 (2 vCPU, 4 GB RAM, 40 GB, ±€ 3,79 p/m), locatie Duitsland/Nederland, image: Ubuntu LTS. SSH-key toevoegen (geen wachtwoord-login).
2. **Basis hardened** — `apt update && apt upgrade`, firewall aan (`ufw allow 22,80,443`), fail2ban voor SSH.
3. **Docker installeren** — officiële Docker-repository, daarna `docker compose` voor alles; niets buiten Docker draaien.
4. **Projectstructuur lokaal (VS Code)**:
   ```
   knwu-chatbot/
     app/main.py          # FastAPI: /chat (SSE-streaming), /healthz
     app/ratelimit.py     # IP-hash based limiet (bijv. 10 vragen/uur)
     app/privacy.py       # 90-dagen retentie-purge, privacy-notitie
     Dockerfile
     docker-compose.yml   # app + caddy (+ ntfy optioneel)
     Caddyfile            # chat.wtcwoerden.nl → reverse proxy naar app:8000
     .env                 # MISTRAL_API_KEY, AGENT_ID (alleen op server, niet in git)
   ```
5. **Caddy als reverse proxy** — automatische HTTPS via Let's Encrypt. In Caddy: `Content-Security-Policy: frame-ancestors <clubsite-domein> <ClubApp-origin>` — geen wildcard.
6. **Deploy vanaf je laptop** — `docker compose up -d --build` via SSH. Later: CI (How-to E).
7. **DNS** — `chat.wtcwoerden.nl` → A-record naar het VPS-IP.
8. **Verificatie** — `curl https://chat.wtcwoerden.nl/healthz` → `{"status": "ok"}`.

### How-to B: chatbot op de clubsite (AllUnited) en in de ClubApp

*Bevestigd door AllUnited: links zijn altijd mogelijk; iframes in artikelen/pagina's mits de externe site framing toestaat.*

**ClubApp — Website-module (snelste route):**

1. Appbeheer → Modules → Module toevoegen → **Website**.
2. Naam bijv. "Vraag de club-assistent", URL `https://chat.wtcwoerden.nl`.
3. Zichtbaar voor leden. De bot opent in een webview — **responsive/mobiel ontwerp is een vereiste**.

**Iframe in artikel/pagina:**

1. Artikel/pagina openen → broncode-icoon (`<>`) → `<iframe src="https://chat.wtcwoerden.nl" width="700" height="900"></iframe>` (breedte 100% op mobiel).
2. CORS op de proxy beperken tot clubsite/ClubApp-origins.

**Alternatief:** link in nieuwsbericht/menu — werkt altijd.

### How-to: documenten verversen bij seizoenwissel (beheerder)

1. Nieuw KNWU-document (bijv. nieuwe Nationale Besluiten) gedetecteerd via de cron-versioncheck of ntfy-melding.
2. Vervang het document in de **Library** (oud PDF eruit, nieuw erin — de Library bevat nóóit oude versies, ADR-0005).
3. Archiveer de oude versie in `knowledge-documents/archive/` in de repo, met datum in de bestandsnaam.
4. Werk `versions.json` bij (documentnaam → versiedatum).
5. **Re-run de eval-set** (launch-gate ≥90% ook hier, ADR-0005); noteer in `LEARNINGS.md`.
6. "Wat is er veranderd?"-vragen beantwoordt de bot uit de **wijzigingsmemo op het Kenniscentrum** — niet door lokale PDF's te diffen.

### How-to: versiecheck tegen het Kenniscentrum (cron + ntfy)

**Laag 1 — passieve check (cron op de VPS, wekelijks):**

1. `versions.json` in de proxy: documentnaam → versiedatum zoals in de Library.
2. Cron-job vergelijkt met de [Kenniscentrum-regelgevingpagina](https://kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten).
3. Mismatch → ntfy-melding naar de beheerder (+ regel in de `outdated`-tabel).

**Notificatiekanaal — ntfy:** publieke ntfy.sh in de startfase (lange willekeurige topicnaam, bijv. `knwu-bot-x7q4m2v9`); optioneel later self-hosted op dezelfde VPS. Hergebruik het kanaal voor healthcheck/cron/disk-alerts.

**Laag 2 — in-chat detectie (function calling):** tool `report_outdated_document(document, library_versie, kenniscentrum_versie)`; de proxy vangt de call af, logt en notify't; de vraagsteller krijgt gewoon antwoord.

### How-to: websearch-tool configureren (ADR-0004)

1. Zet de [Websearch-tool](https://docs.mistral.ai/studio/agents/agent-tools/websearch) aan op de agent.
2. Beperk de scope in de toolconfig/instructies tot `kenniscentrum.knwu.nl` (en KNWU-eigen pagina's). Open web is bewust UIT.
3. System prompt: licentievragen raadpleegt **altijd óók** het Kenniscentrum (pakketten/tarieven staan niet in de documenten); verzekeringsvragen primair via de sectie Verzekeringen van het Kenniscentrum.
4. Let op: websearch kost extra per vraag — houd het spend-limiet in de gaten.

### How-to: privacy & retentie (ADR uit round 2, Q8)

1. Feedback- en chatlogs (vraag, antwoord, bronnen, `conversation_id`, timestamp) in SQLite op de VPS: **retentie 90 dagen**, daarna automatische purge.
2. IP's alleen als salted hash ten behoeve van de rate limiter; nooit plain in logs die geback-upt worden.
3. Geen geheugens tussen sessies: elke bezoeker start een fresh conversation; `conversation_id` dient alleen feedback/abuse.
4. Korte privacy-notitie in de chat-UI ("we bewaren je vraag 90 dagen om de bot te verbeteren; geen account nodig").

### How-to: feedback- en learnings-loop

1. **Opvangen** — 👍/👎 onder elk antwoord + optioneel tekstveld bij 👎. SQLite: vraag, antwoord, bronnen, `conversation_id`, timestamp.
2. **Technische logs** — retrieval-misses, geweigerde (off-topic) vragen, websearch-fouten, tool-errors.
3. **Triage** — `/admin/feedback` (beheerder-only, basic auth): 👎's en fouten, oudste eerst.
4. **Fix op de juiste laag:**
   | Probleem | Fix |
   | --- | --- |
   | Antwoord uit verouderd document | Library verversen + archief |
   | Antwoord klopt, onduidelijk | system prompt bijschaven |
   | Verkeerd reglement opgepikt | preprocessing/chunking verbeteren |
   | Vraag niet gedekt | document toevoegen |
   | Strikethrough passage geciteerd | ingestion-cleaning aanscherpen + prompt-regel handhaven |
5. `LEARNINGS.md` bijhouden: terugkerend probleem + toegepaste fix.

### How-to E: ontwikkelomgeving — branching, tests, CI, deployment

**Structuur:**

```
knwu-chatbot/
  app/                    # FastAPI-app
  tests/                  # pytest; unit-tests zonder live API
  eval/                   # eval-set: ±20 vragen + verwacht antwoord/bron (pytest -m integration)
  .env.example
  .pre-commit-config.yaml # ruff, gitleaks
  .github/workflows/ci.yml
  pyproject.toml
```

**Branching — trunk-based (solo):** `main` altijd deploybaar; korte feature-branches; conventional commits; `main` breekt nooit.

**Tests:** injecteer de Mistral-client (fakes in tests, geen live calls in CI). Unit: rate limiter, feedback-opslag, retentie-purge, versiecheck, tool-call-afhandeling, system-prompt-consistentie. **LLM-kwaliteit NIET in unit-tests** maar via de eval-set (`pytest -m integration` tegen de echte agent): ±20 typische clubvragen met verwacht antwoord/bron; **launch-gate ≥90% correct mét correcte bron**, her-run na elke Library-update.

**CI — één GitHub Actions-workflow:** ruff → mypy → pytest (unit) → gitleaks. Pre-commit hooks in VS Code voor ruff/mypy.

**Deployment — twee fasen:** fase 1 = na groene CI via SSH `git pull && docker compose up -d --build` (deploy-key als GitHub secret; `.env` alleen op de server); fase 2 = image build → ghcr.io, VPS pullt de geteste image. Tag releases (`v0.1.0`) bij live.

### How-to F (post-MVP): verzettenadvies (ADR-0006)

**Doel:** advies welk verzet geschikt is voor een renner, gegeven **geboortejaar** en **fiets** (bandenmaat); op verzoek check of een verzet daadwerkelijk in de handel is.

**Architectuur — hybride:**

1. **RAG-laag:** de KNWU-regel (max. **verzet** in meters per omwenteling, per leeftijdscategorie/discipline — wisselt per seizoen) komt uit de KNWU-bibliotheek — nooit hardcoded in de tool.
2. **Calculator-tool (function calling, deterministisch):** berekent alle combinaties kettingblad × cassette × bandenmaat en filtert op het toegestane max. Verzet:
   `verzet (m) = (tanden voor / tanden achter) × wielomtrek (mm) / 1000`.
3. **Data:** `docs/knowledge/bandenmaat-wielomtrek.csv` en `cassette-overzicht.csv` als versie beheerde tool-data in het repo (MD-versies in de Library ter uitleg); jaarlijks gereviewd door de beheerder.
4. **Wielomtrek bepalen:** flow = wielmaat (24/26/28") → banddikte (25/28/30mm) → lookup in `bandenmaat-wielomtrek.csv`. De tabel is compleet voor deze gangbare combinaties (ontbrekende waarden zijn vooraf uitgerekend met `omtrek ≈ π × (velgdiameter + 2 × banddikte)`, gemarkeerd met * in de MD; geen runtime-fallback nodig). Elke (wielmaat, banddikte) heeft een `standaard`-rij (24"→507, 26"→559, 28"→622), dus de lookup is deterministisch — voor 24" volstaat de standaard op bandenmaat (zeldzame fietsjes, niet vooraf op te meten). Staat de ETRTO-code op de bandenzijkant (bijv. 28-622), dan pakt de bot de exacte ETRTO-rij.
5. **Beschikbaarheidscheck (op verzoek):** lookup in cassette-/kettingblad-tabellen (incl. freehub-compatibiliteit). Een kettingblad dat niet op de crank past (boutsteek/BCD) → expliciete onzekerheidsmelding, geen feit.
6. **Verhelderingsvragen:** max. 4 tegelijk, in één bericht (geboortejaar, wielmaat/banddikte, voorblad, cassette).
7. Eval-set uitbreiden met typisch verzetvragen ("mag een U15 met 28-622-banden een 52-14 rijden?").

---

## 📚 3. Reference — naslagwerk

### Beslissingen en termen

- `docs/adr/0001` — enkele publieke instance, as-is, geen multi-tenancy
- `docs/adr/0002` — VPS + eigen proxy, API-key server-side
- `docs/adr/0003` — RAG over eigen documenten; Kenniscentrum = autoriteit
- `docs/adr/0004` — websearch aan, scope = kenniscentrum.knwu.nl
- `docs/adr/0005` — Library alleen actuele versies; wijzigingen via Kenniscentrum-memo; eval-gate
- `docs/adr/0006` — verzettenadvies hybride (RAG + calculator)
- `GLOSSARY.md` — alle Domeinbegrippen

### Kern-API's

| Wat | Waar |
| --- | --- |
| Chat-completions / eerste request | [First API request](https://docs.mistral.ai/getting-started/quickstarts/developer/first-api-request) |
| Agents & Conversations API | [Agents API](https://docs.mistral.ai/studio/agents/agents-api) |
| RAG / Libraries | [RAG quickstart](https://docs.mistral.ai/getting-started/quickstarts/developer/rag-document-search) |
| Agent-tools (websearch, function calling) | [Tools overview](https://docs.mistral.ai/studio/agents/agent-tools) |
| SDK's (Python, TS) | [SDK's](https://docs.mistral.ai/resources/sdks) |
| HTTP-foutcodes | [Error glossary](https://docs.mistral.ai/resources/error-glossary) |

### Modellen, prijzen, infra

- [Modeloverzicht](https://docs.mistral.ai/models), [Model selection guide](https://docs.mistral.ai/inference/model-selection-guide), [API pricing](https://docs.mistral.ai/inference/pricing), [OCR-modellen](https://docs.mistral.ai/models/ocr-4-1)
- Hetzner CX22 (±€ 3,79 p/m) · Ubuntu LTS · Docker Compose · Caddy (auto-HTTPS) · `/healthz` + UptimeRobot

### Te schrijven naslag (onderdeel van het leerdoel)

- `docs/architecture.md`, `docs/system-prompt.md`, `docs/endpoints.md`, `docs/operations.md` (incl. beheerder + vervanger, key-rotatie, kostenplafond, versie-schema)

### Kernbegrippen

- **RAG**: het model antwoordt uit de geüploade documenten, niet uit zijn geheugen.
- **Library**: de documentverzameling in Studio (per club twee: WTC/Regio + KNWU).
- **Agent**: model + system prompt + tools.
- **Kenniscentrum**: autoritatieve online bron van de KNWU (kenniscentrum.knwu.nl).
- **Verzet**: de afstand per pedaalomwenteling in meters — hoe de KNWU het max. toegestane verzet specificeert.

---

## 💡 4. Explanation — het waarom

### Waarom een publieke instance as-is (ADR-0001)?

De bot is een clubdienst; de onderliggende documenten (KNWU-reglementen, clubreglementen) zijn sowieso publiek. Inloggen voegt een auth-laag toe zonder winst, en multi-tenancy/per-club config is ballast voor deze schaal. Andere clubs gebruiken de bot as-is met de WTC/KNWU-informatie die erin zit.

### Waarom een VPS en geen NAS of PaaS? (ADR-0002)

24/7-clubdienst voor < € 4 p/m. Een NAS hangt aan je thuisnetwerk (stroomuitval, dynamische IP, security-risico); PaaS-free-tiers slapen in (~15 min) waardoor de eerste vraag 10–30 s duurt.

### Waarom RAG en geen fine-tuning? (ADR-0003)

Regelgeving wisselt elk seizoen; fine-tuning is duur, traag en stilstaand. RAG: nieuw document uploaden = direct bijgewerkt. Het Kenniscentrum blijft de autoriteit voor versies, tarieven en verzekeringen.

### Waarom de websearch-tool aan, maar gescoped? (ADR-0004)

Sommige info (licentiepakketten/tarieven, verzekeringen, wijzigingsmemo's) staat alleen op kenniscentrum.knwu.nl. Open web zou de "eigen documenten + Kenniscentrum"-belofte breken, kosten opdrijven en de eval-set non-deterministisch maken.

### Waarom alleen actuele documenten in de Library? (ADR-0005)

Oude versies in de Library kunnen door retrieval als "huidige regel" geciteerd worden — het strikethrough-probleem vermenigvuldigd. Daarom: Library = actueel alleen, archief in repo, "wat is er veranderd" via de officiële Kenniscentrum-memo.

### Waarom de gelaagde aanpak voor zichtbare revisies?

Er zijn geen schone versies van de regelgevings-PDF's. Doel is niet 100% verwijdering garanderen, maar dat doorgestreepte tekst nooit *stilzwijgend* het antwoord kan worden: opschonen bij ingestie waar mogelijk + harde prompt-regel + expliciete onzekerheidsmelding + cron-versiecheck tegen het Kenniscentrum.

### Waarom B1 standaard met B2-toggle?

De taalniveau-skill legt B1 vast als standaard voor teksten aan leden/ouders; B2 op verzoek; bij B2 altijd een B1-aanbod om te delen met ouders. Een toggle maakt het verzoek zichtbaar zonder magische commando's; kindniveau hoort niet in de chatbot (die praat met ouders, niet met kinderen).

### Kostenmodel in begrijpelijke taal

Per vraag betaal je: vraag-tokens + opgehaalde fragmenten + antwoord (+ websearch/tool-calls). De risico's zijn misbruik (rate limiting) en ongescopeerde tools (daarom websearch gescoped).

---

## Voorgestelde leervolgorde

1. Tutorial stap 1 → 5 (lokaal prototype + eval-set).
2. Eén how-to tegelijk: VPS → embed → misbruik/privacy → versiecheck.
3. Per kwadrant: na het *doen* het *waarom* lezen; eigen reference-docs schrijven.
4. Launch-gate: eval-set ≥90% correct mét bron. Daarna live.
5. Post-MVP: verzettenadvies (How-to F), PWA, learnings-loop uitbouwen.

---

## 🚀 5. Vervolgstappen — webapp, PWA (na de MVP)

1. **Responsive webapp + PWA-manifest + service worker** — leden zetten de bot op hun beginscherm (iOS én Android); geen app store nodig.
2. **Store-apps via Capacitor** — alleen als de club het icoon in de stores zelf belangrijk vindt (Apple $99/jr, Google Play $25 eenmalig + review).
3. **Native app** — niet doen; de chatbot heeft geen native API nodig.
