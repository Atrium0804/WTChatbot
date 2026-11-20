# Bekijk lokale routing-traces

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Volg per bericht de gekozen route, intake, handoffs en tool-aanroepen zonder vraag- of antwoordteksten te loggen.

## Voorwaarden

- De project-venv is geinstalleerd en de app kan lokaal draaien.
- Voor echte agent-antwoorden zijn de gebruikelijke Mistral-instellingen geconfigureerd.
- Gebruik voor het paneel een lokaal ontwikkelproces met een worker, rechtstreeks op loopback, niet achter een proxy.

## Stappen

1. Start vanuit de repo-root in PowerShell:

   ```powershell
   $env:LOCAL_DEBUG_TRACES = "1"
   .\.venv\Scripts\python -m uvicorn main:app --app-dir app --host 127.0.0.1 --port 8000 --log-level info
   ```

2. Open `http://127.0.0.1:8000/debug` en stel in een andere tab via `http://127.0.0.1:8000/` een vraag.

3. Bekijk de nieuwste trace in het paneel of zoek in de terminal naar `chat_trace`. Elke regel bevat een `trace_id`, een event en de verstreken tijd in milliseconden:

   - `route` met `bypass` en reden `regex_lookup`: lokaal antwoord zonder LLM-call.
   - `intake`, gevolgd door `route` met reden `intake_lookup`: lokaal antwoord na een intake-call.
   - `lookup_state` met reden `stale_revision`: de job vulde een onvolledige lookup-vraag aan, maar in dezelfde conversatie kwam intussen een nieuwer bericht. De job publiceert zijn lookup-toestand dan niet; zijn eigen antwoord verandert niet. Zie [Lookup-toestand](../reference/categorieoverzicht.md#lookup-toestand).
   - `route` met `direct-knwu`, `direct-regio`, `direct-club`, `direct-archief` of `direct-verzet`: direct naar een expert. `direct-verzet` zonder intake-call heeft reden `verzet_offer_accepted` (de gebruiker ging positief in op het verzetaanbod) of `verzetadvies_vraag` (fietsgegevens of een vraag om verzetadvies, controle of aanpassing).
   - `route` met `router`: terugval, bijvoorbeeld `http_429`, `low_confidence` of `expert_not_configured`.
   - `agent_request`: de aangevraagde startagent. Bij een bestaand Mistral-gesprek kan een andere agent actief zijn; dit event bewijst niet welke agent antwoordt.
   - `handoff`, `tool_started`, `tool_done` en `agent_output`: metadata uit de stream, voor zover Mistral die events en bekende namen levert.
   - `stream_fallback`: de stream kon niet starten; de app probeert de bestaande niet-streamende route. Tool-events zijn dan niet beschikbaar.
   - `function_call`: de app voerde een function call van de agent uit, bijvoorbeeld `bereken_verzet`. `reason` is `ok`, `invalid_input`, `error` of `limit` (meer dan 3 aanroepen in één beurt). `input` bevat de fietsopbouw (bijvoorbeeld `50/34 11-28 28-622`) en `outcome` de uitkomst (bijvoorbeeld `U15 max 6.7 m: 9.68 m te zwaar`); geboortejaar en geslacht staan er niet in.
   - `done`, `error` of `cancelled`: einde van de verwerking; `elapsed_ms` is de totale duur tot dat event.

   `duration_ms` bij `intake` meet alleen de intake-call. De intake-classificatiezekerheid staat in `confidence`; geboortejaar en leeftijd worden niet opgenomen.

4. Koppel een browserrequest aan de terminal via de responseheader `X-Trace-ID` van `POST /chat`. In het paneel groepeert een gehashte conversatiecode de berichten van hetzelfde gesprek.

5. Haal bij `error` de volledige foutmelding op voordat je de server herstart. Gebruik het job-id uit de `/chat/status/<job-id>`-regels in de terminal:

   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8000/chat/status/<job-id>" | ConvertTo-Json -Depth 5
   ```

   Lees het veld `error`; `reason` in de trace bevat alleen de exceptionklasse. HTTP 200 bij het pollen betekent niet dat de job geslaagd is. Na een herstart zijn de jobs gewist en geeft dit endpoint `Onbekende job.`. Verwijder secrets en persoonsgegevens uit de foutmelding voordat je die deelt.

## Controle

Stel bijvoorbeeld: "In welke leeftijdscategorie rijdt een jongen geboren in 2015?"
Je ziet achtereenvolgens `started`, `route` met `regex_lookup` en `done`, zonder intake- of agent-event.

Terminaltraces werken ook zonder `LOCAL_DEBUG_TRACES`. Het paneel en `/debug/traces` geven standaard 404; ze zijn alleen bereikbaar met de instelling aan, een loopback-client, een hostnaam `localhost`, `127.0.0.1` of `::1` en zonder forwardingheaders. Publiceer deze ontwikkelserver niet via een reverse proxy of tunnel.

Het paneel bewaart maximaal 100 traces met elk de laatste 100 events, alleen in het geheugen van dit proces. Herstarten wist ze. De terminal logt events onafhankelijk van die buffer; eventuele bewaring van terminallogs beheer je zelf. Afgewezen requests, bijvoorbeeld door de app-rate-limit of ongeldige invoer, starten geen trace.

Stop de app en verwijder de instelling uit deze PowerShell-sessie om het paneel weer uit te schakelen:

```powershell
Remove-Item Env:LOCAL_DEBUG_TRACES
```

Voor de volledige agentgeschiedenis aan Mistral-zijde gebruik je de [conversatie-trace bij feedbacktriage](raadpleeg-feedback-voor-triage.md). Lokale bypasses verschijnen niet in die geschiedenis. Zie ook de [uitleg over vraagrouting](../explanation/vraag-routing.md).
