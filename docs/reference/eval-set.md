# Eval-set

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

De eval-set is de launch-gate van de MVP: een vaste set clubvragen met verwacht antwoord en bron. Besloten in wayfinder-ticket [Grilling: eval-set specificeren](https://github.com/Atrium0804/WTChatbot/issues/13) (map #2). Bestanden: `eval/evalset.yaml` (de set), `eval/run_eval.py` (de runner), `eval/last_run.json` (resultaat van de laatste run).

## Schema

| Veld | Type | Verplicht | Betekenis |
| --- | --- | --- | --- |
| `id` | string | ja | Unieke code, bijv. `knwu-verzet-u15` |
| `categorie` | enum | ja | `knwu` \| `regio` \| `club` — bepaalt welke agent de vraag krijgt (tenzij `via: router`) en in welke categoriescore de vraag meetelt |
| `type` | enum | ja | `standaard` \| `websearch` \| `strikethrough` \| `verheldering` |
| `vraag` | string | ja | Typische clubvraag |
| `verwacht_antwoord` | string | ja | Kernfeiten, gescheiden door `;` — moeten allemaal in het B2-antwoord voorkomen. Houd kernfeiten kort (één tot drie woorden of getallen) |
| `bron` | string | ja, behalve bij `verheldering` | Verwachte bron (documentnaam of URL); moet in een `Bron:`-regel van het antwoord staan. Alternatieven scheiden met ` \| ` (één match volstaat) |
| `versiedatum` | string | ja | Verwachte versie/datum van de bron |
| `doorhaal_waarde` | string | nee (alleen `strikethrough`) | Superseded waarde uit de rode revisie; mag NIET in het antwoord voorkomen |
| `niet_in_antwoord` | string | nee | Woorden gescheiden door `;` die NIET in het antwoord mogen staan, bv. termen uit een ongewenste routeringsvraag of overbodige verheldervragen. Zelfde tokenmatching als de kernfeiten |
| `via` | enum | nee | Alleen `router`: de vraag gaat naar de router-agent (`MISTRAL_AGENT_ID`) in plaats van de categorie-agent, dus end-to-end met handoff |
| `beurten` | lijst van strings | nee | Eerdere gebruikersberichten in dezelfde conversatie, vóór `vraag`. De runner stuurt ze in volgorde; alleen het antwoord op `vraag` wordt gecheckt |
| `verwachte_agent` | string | nee | Agent die `vraag` moet beantwoorden (`router-agent` \| `knwu-agent` \| `regio-agent` \| `club-agent`). Vangt een conversatie die na een handoff bij de verkeerde agent blijft hangen |

Huidige verdeling: 27 vragen — 17 knwu, 5 regio, 5 club; 19 standaard, 4 strikethrough, 2 websearch, 2 verheldering. 4 vragen gaan via de router, waarvan 3 met `beurten` en `verwachte_agent` (issue #44).

Bij `type: verheldering` is de vraag expres vaag (bv. "in welke categorie rijdt mijn kind?"); de bot moet dan een wedervraag stellen. De bot stelt één vraag per bericht, dus `verwacht_antwoord` bevat alleen wat in de éérste vraag hoort (bv. `geboortejaar`); met `niet_in_antwoord` controleer je dat er geen overbodige vragen bij staan. De bron-check vervalt, dus `bron` en `versiedatum` zijn daarbij optioneel.

Een test (`tests/test_run_eval.py`, `Run3ReviewTests`) legt per vraag het oordeel uit de handmatige review van eval run 3 vast en controleert dat de evalset met de echte run-3-antwoorden (`tests/fixtures/eval_run3_antwoorden.json`) tot hetzelfde oordeel leidt. Pas je een entry aan, draai dan de tests.

## Meting: "correct mét correcte bron"

Deterministisch, zonder LLM-judge (kosten en non-determinisme):

1. **Bron**: een van de `Bron: ...`-regels van het antwoord bevat na normalisatie (lowercase, alleen letters en cijfers) de `bron` in de evalset, of één van de alternatieven. Locale-segmenten (`/nl_NL/`), `/index.php` en de sessie-parameter `sid` tellen niet mee.
2. **Kernfeiten**: elk token van elk item van `verwacht_antwoord` staat los in het antwoord. Getallen en woorden van maximaal 3 tekens moeten als heel token voorkomen (`5` matcht niet in `15`, `ja` niet in `jaar`); langere woorden als woordbegin (`verzeker` matcht `verzekering`). Getallen worden genormaliseerd: `11.05` = `11:05`, `08:30` = `8.30`, `€ 10,-` = `10,00` = `10`.
3. **Strikethrough**: `doorhaal_waarde` mag niet in het antwoord voorkomen.
4. **Verboden woorden**: geen van de woorden uit `niet_in_antwoord` mag in het antwoord voorkomen; `last_run.json` toont ze onder `verboden_gevonden`.
5. **Verheldering** (`type: verheldering`): de bron-check vervalt; de kernfeiten (de wedervraag) en eventueel `niet_in_antwoord` tellen.
6. **Agent** (alleen met `verwachte_agent`): de agent die het antwoord op `vraag` gaf moet de verwachte agent zijn. De naam komt uit `agent_id` van de `message.output` in de response, vertaald via de `MISTRAL_AGENT_ID*`-variabelen.

Een vraag is "correct mét correcte bron" als alle checks slagen.

Websearch-vragen krijgen 300 s timeout en 3 pogingen, overige vragen 180 s en 2 pogingen. `eval/last_run.json` bevat per vraag het volledige antwoord en een `trace`: per beurt de vraag en de agent(s) die antwoordden.

## Contextregels

Elk bericht krijgt dezelfde contextregels als in productie (`app/context.py`): bij de eerste beurt de datum van vandaag, en bij een geboortejaar uit de jeugdindeling de leeftijdscategorie (weg en veld) en de licentiecategorie. De runner gebruikt de datum van de dag waarop hij draait.

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

Waarden uit `.env` overschrijven gelijknamige shellvariabelen (`load_dotenv(override=True)`), zodat nieuwe agent-ids na `scripts/create_agents.py --apply` direct gelden.

Output: per-vraag resultaat op stdout, volledig resultaat in `eval/last_run.json`, exit-code 0 als de gate gehaald is, anders 1. **Nooit in CI draaien** (geen live API-calls in CI).

## Onderhoud

- De beheerder (zie [operations.md](../operations.md)) runt de eval-set handmatig na elke library-update (seizoenwissel) en bij elke prompt-wijziging.
- Missers (falende vragen) noteert de beheerder als entry in [LEARNINGS.md](../../LEARNINGS.md) met oorzaak en fix.
- Nieuwe vragen worden toegevoegd aan `eval/evalset.yaml`; de set is een door de agent gegenereerd voorstel dat de beheerder reviewt en corrigeert.
