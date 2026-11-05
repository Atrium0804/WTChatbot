# Eval-set

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

De eval-set is de launch-gate van de MVP: een vaste set clubvragen met verwacht antwoord en bron. Besloten in wayfinder-ticket [Grilling: eval-set specificeren](https://github.com/Atrium0804/WTChatbot/issues/13) (map #2). Bestanden: `eval/evalset.yaml` (de set), `eval/run_eval.py` (de runner), `eval/last_run.json` (resultaat van de laatste run).

## Schema

| Veld | Type | Verplicht | Betekenis |
| --- | --- | --- | --- |
| `id` | string | ja | Unieke code, bijv. `knwu-verzet-u15` |
| `categorie` | enum | ja | `knwu` \| `regio` \| `club` — bepaalt welke agent de vraag krijgt |
| `type` | enum | ja | `standaard` \| `websearch` \| `strikethrough` |
| `vraag` | string | ja | Typische clubvraag |
| `verwacht_antwoord` | string | ja | Kernfeiten, gescheiden door `;` — moeten allemaal in het B2-antwoord voorkomen. Houd kernfeiten kort (één tot drie woorden of getallen) |
| `bron` | string | ja | Verwachte bron (documentnaam of URL); moet in een `Bron:`-regel van het antwoord staan. Alternatieven scheiden met ` \| ` (één match volstaat) |
| `versiedatum` | string | ja | Verwachte versie/datum van de bron |
| `doorhaal_waarde` | string | nee (alleen `strikethrough`) | Superseded waarde uit de rode revisie; mag NIET in het antwoord voorkomen |

Huidige verdeling: 20 vragen — 10 knwu, 5 regio, 5 club; 14 standaard, 4 strikethrough, 2 websearch.

Een test (`tests/test_run_eval.py`, `Run3ReviewTests`) legt per vraag het oordeel uit de handmatige review van eval run 3 vast en controleert dat de evalset met de echte run-3-antwoorden (`tests/fixtures/eval_run3_antwoorden.json`) tot hetzelfde oordeel leidt. Pas je een entry aan, draai dan de tests.

## Meting: "correct mét correcte bron"

Deterministisch, zonder LLM-judge (kosten en non-determinisme):

1. **Bron**: een van de `Bron: ...`-regels van het antwoord bevat na normalisatie (lowercase, alleen letters en cijfers) de `bron` in de evalset, of één van de alternatieven. Locale-segmenten (`/nl_NL/`), `/index.php` en de sessie-parameter `sid` tellen niet mee.
2. **Kernfeiten**: elk token van elk item van `verwacht_antwoord` staat los in het antwoord. Getallen en woorden van maximaal 3 tekens moeten als heel token voorkomen (`5` matcht niet in `15`, `ja` niet in `jaar`); langere woorden als woordbegin (`verzeker` matcht `verzekering`). Getallen worden genormaliseerd: `11.05` = `11:05`, `08:30` = `8.30`, `€ 10,-` = `10,00` = `10`.
3. **Strikethrough**: `doorhaal_waarde` mag niet in het antwoord voorkomen.

Een vraag is "correct mét correcte bron" als alle drie de checks slagen.

Websearch-vragen krijgen 300 s timeout en 3 pogingen, overige vragen 180 s en 2 pogingen. `eval/last_run.json` bevat per vraag het volledige antwoord.

## Gate

| Gate | Eis |
| --- | --- |
| Globaal | ≥ 90% correct mét correcte bron |
| Per categorie (knwu/regio/club) | ≥ 90% |
| Harde gate: `type: strikethrough` en `type: websearch` | 100% — deze mogen nooit falen (acceptance-criterium ADR-0005) |

## Runner

`eval/run_eval.py` draait **offline** tegen dezelfde agents via de Mistral Conversations API (per vraag een nieuwe conversation, zelfde prompt als productie) — niet tegen de draaiende bot. Een live smoke-test tegen de gedeployde bot is post-MVP.

```bash
python eval/run_eval.py
```

| Variabele (uit `.env` in de repo-root) | Betekenis |
| --- | --- |
| `MISTRAL_API_KEY` | Verplicht |
| `MISTRAL_AGENT_ID_KNWU` / `_REGIO` / `_CLUB` | Agent per categorie; fallback `MISTRAL_AGENT_ID` |

Waarden uit `.env` overschrijven gelijknamige shellvariabelen (`load_dotenv(override=True)`), zodat nieuwe agent-ids na `scripts/create_agents.py --apply` direct gelden.

Output: per-vraag resultaat op stdout, volledig resultaat in `eval/last_run.json`, exit-code 0 als de gate gehaald is, anders 1. **Nooit in CI draaien** (geen live API-calls in CI).

## Onderhoud

- De beheerder (zie [operations.md](../operations.md)) runt de eval-set handmatig na elke library-update (seizoenwissel) en bij elke prompt-wijziging.
- Missers (falende vragen) noteert de beheerder als entry in [LEARNINGS.md](../../LEARNINGS.md) met oorzaak en fix.
- Nieuwe vragen worden toegevoegd aan `eval/evalset.yaml`; de set is een door de agent gegenereerd voorstel dat de beheerder reviewt en corrigeert.
