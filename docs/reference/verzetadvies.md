# Verzetadvies

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Exacte details van het verzetadvies: routes, herkenning, de rekentool `bereken_verzet`, invoergrenzen, adviezen en configuratie. Het besluit en de afwegingen staan in [ADR-0010](../adr/0010-verzetadvies-verzet-agent-met-rekentool.md); de termen (Verzetadvies, Kettingblad, Optimale configuratie, Kettingbladadvies, Cassetteadvies, Reguliere-cassetteadvies, Zwaarste verzet, Bereik, Wielomtrek, ETRTO-bandenmaat, Reguliere cassette, Jeugdcassette) in [GLOSSARY.md](../../GLOSSARY.md). Instellen en controleren: [Zet het verzetadvies aan](../how-to/zet-het-verzetadvies-aan.md).

## Bestanden

| Bestand | Inhoud |
| --- | --- |
| `app/verzet_advies.py` | Rekenmodule: `advise()`, invoervalidatie, adviezen |
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
| `chainring` | integer | ja | Tanden van het buitenblad (of het enige kettingblad) |
| `small_chainring` | integer | nee | Tanden van het binnenblad; weglaten bij één kettingblad (1x) |
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
| Kettingblad (buiten- en binnenblad) | 28–60T |
| Banddikte | 23–40 mm |
| Velgdiameter | 406, 507, 520, 540, 559, 584 of 622 mm |
| Geboortejaar | binnen de jeugdcategorieën U6 t/m U17 van het wedstrijdjaar |

Daarbuiten geeft de tool `{"error": ...}` met een Nederlandse melding (`invalid_input`).

### Formules

| Grootheid | Formule |
| --- | --- |
| Wielomtrek (mm) | π × (velgdiameter + 2 × banddikte) |
| Verzet (m) | wielomtrek × tanden kettingblad / tanden kransje / 1000 |
| Zwaarste verzet | buitenblad (of het enige) / kleinste kransje |
| Lichtste verzet | binnenblad (of het enige) / grootste kransje |
| Bereik (%) | zwaarste / lichtste verzet × 100, afgerond |
| Topsnelheid (km/u) | zwaarste verzet × 100 omw/min × 60 / 1000 |
| Binnen het maximaal toegestane verzet | zwaarste verzet ≤ maximum (gelijk is toegestaan) |

Het maximaal toegestane verzet komt uit `app/knwu_categories.json` (art. 20.1.007), alleen voor wegwielrennen.

### Adviezen

*Opt* is het grootste toegestane kettingblad bij een kransje (oneven mag). Geldige kleinste kransjes voor een nieuwe cassette: 11–16T (`VALID_SPROCKETS`).

De tool berekent drie configuraties en geeft ze in de lijst `advices`, op volgorde van `number`. Het nummer en de titel volgen uit wat er verandert, niet uit de berekening:

| `number` | `title` | Wat verandert |
| --- | --- | --- |
| 1 | Kettingblad aanpassen | Het kettingblad; de cassette blijft |
| 2 | Cassette wijzigen | De cassette; het kettingblad blijft (of alleen het binnenblad) |
| 3 | Cassette en kettingblad (1x) wijzigen | Kettingblad en cassette |

De drie berekeningen:

| Berekening | Regel |
| --- | --- |
| Kettingbladadvies | Bij het huidige kleinste kransje. 1x: *opt* afgerond naar beneden op even. Twee bladen: *opt* > binnenblad → nieuw buitenblad *opt*; *opt* = binnenblad → buitenblad eraf, 1x op het binnenblad; *opt* < binnenblad → geen configuratie (het reguliere-cassetteadvies geeft dan de 1x-configuratie) |
| Cassetteadvies | Kleinste kransje uit 11–16T waarmee het huidige blad binnen het maximum blijft. Bij twee bladen eerst het buitenblad; past dat bij geen kransje, dan het binnenblad zonder buitenblad. Het grootste kransje blijft gelijk |
| Reguliere-cassetteadvies | 1x met 11T of 12T en *opt* afgerond naar beneden op even, minstens 30T; het verzet dat het dichtst bij het maximum ligt, bij gelijke stand 11T. Vervalt als het kettingblad- of cassetteadvies al 11T of 12T heeft. Is het huidige kleinste kransje al dat kransje, dan verandert alleen het kettingblad en wordt het advies 1 (bijv. U12, 50/40 met 11-25 → 30T met 11-25) |

`too_light`: binnen het maximum, maar meer dan één stap (blad of kransje) eronder.

Voor alle adviezen geldt:

| Regel | Waarde |
| --- | --- |
| Kleinste nieuwe kettingblad | 30T (`MIN_ADVISED_CHAINRING`); een configuratie met een kleiner nieuw blad vervalt |
| Dubbel advies | Een configuratie gelijk aan de huidige, of met dezelfde configuratie of hetzelfde nummer als een eerdere berekening, vervalt |

Elk advies heeft deze velden:

| Veld | Betekenis |
| --- | --- |
| `number`, `title` | Uit wat er verandert (`ADVICE_TITLES`) |
| `result` | Dezelfde velden als `current` |
| `chainring_status` | `huidig`, `aangepast` of `binnenblad` (het huidige binnenblad wordt het enige kettingblad) |
| `cassette_status` | `huidig` of `aangepast` |
| `removes_outer_chainring` | Het buitenblad gaat eraf; het binnenblad wordt het enige kettingblad |
| `replaces_both_chainrings` | Twee kettingbladen worden één nieuw kettingblad |
| `single_sprocket_swap` | Het kleinste kransje wijkt precies 1 tand af van het huidige |
| `chain_may_be_too_short` | Grootste blad + grootste kransje is groter dan nu |

De agent toont de adviezen alleen bij een te zwaar verzet of bij `too_light`.

### Uitvoer

`{"discipline": "weg", ...}` met de velden van `VerzetAdvies`: `category`, `limit_m`, `source` (naam, versie, artikel), `wheel_circumference_mm`, `current`, `too_light` en `advices` (hierboven). `current` en `result` van elk advies hebben dezelfde velden: `setup`, `heaviest_gear_m`, `lightest_gear_m`, `range_percent`, `with_34t` (dezelfde configuratie met 34T als grootste kransje, `COMMON_LARGEST_SPROCKET`: `cassette`, bijv. `"15-34"`, `range_percent` en `tip`, de zin die de agent letterlijk overneemt, bijv. "Met een 15-34 in plaats van een 15-25 wordt het bereik 227% in plaats van 167%; het zwaarste verzet blijft gelijk."; `null` als het grootste kransje al 34T of groter is), `top_speed_kmh` en `within_limit`.

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
