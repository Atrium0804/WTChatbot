# Findings: eval-impact van de nieuwe flow + 4 baseline-vragen (issue #92)

Datum: 2026-11-14. Primaire bronnen: eigen repo — `eval/run_eval.py`, `eval/evalset.yaml`, `eval/last_run.json`, `app/main.py`, `app/context.py`, `app/knwu_categories.py`, `app/mistral_client.py`, `scripts/agents_config.json`, `docs/reference/eval-set.md`; context: resolves van #88 en #91 (architectuur: light intake + deterministische bypass, direct-to-expert, kleine router).

## (a) Spiegelt `eval/run_eval.py` de productie-input — en wat moet mee veranderen?

**Wat nu al gespiegeld wordt.** De runner importeert de app-modules (`eval/run_eval.py:59-62`: `sys.path.insert(app)` + `import context, knwu_categories`) en stuurt elk bericht met exact dezelfde contextregels als de proxy: `context.build_context_lines(message, today, rules, new_conversation=..., language_level=entry.taalniveau)` + `context.add_context(...)` (`run_eval.py:224-231`), met `today = context.today_in_netherlands()` en `rules = knwu_categories.load_rules()` — 1-op-1 dezelfde functies als `app/main.py` in `/chat` (`main.py:206-214`). De context-input spiegelt productie dus volledig.

**Waar de eval nu al afwijkt van productie:**

