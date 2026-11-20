# Zet het verzetadvies aan

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Maak de verzet-agent aan, koppel hem aan de app en controleer dat verzetvragen bij die agent uitkomen. Details van routes en rekentool: [Verzetadvies](../reference/verzetadvies.md); het besluit: [ADR-0010](../adr/0010-verzetadvies-verzet-agent-met-rekentool.md).

## Voorwaarden

- De project-venv is geïnstalleerd en `MISTRAL_API_KEY` staat in `.env`.
- `scripts/architectures/huidig.json` (of de actieve variant) bevat de `verzet-agent` met `function_tools: ["bereken_verzet"]`.

## Stappen

1. Maak of update de agents, zoals in [Productie-agents aanmaken of updaten](maak-of-update-productie-agents.md):

   ```powershell
   .\.venv\Scripts\python scripts\create_agents.py
   .\.venv\Scripts\python scripts\create_agents.py --apply
   ```

   De router-, knwu-, regio- en club-agent krijgen een handoff naar de verzet-agent; draai het script dus ook na een wijziging in hun prompts.

2. Zet het id van de `verzet-agent` uit de summary in `.env` als `MISTRAL_AGENT_ID_VERZET`.

3. Herstart de app; die leest `.env` alleen bij het starten. Zonder dit id faalt elke vraag om verzetadvies en elk aangenomen verzetaanbod met een foutmelding die `MISTRAL_AGENT_ID_VERZET` noemt.

4. Start de app met lokale traces, zoals in [Lokale routing-traces bekijken](bekijk-lokale-routing-traces.md):

   ```powershell
   $env:LOCAL_DEBUG_TRACES = "1"
   .\.venv\Scripts\python -m uvicorn main:app --app-dir app --host 127.0.0.1 --port 8000 --log-level info
   ```

## Controle

Stel deze vragen via `http://127.0.0.1:8000/` en bekijk de traces in `http://127.0.0.1:8000/debug`:

| Vraag | Verwacht |
| --- | --- |
| "ik wil mijn verzet aanpassen" | `route` `direct-verzet` met reden `verzetadvies_vraag`, geen `intake`-event |
| "Wat is het maximale verzet voor een jongen geboren in 2013?" | Bypass-antwoord dat eindigt met "Heb je hulp nodig bij het controleren of aanpassen van het verzet van je fiets?" |
| Daarna "ja" | `route` `direct-verzet` met reden `verzet_offer_accepted`; de agent vraagt niet opnieuw naar geboortejaar of geslacht |
| "50/34, 11-28 en 28-622" als antwoord op de agent | `function_call` met `tool` `bereken_verzet` en `reason` `ok` |

Draai daarna de eval-set met dezelfde `.env`; de `verzet-*`-entries verwachten route `direct-verzet` (zie [Eval-set](../reference/eval-set.md)):

```powershell
.\.venv\Scripts\python eval\run_eval.py
```
