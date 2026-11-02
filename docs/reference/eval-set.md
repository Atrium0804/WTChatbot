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
| `verwacht_antwoord` | string | ja | Kernfeiten, gescheiden door `;` — moeten allemaal in het B2-antwoord voorkomen |
| `bron` | string | ja | Verwachte bron (documentnaam of URL); moet in de `Bron:`-regel van het antwoord staan |
| `versiedatum` | string | ja | Verwachte versie/datum van de bron |
| `doorhaal_waarde` | string | nee (alleen `strikethrough`) | Superseded waarde uit de rode revisie; mag NIET in het antwoord voorkomen |

Huidige verdeling: 20 vragen — 10 knwu, 5 regio, 5 club; 13 standaard, 5 strikethrough, 2 websearch.

## Meting: "correct mét correcte bron"

Deterministisch, zonder LLM-judge (kosten en non-determinisme):

1. **Bron**: de laatste `Bron: ...`-regel van het antwoord matcht na normalisatie (lowercase, komma/punt, URL zonder protocol/query) de `bron` in de evalset.
2. **Kernfeiten**: elk item van `verwacht_antwoord` komt voor in het antwoord (zelfde normalisatie).
3. **Strikethrough**: `doorhaal_waarde` mag niet in het antwoord voorkomen.

Een vraag is "correct mét correcte bron" als alle drie de checks slagen.

## Gate

| Gate | Eis |
| --- | --- |
| Globaal | ≥ 90% correct mét correcte bron |
| Per categorie (knwu/regio/club) | ≥ 90% |
| Harde gate: `type: strikethrough` en `type: websearch` | 100% — deze mogen nooit falen (acceptance-criterium ADR-0005) |

## Runner

`eval/run_eval.py` draait **offline** tegen dezelfde agents via de Mistral Conversations API (per vraag een nieuwe conversation, zelfde prompt als productie) — niet tegen de draaiende bot. Een live smoke-test tegen de gedeployde bot is post-MVP.

```bash
pip install requests pyyaml
MISTRAL_API_KEY=... MISTRAL_AGENT_ID_KNWU=... MISTRAL_AGENT_ID_REGIO=... MISTRAL_AGENT_ID_CLUB=... \
  python eval/run_eval.py
```

Output: per-vraag resultaat op stdout, volledig resultaat in `eval/last_run.json`, exit-code 0 als de gate gehaald is, anders 1. **Nooit in CI draaien** (geen live API-calls in CI).

## Onderhoud

- De beheerder (zie [operations.md](../operations.md)) runt de eval-set handmatig na elke library-update (seizoenwissel) en bij elke prompt-wijziging.
- Missers (falende vragen) noteert de beheerder als entry in [LEARNINGS.md](../../LEARNINGS.md) met oorzaak en fix.
- Nieuwe vragen worden toegevoegd aan `eval/evalset.yaml`; de set is een door de agent gegenereerd voorstel dat de beheerder reviewt en corrigeert.