1. **Agent-selectie.** Productie start élk bericht bij de router-agent (`mistral_client.answer_question(agent_id=config.MISTRAL_AGENT_ID)`, `main.py:156-162`). De eval start direct bij de categorie-agent (`agent_id_for`, `run_eval.py:87-107`), behalve bij `via: router`. De eval spiegelt de router-first entry dus niet — en na #88/#91 (light intake in de app, direct-to-expert bij confidence ≥ 0,8, anders router) wordt dat verschil groter.
2. **API-laag.** De eval heeft eigen request-code (`send_message`, `run_eval.py:148-172`) in plaats van `mistral_client.answer_question` — geen `metadata`, geen `stream: true`, geen `prompt_cache_key`. Als productie die aanzet (#88 besluit 6), moet de eval óf `mistral_client` hergebruiken óf dezelfde velden meesturen, anders meet hij een andere call dan productie.

**Wat mee moet veranderen met de light-model intake + deterministische standaardantwoorden (#91):**

- **Intake-stap toevoegen vóór de conversation.** De eval moet dezelfde light-call doen (1 call `mistral-small-latest`, JSON `{intentie, domein, discipline, geboortejaar/leeftijd, confidence}` — #91 besluit 2) en daraus de route bepalen: `bypass` (lookup, alle data aanwezig) / `direct-to-expert` (confidence ≥ drempel) / `router`. Doet de eval dat niet, dan test hij een flow die in productie niet meer bestaat en is de latency-vergelijking waardeloos.
- **Deterministische bypass nabootsen.** Bij route `bypass` start de eval géén conversation, maar roept dezelfde app-functie aan als productie (template-antwoord uit `knwu_categories.json` met bron+versie+artikel, stijl van `context.category_line` — #91 besluit 4). Check: kernfeiten uit `verwacht_antwoord` blijven gelden; bij B1 géén `Bron:`-regel (bestaande B1-regel past); bij B2 moet het template bron+versie+artikel uit het JSON citeren.
- **Route-assertions in de evalset.** `via: router` en `verwachte_agent` zijn nu handmatige route-hints; na de change moet de evalset de *verwachte* route kunnen assertiven, bv. nieuw veld `verwacht_route: bypass | direct-knwu | router>knwu`. Anders kan een foute intake-route (bv. lookup die tóch naar de router gaat) niet als FAIL worden gevangen.
- **Regex-context blijft** in eval én productie (#91 besluit 3) — bij bypass is het input voor het template, niet voor een LLM.

## (b) Lookup- vs library-vragen in `eval/evalset.yaml` + voorstel 4 baseline-vragen

Van de 28 entries:

- **Lookup-vragen** (deterministisch uit `app/knwu_categories.json`; na #91 direct app-antwoord, 0 LLM-calls): `knwu-categorie-jongen-2013`, `knwu-b1-categorie-jongen-2015`, `knwu-router-geboortejaar-als-vervolg`, `knwu-router-licentie-na-clubvraag`, `knwu-leeftijd-in-jaren-kind-van-6`, `knwu-bronconflict-u17-nieuweling` (categorie uit leeftijd). Na #94 (max-verzet-tabel in `knwu_categories.json`) ook: `knwu-verzet-u15`, `knwu-verzet-u17`. (Oude aanduidingen "categorie 3"/"MU12, VU13" — `context.old_designation_lines` — zijn lookup-candidates maar zitten nu niet in de evalset.)
- **Library-vragen** (RAG `document_library` / websearch via de domeinexperts): alle 5 `regio-*`, 6 `club-*` (contributie, ZMC, vertrouwenspersoon, gedragscode, fiets-kopen, b1-zmc-kosten), en de knwu-vragen over licentiepakketten, verzekering, inschrijfgeld, NK-dispensatie, actuele Titel 20-versie, contact.
- **Verheldering** (2×): agent-gedreven wedervraag, géén lookup.

**Voorgestelde 4 baseline-vragen** (2 lookup, 2 library) voor latency vóór/na de change:

| # | Type | Evalset-id | Vraag (kort) | Verwacht antwoord |
|---|------|-----------|--------------|-------------------|
| 1 | lookup | `knwu-b1-categorie-jongen-2015` | categorie bij geboortejaar 2015, weg 2026 | U12; 2015 |
| 2 | lookup | `knwu-router-licentie-na-clubvraag` | licentie bij geboortejaar 2012 (nu via router = 2 calls) | KNWU Licentie U17; U15 |
| 3 | library (RAG) | `club-contributie-jeugd-2026` | contributie jeugdlid WTC 2026 | 64,50; 50,00; 14,50 |
| 4 | library (websearch) | `knwu-licentie-pakketten` | licentiepakketten KNWU jeugd 2026 + prijzen | Basis; Plus; Premium; 26; 72; 135 |

Alternatieven: `knwu-verzet-u15` als lookup-ná #94; `regio-b1-mnc-starttijden` als tweede library-vraag. Met deze 4 is het snelheidsverschil direct af te lezen: lookup 2 LLM-calls → 0 (plus 1 kleine intake-call), library ~3,2 calls → ~2 (geen return-handoff).

## (c) Kan de eval de route loggen?

**Nu algedeeltelijk:** `trace` in `last_run.json` logt per beurt de agent(s) die antwoordden (`answering_agents`, `run_eval.py:139-146`, vertaalt `agent_id` → naam via de `MISTRAL_AGENT_ID*`-envs) — handoffs verschijnen als extra `message.output`-entries, dus "welke agent(s)" is al zichtbaar in `last_run.json` (bv. 5× knwu-agent bij een websearch-vraag).

**Ontbreekt:**

1. **Timing** — `run_eval.py` meet geen latency (geen `time`-import); alleen timeouts.
2. **Expliciete route** — geen veld dat zegt `bypass` vs `intake→direct-expert` vs `router→expert`; bij bypass is er straks helemaal geen conversation, dus "0 LLM-calls" moet expliciet gelogd worden.
3. **Call-count per beurt** — af te leiden uit het aantal `message.output`-entries, maar niet als getal in de trace.

**Voorstel:** per beurt `time.monotonic()` rond `send_message` → `duur_ms` in de trace; per beurt `llm_calls` = aantal `message.output`-outputs; per entry een `route`-veld (`bypass | direct-<agent> | router→<agent>`) plus de intake-call apart getimed (1 small-call, de nieuwe vaste kostenpost per bericht). In `last_run.json` + summary een aggregatie per route (gemiddelde `duur_ms`, `llm_calls`) — daarmee zijn de 4 baseline-vragen vóór/na de #88/#91-change direct vergelijkbaar.
