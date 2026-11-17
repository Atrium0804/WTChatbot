# Eval-set

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

De eval-set is de launch-gate van de MVP: een vaste set clubvragen met verwacht antwoord en bron. Besloten in wayfinder-ticket [Grilling: eval-set specificeren](https://github.com/Atrium0804/WTChatbot/issues/13) (map #2). Bestanden: `eval/evalset.yaml` (de set), `eval/run_eval.py` (de runner), `eval/last_run.json` (resultaat van de laatste run).

## Schema

Bovenaan `evalset.yaml`, naast de lijst `evalset`:

| Veld | Type | Verplicht | Betekenis |
| --- | --- | --- | --- |
| `peildatum` | datum (`JJJJ-MM-DD`) | ja | De datum waarop de verwachte antwoorden kloppen. De runner (`load_peildatum` in `run_eval.py`) en de offline tests (`tests/test_run_eval.py`) rekenen hiermee in plaats van met de rundatum; `PeildatumTests` faalt als de runner een andere datum gebruikt. Ontbreekt het veld, dan stopt de runner met een `ValueError` |

Per entry in `evalset`:

| Veld | Type | Verplicht | Betekenis |
| --- | --- | --- | --- |
| `id` | string | ja | Unieke code, bijv. `knwu-verzet-u15` |
| `categorie` | enum | ja | `knwu` \| `regio` \| `club` — bepaalt welke agent de vraag krijgt (tenzij `via: router`) en in welke categoriescore de vraag meetelt |
| `type` | enum | ja | `standaard` \| `websearch` \| `strikethrough` \| `verheldering` |
| `taalniveau` | enum | nee | `B1` (default) \| `B2` — het taalniveau dat de runner per bericht in de contextregel injecteert (issue #52); de bron-check geldt bij `B2` en bij een `bypass`-antwoord |
| `vraag` | string | ja | Typische clubvraag |
| `verwacht_antwoord` | string | ja | Kernfeiten, gescheiden door `;` — moeten allemaal in het antwoord voorkomen. Houd kernfeiten kort (één tot drie woorden of getallen) |
| `bron` | string | ja, behalve bij `verheldering` | Verwachte bron (documentnaam of URL); bij `taalniveau: B2` moet die in een `Bron:`-regel van het antwoord staan, bij `B1` mag het antwoord géén `Bron:`-regel bevatten, behalve een `bypass`-antwoord (#102). Alternatieven scheiden met ` \| ` (één match volstaat) |
| `versiedatum` | string | ja | Verwachte versie/datum van de bron |
| `doorhaal_waarde` | string | nee (alleen `strikethrough`) | Superseded waarde uit de rode revisie; mag NIET in het antwoord voorkomen |
| `verwacht_marker` | string | nee | Marker die in de **ruwe agent-output** moet voorkomen, bijv. `[BRONCONFLICT]` (#47). De proxy stript de marker vóór de gebruiker hem ziet, dus in productie-antwoorden is hij weg; de eval-runner draait offline en ziet de ruwe output |
| `niet_in_antwoord` | string | nee | Woorden gescheiden door `;` die NIET in het antwoord mogen staan, bv. termen uit een ongewenste routeringsvraag of overbodige verheldervragen. Zelfde tokenmatching als de kernfeiten |
| `via` | enum | nee | Alleen `router`: de vraag gaat naar de router-agent (`MISTRAL_AGENT_ID`) in plaats van de categorie-agent, dus end-to-end met handoff |
| `verwacht_route` | enum | nee | Assert de productie-route van de app (#92): `bypass` (deterministische lookup, 0 LLM-calls), `direct-<domein>` (direct-to-expert via de light intake) of `router`. Mismatch = FAIL |
| `beurten` | lijst van strings | nee | Eerdere gebruikersberichten in dezelfde conversatie, vóór `vraag`. De runner stuurt ze in volgorde; alleen het antwoord op `vraag` wordt gecheckt |
| `verwachte_agent` | string | nee | Agent die `vraag` moet beantwoorden (`router-agent` \| `knwu-agent` \| `regio-agent` \| `club-agent`). Vangt een conversatie die na een handoff bij de verkeerde agent blijft hangen |

Huidige verdeling: 30 vragen — 19 knwu, 5 regio, 6 club; 21 standaard, 3 strikethrough, 4 websearch, 2 verheldering. 4 vragen gaan via de router, waarvan 3 met `verwachte_agent`; 4 vragen hebben `beurten` (issue #44). Alle entries hebben expliciet `taalniveau: B2`, behalve de 6 B1-vragen (issue #52).

Bij `type: verheldering` is de vraag expres vaag (bv. "in welke categorie rijdt mijn kind?"); de bot moet dan een wedervraag stellen. De bot stelt één vraag per bericht, dus `verwacht_antwoord` bevat alleen wat in de éérste vraag hoort (bv. `geboortejaar`); met `niet_in_antwoord` controleer je dat er geen overbodige vragen bij staan. De bron-check vervalt, dus `bron` en `versiedatum` zijn daarbij optioneel.

Een test (`tests/test_run_eval.py`, `Run3ReviewTests`) legt per vraag het oordeel uit de handmatige review van eval run 3 vast en controleert dat de evalset met de echte run-3-antwoorden (`tests/fixtures/eval_run3_antwoorden.json`) tot hetzelfde oordeel leidt. Pas je een entry aan, draai dan de tests.

## Meting: "correct mét correcte bron"

Deterministisch, zonder LLM-judge (kosten en non-determinisme):

1. **Bron**: bij `taalniveau: B2` moet een van de `Bron: ...`-regels van het antwoord na normalisatie (lowercase, alleen letters en cijfers) de `bron` in de evalset bevatten, of één van de alternatieven. Locale-segmenten (`/nl_NL/`), `/index.php` en de sessie-parameter `sid` tellen niet mee. Bij `taalniveau: B1` (default) moet het antwoord juist géén `Bron:`-regel bevatten, behalve bij route `bypass`: dat overzicht draagt ook bij B1 een bronregel die moet matchen (#102).
2. **Kernfeiten**: elk token van elk item van `verwacht_antwoord` staat los in het antwoord. Getallen en woorden van maximaal 3 tekens moeten als heel token voorkomen (`5` matcht niet in `15`, `ja` niet in `jaar`); langere woorden als woordbegin (`verzeker` matcht `verzekering`). Getallen worden genormaliseerd: `11.05` = `11:05`, `08:30` = `8.30`, `€ 10,-` = `10,00` = `10`.
3. **Strikethrough**: `doorhaal_waarde` mag niet in het antwoord voorkomen.
4. **Verboden woorden**: geen van de woorden uit `niet_in_antwoord` mag in het antwoord voorkomen; `last_run.json` toont ze onder `verboden_gevonden`.
5. **Verheldering** (`type: verheldering`): de bron-check vervalt; de kernfeiten (de wedervraag) en eventueel `niet_in_antwoord` tellen.
6. **Agent** (alleen met `verwachte_agent`): de agent die het antwoord op `vraag` gaf moet de verwachte agent zijn. De naam komt uit `agent_id` van de `message.output` in de response, vertaald via de `MISTRAL_AGENT_ID*`-variabelen.
7. **Route** (alleen met `verwacht_route`, #92): de route die de runner spiegelt uit de app (`bypass` | `direct-<domein>` | `router`) moet gelijk zijn aan `verwacht_route`.

Een vraag is "correct mét correcte bron" als alle checks slagen.

Websearch-vragen krijgen 300 s timeout en 3 pogingen, overige vragen 180 s en 2 pogingen. `eval/last_run.json` bevat per vraag het volledige antwoord, een `trace` (per beurt de vraag, de agent(s) die antwoordden en `duur_ms`), en per vraag `route`, `route_reden` (`regex_lookup` of `intake_lookup` bij een bypass, `via_router` bij `via: router`, anders de trace-reden van de app: `confident_domain`, `low_confidence`, `expert_not_configured` of de reden van een intake-fout), `duur_ms`, `llm_calls` (aantal `message.output`-calls in de laatste beurt; 0 bij `bypass`) en `intake_ms` (de light-intake-call, #91). In de summary staat per route een aggregatie (`per_route`: n, ok, gemiddelde_duur_ms, llm_calls_totaal) — daarmee zijn de 4 baseline-vragen (#92: 2 lookup, 2 library) vóór/na de snelheidsflow direct vergelijkbaar.

## Contextregels

Elk bericht krijgt dezelfde contextregels als in productie (`app/context.py`): per bericht het taalniveau van de entry (`taalniveau`, default B1 — sinds issue #52 de productiestandaard), bij de eerste beurt de datum, bij een geboortejaar uit de jeugdindeling de leeftijdscategorie (weg en veld) en de licentie, en bij een oude aanduiding of kalenderaanduiding ("categorie 3", "MU12, VU13") de nieuwe leeftijdscategorie. Als datum geldt de `peildatum` uit `evalset.yaml`, niet de rundatum; daarmee rekent de runner ook het bypass-antwoord en de seizoenen uit.

## Route spiegelen (#91/#92)

De runner spiegelt de route-beslissing van de app per vraag (`plan_entry` in `run_eval.py`, zelfde operaties als productie — `app/lookups.py` + `app/intake.py`): `beurten` en `vraag` gaan in volgorde door `lookups.recognize_turn`, met de lookup-toestand van de vorige beurt. Is een eerdere beurt een herkende onvolledige vraag, dan vult de runner die net als de app aan met de light intake en `lookups.complete_with_intake`. Is de beslissing voor `vraag` Ready, dan is de route `bypass` (`route_reden: regex_lookup`) en komt het antwoord uit `lookups.render_answer`, zonder conversation te starten; ook bij B1 met één `Bron:`-regel (#102). Anders geldt `via: router` als vaste router-route, en start de runner de light intake (1 call naar `mistral-small-latest`, `MISTRAL_CHAT_COMPLETIONS_URL`/`MISTRAL_INTAKE_MODEL`). `intake.decide_route` kiest dan een intake-ondersteunde bypass (`route_reden: intake_lookup`, alleen voor een herkende onvolledige vraag), direct-to-expert (confidence ≥ `INTAKE_CONFIDENCE_THRESHOLD`, expert-id uit `MISTRAL_AGENT_ID_<DOMEIN>`) of router.

## Gate

| Gate | Eis |
| --- | --- |
| Globaal | ≥ 90% correct mét correcte bron |
| Per categorie (knwu/regio/club) | ≥ 90% |
| Harde gate: `type: strikethrough` en `type: websearch` | 100% — deze mogen nooit falen (acceptance-criterium ADR-0005) |

## Runner

`eval/run_eval.py` draait **offline** tegen dezelfde agents via de Mistral Conversations API (per vraag een nieuwe conversation, zelfde prompt en contextregels als productie) — niet tegen de draaiende bot. Een live smoke-test tegen de gedeployde bot is post-MVP.

```bash
python eval/run_eval.py
```

| Variabele (uit `.env` in de repo-root) | Betekenis |
| --- | --- |
| `MISTRAL_API_KEY` | Verplicht |
| `MISTRAL_AGENT_ID_KNWU` / `_REGIO` / `_CLUB` | Agent per categorie; fallback `MISTRAL_AGENT_ID` |
| `MISTRAL_AGENT_ID` | Router-agent, voor vragen met `via: router` |

Waarden uit de env-file overschrijven gelijknamige shellvariabelen (`load_dotenv(override=True)`), zodat nieuwe agent-ids na `scripts/create_agents.py --apply` direct gelden.

Output: per-vraag resultaat op stdout, volledig resultaat in `eval/last_run.json`, exit-code 0 als de gate gehaald is, anders 1. **Nooit in CI draaien** (geen live API-calls in CI).

## Onderhoud

- De beheerder (zie [operations.md](../operations.md)) runt de eval-set handmatig na elke library-update (seizoenwissel) en bij elke prompt-wijziging.
- Missers (falende vragen) noteert de beheerder als entry in [LEARNINGS.md](../../LEARNINGS.md) met oorzaak en fix.
- Nieuwe vragen worden toegevoegd aan `eval/evalset.yaml`; de set is een door de agent gegenereerd voorstel dat de beheerder reviewt en corrigeert.
- De `peildatum` verandert alleen samen met de seizoensafhankelijke verwachte antwoorden (leeftijdscategorie, seizoen), bijvoorbeeld bij een seizoenwissel.
- Van feedback naar een prompt-wijziging met de eval-gate als controle: zie [how-to: gebruik feedback om prompts te finetunen](../how-to/gebruik-feedback-om-prompts-te-finetunen.md) (issue #55).
