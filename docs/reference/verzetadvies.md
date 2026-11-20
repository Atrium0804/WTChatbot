# Verzetadvies

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Exacte details van het verzetadvies: routes, herkenning, de rekentool `bereken_verzet`, invoergrenzen, voorstellen en configuratie. Het besluit en de afwegingen staan in [ADR-0010](../adr/0010-verzetadvies-verzet-agent-met-rekentool.md); de termen (Verzetadvies, Zwaarste verzet, Bereik, Wielomtrek, ETRTO-bandenmaat, Reguliere cassette, Jeugdcassette) in [GLOSSARY.md](../../GLOSSARY.md). Instellen en controleren: [Zet het verzetadvies aan](../how-to/zet-het-verzetadvies-aan.md).

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `app/verzet_advies.py` | Rekenmodule: `advise()`, invoervalidatie, voorstellen |
| `app/function_calls.py` | Tool-schema `BEREKEN_VERZET_TOOL`, `execute()`, function-call-lus `run_turn()` |
| `app/lookups.py` | `asks_verzetadvies()`, verzetaanbod (`VERZET_OFFER`, `accepted_verzet_offer()`, `verzet_offer_context()`) |
| `app/intake.py` | `route_before_intake()`: route `direct-verzet` zonder intake-call |
| `scripts/prompts/verzet-agent.md` | Prompt: uitvraagvolgorde, antwoordvorm, richtlijnen, Park Tool-links |
| `scripts/architectures/huidig.json` | `verzet-agent`: geen library, geen websearch, `function_tools: ["bereken_verzet"]` |

## Routes

`intake.route_before_intake()` kiest vóór de intake-call. App (`app/main.py`) en eval (`eval/run_eval.py`) gebruiken dezelfde functie.

| Situatie | Route | Trace-reden | Intake-call |
| --- | --- | --- | --- |
| Positief antwoord op het verzetaanbod van het vorige bypass-antwoord | `direct-verzet` | `verzet_offer_accepted` | nee |
| Vraag om verzetadvies (`lookups.asks_verzetadvies`) | `direct-verzet` | `verzetadvies_vraag` | nee |
| Alleen het maximaal toegestane verzet, met complete invoer | `bypass` | `regex_lookup` | nee |
| Intake kiest domein `verzet` met confidence ≥ drempel | `direct-verzet` | `confident_domain` | ja |
| `MISTRAL_AGENT_ID_VERZET` leeg bij een van de eerste twee situaties | job `error` | `RuntimeError` | nee |

Bij `verzet_offer_accepted` start een nieuwe Mistral-conversatie met de bypass-feiten als contextregels (`verzet_offer_context`). Bij `verzetadvies_vraag` loopt een bestaande conversatie door.

## Herkenning van een vraag om verzetadvies

`lookups.asks_verzetadvies(text)` in `app/lookups.py` bevat de exacte patronen; `app/tests/fixtures/routecontract.yaml` legt de voorbeelden vast.

| Bericht | Vraag om verzetadvies | Waarom |
| --- | --- | --- |
| "Mijn fiets heeft 50/34, 11-28 en 25-622" | ja | kettingbladen (32–60 tanden), cassette, ETRTO-maat |
| "Is mijn verzet met 46x12 te zwaar?" | ja | blad × kransje |
| "Welke cassette past?" | ja | onderdeelwoord (kettingblad, voorblad, cassette, tandkrans, kransje, bandenmaat, ETRTO) |
| "ik wil verzetadvies" | ja | "verzetadvies" of "advies … verzet" |
| "ik wil mijn verzet aanpassen" | ja | controleren, nakijken, aanpassen of "te zwaar", samen met verzet, versnelling of tandwiel |
| "Wanneer is de clubwedstrijd op 14/09?" | nee | 14 is geen kettingblad |
| "Welke categorie in seizoen 25/26?" | nee | 25 is geen kettingblad |
| "Is er een controle van de fiets voor de wedstrijd?" | nee | geen verzetwoord |

Een vraag om verzetadvies krijgt nooit een bypass.

## Verzetaanbod

Zie de term **Antwoord op een aanbod** in [GLOSSARY.md](../../GLOSSARY.md).

| Onderdeel | Waarde |
| --- | --- |
| Tekst | "Heb je hulp nodig bij het controleren of aanpassen van het verzet van je fiets?" (`lookups.VERZET_OFFER`) |
| Wanneer | Bypass-antwoord op een vraag die alleen over verzet gaat, met minstens één wegwielrenrij; vervangt dan de slotvraag over de KNWU-documenten |
| Niet bij | Gecombineerde vragen (categorie, licentie), alleen veldrijden |
| Positief antwoord | "ja", "jazeker", "graag", "ok", "oké", "prima", "doe maar", eventueel gevolgd door "graag", "hoor", "alsjeblieft", "bedankt" e.d. (`_POSITIVE_REPLY`) |
| Context naar de agent | Per wegrij: geboortejaar, geslacht, categorie, maximaal toegestaan verzet wegwielrennen, bron, versie en artikel |

## Tool `bereken_verzet`

### Invoer

| Argument | Type | Verplicht | Betekenis |
| --- | --- | --- | --- |
| `birth_year` | integer | ja | Geboortejaar van de renner |
| `gender` | `jongens` \| `meisjes` | ja | Geslacht |
| `chainring` | integer | ja | Tanden van het grootste (of enige) kettingblad |
| `small_chainring` | integer | nee | Tanden van het kleine kettingblad; weglaten bij één blad (1x) |
| `smallest_sprocket` | integer | ja | Tanden van het kleinste tandkransje |
| `largest_sprocket` | integer | ja | Tanden van het grootste tandkransje |
| `tire_width_mm` | integer | ja | Banddikte uit de ETRTO-maat |
| `rim_diameter_mm` | integer | ja | Velgdiameter uit de ETRTO-maat |

Het wedstrijdjaar is het huidige jaar van de app; de agent geeft het niet mee.

### Invoergrenzen

| Invoer | Toegestaan |
| --- | --- |
| Kleinste tandkransje | 9–16T |
| Grootste tandkransje | 23–59T |
| Voorblad (groot en klein) | 32–60T |
| Banddikte | 23–40 mm |
| Velgdiameter | 406, 507, 520, 540, 559, 584 of 622 mm |
| Geboortejaar | binnen de jeugdcategorieën U6 t/m U17 van het wedstrijdjaar |

Daarbuiten geeft de tool `{"error": ...}` met een Nederlandse melding (`invalid_input`).

### Formules

| Grootheid | Formule |
| --- | --- |
| Wielomtrek (mm) | π × (velgdiameter + 2 × banddikte) |
| Verzet (m) | wielomtrek × tanden voorblad / tanden kransje / 1000 |
| Zwaarste verzet | grootste blad / kleinste kransje |
| Lichtste verzet | kleinste blad (of het enige) / grootste kransje |
| Bereik (%) | zwaarste / lichtste verzet × 100, afgerond |
| Topsnelheid (km/u) | zwaarste verzet × 100 omw/min × 60 / 1000 |
| Binnen het maximaal toegestane verzet | zwaarste verzet ≤ maximum (gelijk is toegestaan) |

Het maximaal toegestane verzet komt uit `app/knwu_categories.json` (art. 20.1.007), alleen voor wegwielrennen.

### Voorstellen

| Uitvoerveld | Regel |
| --- | --- |
| `smallest_sprocket_proposal` | Kleinste kransje waarmee het huidige blad binnen het maximum blijft; ontbreekt als dat 17T of meer zou zijn |
| `largest_chainring_proposal` | Grootste blad bij het huidige kleinste kransje; bij 1x een even aantal tanden. Zakt het onder het kleine blad, dan wordt het 1x |
| `regular_cassette_proposals` | Grootste blad met een even aantal tanden bij een reguliere cassette met 11T; 12T alleen als die dichter bij het maximum uitkomt. Een voorstel dat dezelfde configuratie geeft als `smallest_sprocket_proposal` of `largest_chainring_proposal` valt weg |
| `too_light` | Binnen het maximum, maar meer dan één stap (blad of kransje) eronder |

Een voorstel met een blad onder 32T vervalt.

### Uitvoer

`{"discipline": "weg", ...}` met de velden van `VerzetAdvies`: `category`, `limit_m`, `source` (naam, versie, artikel), `wheel_circumference_mm`, `current` (`heaviest_gear_m`, `lightest_gear_m`, `range_percent`, `top_speed_kmh`, `within_limit`), `too_light` en de voorstellen hierboven.

### Limieten

| Limiet | Waarde |
| --- | --- |
| Uitgevoerde calls per beurt | 3 (`MAX_CALLS_PER_TURN`); daarna krijgt elke call een limietfout (`limit`) |
| Rondes per beurt | 6 (`MAX_ROUNDS_PER_TURN`); daarna `TooManyRoundsError` en wordt de conversatie gewist |

## Trace

| Event | Velden |
| --- | --- |
| `route` | `route=direct-verzet`, `reason` uit de routetabel |
| `function_call` | `tool`, `reason` (`ok`, `invalid_input`, `error`, `limit`), `input` (bijv. `50/34 11-28 28-622`), `outcome` (bijv. `U15 max 6.7 m: 9.68 m te zwaar`); zonder geboortejaar en geslacht |

Fase in `/chat/status` tijdens een call: "Ik bereken je verzet…".

## Configuratie

| Variabele | Gebruik |
| --- | --- |
| `MISTRAL_AGENT_ID_VERZET` | Id van de `verzet-agent`; verplicht voor de routes `verzet_offer_accepted` en `verzetadvies_vraag`, in app en eval |
