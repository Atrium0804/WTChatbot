---
# Metadata voor agents (frontmatter — lees dit eerst)
type: eval-vergelijking          #artefact uit eval/, geen Diátaxis-doc
status: gereviewd (large-fails)  #jouw [!important]-annotaties bij de large-fails zijn leidend
doel: modelkeuze (large vs medium) onderbouwen + actielijst uit review van falende vragen
inputs:                          #hier wordt dit document uit gegenereerd
  - eval/last_run - large.json
  - eval/last_run - medium.json
  - eval/evalset.yaml             #definities van vragen, kernfeiten, doorhaalwaarden
bron_van_waarheid: eval/run_eval.py + eval/evalset.yaml  #bij conflicten wint de runner/evalset, niet dit md
update_trigger:                 #wanneer dit document opnieuw genereren
  - na elke nieuwe eval-run (nieuwe `last_run - *.json`)
  - na een wijziging in evalset.yaml (kernfeiten/doorhaalwaarden/niet_in_antwoord)
  - na een prompt-wijziging in scripts/prompts/ die de resultaten raakt
behouden_bij_update:             #deze secties moeten bij regenereren intact blijven
  - alle `> [!important]`-reviewblokken (per vraag-id)
  - sectie "Benodigde wijzigingen" (pas aan als de review wijzigt)
samenhangende_docs:
  - docs/reference/eval-set.md   #hoe de eval-set werkt (kernfeiten, doorhaalwaarde, beurten)
  - eval/run_eval.py              #de runner (checker-logica)
  - scripts/prompts/knwu-agent.md #prompt van de knwu-agent
---

# Vergelijking eval-runs: large vs medium

Vergelijking van `eval/last_run - large.json` en `eval/last_run - medium.json` (zelfde evalset, 33 vragen). Gegenereerd op 2026-11-12.

## Dit document actualiseren

Gebruik de onderstaande prompt (kopieerbaar) om dit document te regenereren vanuit de JSON-runs:

```
Actualiseer eval/last_run - large vs medium.md vanuit de bronbestanden.

Stappen:
1. Lees eval/last_run - large.json en eval/last_run - medium.json (beide: summary + resultaten[]).
2. Lees het huidige eval/last_run - large vs medium.md en verzamel ALLE bestaande
   `> [!important]`-reviewblokken, gekeyed op vraag-id (de `### \`<id>\``-sectie waar ze in staan).
3. Genereer het document opnieuw met dezelfde secties: Samenvatting (tabellen per metriek,
   per categorie, harde gate), Per-vraag aflepeling (alle 33 ids, winnaar bij verschil),
   Falende vragen per run (per fail: vraag, verwacht_antwoord, missende_kernfeiten,
   doorhaal_waarde + gevonden-flag, niet_in_antwoord/verboden_gevonden, bron_ok +
   bron_gevonden, agent_ok + agents_laatste_beurt, en het volledige `antwoord` in een
   <details>-blok), Bevindingen/patronen.
4. Plaats elk Bewaard reviewblok onder de juiste vraag-id in de sectie van de run
   waarin die vraag faalt (large-fails onder LARGE, etc.). Als een id in de nieuwe run
   niet meer faalt, verplaats het reviewblok naar een sectie "Reviewgeschiedenis" onderaan
   (niet weggooien).
5. Werk "Gegenereerd op" bij naar vandaag. Behoud de frontmatter en de sectie
   "Benodigde wijzigingen" ongewijzigd tenzij de review is aangepast.
6. Schrijf het resultaat naar eval/last_run - large vs medium.md.

Regels: neem vraag/antwoord/bron-teksten letterlijk over uit de JSON (geen parafrase);
houd de tabelstructuur en <details>-blokken aan; geen emoji's.
```

## Samenvatting

| Metriek | large | medium | verschil |
|---|---|---|---|
| Totaal OK | **24/33 (72.7%)** | 17/33 (51.5%) | **+7 vragen, +21.2 procentpunt** |
| club | 6/6 (100.0%) | 6/6 (100.0%) | +0 vragen |
| knwu | 15/21 (71.4%) | 9/21 (42.9%) | +6 vragen |
| regio | 3/6 (50.0%) | 2/6 (33.3%) | +1 vragen |
| Harde gate (strikethrough, websearch) | 3/7 — gate niet gehaald | 0/7 — gate niet gehaald | +3 |

Large scoort **1.4× zoveel** goede antwoorden als medium (24 vs 17). Het verschil zit vrijwel volledig in categorie **knwu** — precies de categorie die door `scripts/prompts/knwu-agent.md` wordt aangestuurd (websearch naar het Kenniscentrum, strikethrough-waarden, router/verheldering). Bij `club` is er geen verschil; de harde gate faalt in beide runs.

## Per-vraag aflepeling (13 van 33 vragen scoren verschillend)

| vraag | large | medium | winnaar |
|---|---|---|---|
| `knwu-actuele-versie-titel20` | ok | FALEN | **large** |
| `knwu-b1-verzet-u15` | ok | FALEN | **large** |
| `knwu-categorie-jongen-2013` | ok | FALEN | **large** |
| `knwu-categorie-meisje-2015` | ok | FALEN | **large** |
| `knwu-licentie-u13-geen-pakketten` | ok | FALEN | **large** |
| `knwu-nk-dispensatie-u10` | ok | FALEN | **large** |
| `knwu-router-verzet-na-regiovraag` | FALEN | ok | **medium** |
| `knwu-verheldering-categorie-via-router` | FALEN | ok | **medium** |
| `knwu-verzekering-dekking` | ok | FALEN | **large** |
| `knwu-wijziging-nationale-besluiten` | ok | FALEN | **large** |
| `regio-b1-mnc-starttijden` | ok | FALEN | **large** |
| `regio-hvh-kalender-2026` | FALEN | ok | **medium** |
| `regio-mnc-veldrijden-starttijden` | ok | FALEN | **large** |

Vragen die in **beide** runs falen: `knwu-licentie-pakketten`, `knwu-verzet-u11`, `knwu-verzet-u15`, `knwu-verzet-u17`, `regio-juiste-knwu-regio`, `regio-nk-kwalificatie`

## Falende vragen in LARGE (9)

### `knwu-licentie-pakketten` — categorie `knwu`, type `websearch`, taalniveau `B2`

- **Vraag:** Welke licentiepakketten kent de KNWU voor jeugd in 2026 en wat kost elk pakket?
- **Verwacht antwoord (kernfeiten):** Basis; Plus; Premium; 26; 72; 135; startrecht; internationa; verzeker
- **Missende kernfeiten:** `startrecht`
- **Bron ok:** True (verwachte bron: `kenniscentrum.knwu.nl/knwu-licenties`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent', 'knwu-agent', 'knwu-agent', 'knwu-agent', 'knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21 (art. 20.0.002, 20.0.003); Nationale_Besluiten_20260918.md, versie 2026-09-18 (art. 1.4, 18.1); https://kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13, geraadpleegd op 2026-11-12; https://kenniscentrum.knwu.nl/knwu-licenties/knwu-wedstrijdlicentie-u17, geraadpleegd op 2026-11-12; https://kenniscentrum.knwu.nl/algemeen/tarieven-knwu, geraadpleegd op 2026-11-12

> [!important]
>
> Dit antwoord is goed. Er worrt genoemd welke wedstrijden je mag rijden (startrecht)

<details><summary>Gegeven antwoord (volledig)</summary>

```
In 2026 kent de KNWU voor de jeugd twee licenties, bepaald door het geboortejaar (Titel 20, art. 20.0.002): de **KNWU Licentie U13** (5 t/m 12 jaar, leeftijdscategorieën U6 t/m U13) en de **KNWU Licentie U17** (13 t/m 16 jaar, U14 t/m U17, inclusief de nieuwelingen van 15 en 16 jaar). Alleen de U17-licentie kent pakketten; de U13-licentie kent één variant. Een licentie is geldig per kalenderjaar en loopt tot en met 31 december (Nationale Besluiten, art. 1.4); het KNWU-lidmaatschap is verplicht voor licentiehouders (Titel 20, art. 20.0.003) en staat los van de licentiekosten. Wil een renner alleen trainen, dan volstaat het KNWU-lidmaatschap.

De pakketten en kosten voor 2026 (tarievenlijst 2026, versie 12-01-2026):

- **KNWU Licentie U13 – € 26**: één licentie zonder pakketkeuze; hiermee kun je alle wedstrijden rijden: club-, regionale, nationale en internationale wedstrijden, plus NK/EK/WK mits gekwalificeerd. Voor regionale wedstrijden kun je ook een daglicentie gebruiken.
- **KNWU Licentie U17 – basispakket – € 26**: deelname aan regionale wedstrijden (clubparcoursen), verzekerd bij deelname, digitale licentiepas.
- **KNWU Licentie U17 – pluspakket – € 72**: additionally nationale wedstrijden, nationale kampioenschappen (mits gekwalificeerd) en internationale wedstrijden inclusief UCI-ID; aansprakelijkheidsverzekering in Nederland, België en Duitsland; aanduiding cruiser/challenge; digitale licentiepas.
- **KNWU Licentie U17 – premiumpakket – € 135**: alles van het pluspakket, plus aansprakelijkheidsverzekering voor wedstrijden buiten Nederland, België en Duitsland, een fysieke licentiepas en extra's van partners (onder andere 25% korting op Amacx- en PPEEQQ-producten).

Bij wedstrijden voor basis- en pluslicentiehouders is deelname met een KNWU daglicentie mogelijk, digitaal via MijnKNWU (Nationale Besluiten, art. 1.4). De bedragen staan niet in de Nationale Besluiten zelf; art. 18.1 verwijst daarvoor naar de tarievenlijst op het KNWU Kenniscentrum.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21 (art. 20.0.002, 20.0.003); Nationale_Besluiten_20260918.md, versie 2026-09-18 (art. 1.4, 18.1)
Bron: https://kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13, geraadpleegd op 2026-11-12
Bron: https://kenniscentrum.knwu.nl/knwu-licenties/knwu-wedstrijdlicentie-u17, geraadpleegd op 2026-11-12
Bron: https://kenniscentrum.knwu.nl/algemeen/tarieven-knwu, geraadpleegd op 2026-11-12

Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/knwu-licenties — 2026
```

</details>


### `knwu-verzet-u15` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 6,70; U15; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `6,55` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent', 'knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

> [!important]
>
> Dit antwoord is goed, er wordt verwezen naar het artikel 20.1.007, (maar dat staat niet in de bronvermelding wat wenselijk is i.v.m. overzichtelijkheid)
>
> Het antwoord bevat wel irrelevante informatie dan nodig (hoe meet je het, buitenland)

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor jongens U15 bij wegwielrennen is **6,70 meter** per omwenteling van de trapas (art. 20.1.007, Titel 20).

Hoe het verzet wordt bepaald: deel het aantal tanden van het grootste voorblad door het aantal tanden van het kleinste bruikbare achtertandwiel en vermenigvuldig de uitkomst met de omtrek van het achterwiel met opgepompte band (art. 20.1.008). Maximaliseren door beperking van het schakelbereik of de achterderailleur is niet toegestaan. Bij een te hoog verzet vóór de wedstrijd krijgt de renner één keer de gelegenheid dit te herstellen; na de wedstrijd volgt diskwalificatie (art. 20.1.009). In het buitenland kunnen andere verzetten gelden. Dit geldt niet als de renner met dispensatie in een andere leeftijdscategorie rijdt.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-verzet-u11` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Wat is het maximaal toegestane verzet voor jongens U11 bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 5,90; U11; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `5,78` — gevonden in antwoord: **True**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent', 'knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

> [!important]
>
> Dit antwoord is goed, er wordt verwezen naar het artikel 20.1.007, (maar dat staat niet in de bronvermelding wat wenselijk is i.v.m. overzichtelijkheid)
>
> Het antwoord bevat wel irrelevante informatie dan nodig (hoe meet je het, het verschil met baanwielrennen, veldrijden)

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor jongens U11 bij wegwielrennen is **5,90 meter** (art. 20.1.007, Titel 20). Het verzet wordt gemeten als de afstand die de fiets aflegt per omwenteling van de trapas (art. 20.1.008): het aantal tanden van het grootste voorblad gedeeld door het aantal tanden van het kleinste bruikbare achtertandwiel, vermenigvuldigd met de omtrek van het achterwiel met opgepompte band. Ter vergelijking: bij baanwielrennen geldt voor jongens U11 maximaal 5,78 meter; in het veldrijden is het verzet vrij.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-verzet-u17` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Welk maximaal verzet geldt voor U17 (nieuwelingen) bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 7,68; U17; nieuwelingen; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `7,01` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent', 'knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

> [!important]
>
> dit antwoord is goed, alleen irrelevante informatie geleverd. artikelnummer hoort bij bronverwijzing

<details><summary>Gegeven antwoord (volledig)</summary>

```
Voor U17 (Nieuwelingen) geldt bij wegwielrennen een maximaal verzet van **7,68 meter** (gemeten als de afstand die de fiets aflegt per omwenteling van de trapas, art. 20.1.008). Deze waarde is in de huidige versie van Titel 20 gewijzigd (per 05.05.26) en staat in de verzettabel van art. 20.1.007. Ter vergelijking binnen dezelfde tabel: op de baan is het maximum voor U17 7,41 meter en in het veldrijden is het verzet vrij.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-verheldering-categorie-via-router` — categorie `knwu`, type `verheldering`, taalniveau `B1`

- **Vraag:** In welke categorie rijdt mijn zoon?
- **Verwacht antwoord (kernfeiten):** geboortejaar
- **Missende kernfeiten:** `geboortejaar`
- **Verboden woorden (`niet_in_antwoord`):** `agent; geslacht` — gevonden: []
- **Bron ok:** True (verwachte bron: ``)
- **Agent ok:** True (verwacht: `knwu-agent`, laatste beurten: ['router-agent', 'knwu-agent', 'knwu-agent', 'knwu-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
In welk jaar is je zoon geboren? Kies een jaar: 2009 of eerder, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021 of later.
```

> [!important]
>
> Overbodige informatie: vraag gewoon naar het geboorte jaar, geef niet zoveel voorbeelden/geldige waarden, Bij geboortejaar is het evident wat er ingevuld moet worden.Wat wel wenselijk is als er 2-3 mogelijkheden zijn en de keuze minder voor de hand liggen dis: Welke discipline? (veldrijden/wegwielrennen) 

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
—
```

</details>


### `knwu-router-verzet-na-regiovraag` — categorie `knwu`, type `standaard`, taalniveau `B2`

- **Vraag:** Welk verzet mag mijn zoon op de weg rijden? Hij is geboren in 2015.
- **Verwacht antwoord (kernfeiten):** 5,90; U12; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: `knwu-agent`, laatste beurten: ['regio-agent', 'regio-agent', 'knwu-agent', 'knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

> [!important]
>
> verwijder deze vraag uit de eval-set, er zijn voldoende verzet-vragen

<details><summary>Gegeven antwoord (volledig)</summary>

```
Een jongen geboren in **2015** rijdt in 2026 op de weg in de leeftijdscategorie **U12** (jongens) (art. 20.0.004). In die categorie mag hij op de weg maximaal een verzet (de afstand die de fiets aflegt per omwenteling van de trapas) van **5,90 meter** rijden (art. 20.1.007).

Het verzet wordt bepaald volgens art. 20.1.008: het aantal tanden van het grootste voorblad gedeeld door het aantal tanden van het kleinste bruikbare achtertandwiel, vermenigvuldigd met de omtrek van het achterwiel met opgepompte band. Het verzet kunstmatig verhogen door het schakelbereik of de achterderailleur te beperken is niet toegestaan.

Terzijde: in het veldrijden is het verzet vrij — daar geldt geen verzetcontrole in seizoen 2026-2027. Dit maximum van 5,90 meter geldt niet als je zoon met dispensatie in een andere leeftijdscategorie rijdt.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

Wil je dit antwoord ook in begrijpelijk Nederlands (B1)?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `regio-hvh-kalender-2026` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** Wanneer loopt de In Memoriam Hans van den Hengel jeugdcompetitie 2026?
- **Verwacht antwoord (kernfeiten):** 29 maart; 27 september
- **Missende kernfeiten:** `29 maart`, `27 september`
- **Bron ok:** True (verwachte bron: `MNC 2026 Hans vd Hengelcompetitie - wegwielrennen | knwumidden.nl/competities`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['regio-agent', 'regio-agent', 'regio-agent', 'regio-agent'])
- **Gevonden bron:** MNC 2026 Hans vd Hengelcompetitie - wegwielrennen.pdf, versie 2026-11-03

> [!important]
>
> dit antwoord is juist, de logica is aangepast. antwoorden mogen geen datums in het verleden bevatten

<details><summary>Gegeven antwoord (volledig)</summary>

```
De In Memoriam Hans van den Hengel-jeugdcompetitie 2026 is al afgelopen. In mijn bronnen staan voor deze competitie alleen wedstrijddata die vóór vandaag (donderdag 12 november 2026) liggen. Ik vind geen toekomstige wedstrijd in mijn bronnen. Er staat nog geen kalender voor een volgende editie in mijn bronnen; voor de planning daarvan kun je terecht bij het clubsecretariaat van WTC Woerden of op knwumidden.nl.

Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?

Bron: MNC 2026 Hans vd Hengelcompetitie - wegwielrennen.pdf, versie 2026-11-03
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
MNC 2026 Hans vd Hengelcompetitie - wegwielrennen | knwumidden.nl/competities — 2026
```

</details>


### `regio-nk-kwalificatie` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** Hoe kwalificeer je je voor het NK jeugd in regio Midden-Oost?
- **Verwacht antwoord (kernfeiten):** selectieprocedure; nationale wedstrijden; 5; Mijn KNWU; LJT
- **Missende kernfeiten:** `selectieprocedure`, `nationale wedstrijden`, `5`, `Mijn KNWU`, `LJT`
- **Bron ok:** False (verwachte bron: `Nationale_Besluiten_20260918`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['regio-agent', 'knwu-agent', 'knwu-agent', 'knwu-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
Voor welke discipline wil je je kwalificeren: het NK wegwielrennen voor jeugd, of het NK veldrijden voor jeugd?
```

> [!important]
>
> dit antwoord is juist (verhelderingsvraag: vraagde discipline) maar er is geen eindantwoord

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
Nationale_Besluiten_20260918 — 2026
```

</details>


### `regio-juiste-knwu-regio` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** In welke KNWU-regio ligt WTC Woerden (Woerden, Utrecht)?
- **Verwacht antwoord (kernfeiten):** Midden-Oost
- **Missende kernfeiten:** `Midden-Oost`
- **Bron ok:** False (verwachte bron: `knwu.nl/over-knwu/regios | kenniscentrum.knwu.nl`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['regio-agent', 'knwu-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
De knwu-agent pakt deze vraag op: in welke KNWU-regio WTC Woerden (Woerden, Utrecht) valt, is een nationale KNWU-zaak die door de knwu-agent wordt beantwoord.
```

> [!important]
>
> Ik krijg dit antwoord
>
> > Er ging iets mis bij het ophalen van het antwoord. Probeer het opnieuw. (Mistral API timeout na 60s — probeer het opnieuw)

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
knwu.nl/over-knwu/regios | kenniscentrum.knwu.nl — 2026
```

</details>


## Falende vragen in MEDIUM (16)

### `knwu-licentie-pakketten` — categorie `knwu`, type `websearch`, taalniveau `B2`

- **Vraag:** Welke licentiepakketten kent de KNWU voor jeugd in 2026 en wat kost elk pakket?
- **Verwacht antwoord (kernfeiten):** Basis; Plus; Premium; 26; 72; 135; startrecht; internationa; verzeker
- **Missende kernfeiten:** `startrecht`
- **Bron ok:** True (verwachte bron: `kenniscentrum.knwu.nl/knwu-licenties`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** [kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13](https://kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13) en [kenniscentrum.knwu.nl/nl_NL/knwu-licenties/knwu-wedstrijdlicentie-u17](https://kenniscentrum.knwu.nl/nl_NL/knwu-licenties/knwu-wedstrijdlicentie-u17), geraadpleegd op 12 november 2026.

<details><summary>Gegeven antwoord (volledig)</summary>

```
De KNWU kent voor jeugd in 2026 de volgende licentiepakketten en tarieven:

- **KNWU Licentie U13**: één pakket van **€26,-** (dekt alle regionale, nationale, internationale wedstrijden en NK/EK/WK-deelname).
- **KNWU Licentie U17**: drie pakketten:
  - Basis: **€26,-** (alleen regionale wedstrijden)
  - Plus: **€72,-** (regionale, nationale wedstrijden en NK-deelname)
  - Premium: **€135,-** (regionale, nationale, internationale wedstrijden, NK/EK/WK-deelname, extra verzekeringen en goodies)

Bron: [kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13](https://kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13) en [kenniscentrum.knwu.nl/nl_NL/knwu-licenties/knwu-wedstrijdlicentie-u17](https://kenniscentrum.knwu.nl/nl_NL/knwu-licenties/knwu-wedstrijdlicentie-u17), geraadpleegd op 12 november 2026.
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/knwu-licenties — 2026
```

</details>


### `knwu-licentie-u13-geen-pakketten` — categorie `knwu`, type `websearch`, taalniveau `B2`

- **Vraag:** Welke licentie en welk licentiepakket heeft mijn dochter nodig? Ze is geboren in 2016.
- **Verwacht antwoord (kernfeiten):** KNWU Licentie U13; 26
- **Missende kernfeiten:** `26`
- **Verboden woorden (`niet_in_antwoord`):** `72; 135` — gevonden: []
- **Bron ok:** True (verwachte bron: `kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13 | TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21

<details><summary>Gegeven antwoord (volledig)</summary>

```
Een meisje geboren in 2016 heeft in 2026 een **KNWU Licentie U13** en rijdt in leeftijdscategorie **U11 (wegwielrennen)** en **U12 (veldrijden, seizoen 2026-2027)**. Voor de KNWU Licentie U13 is er één variant: de **KNWU Licentie U13** (geen pakketten zoals Basis, Plus of Premium).
Wil zij alleen trainen? Dan volstaat het KNWU-lidmaatschap.

Bron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/knwu-licenties/jeugd-u13 | TITEL_20-Jeugdwielrennen_20260921 — 2026
```

</details>


### `knwu-verzekering-dekking` — categorie `knwu`, type `websearch`, taalniveau `B2`

- **Vraag:** Wat is er verzekerd bij een Basis-licentie versus een Premium-licentie?
- **Verwacht antwoord (kernfeiten):** aansprakelijk; Basis; Premium; wereldwijd
- **Missende kernfeiten:** geen
- **Bron ok:** False (verwachte bron: `kenniscentrum.knwu.nl/verzekeringen`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** [kenniscentrum.knwu.nl/nl_NL/voor-renners/veelgestelde-vragen-nieuwe-structuur](https://kenniscentrum.knwu.nl/nl_NL/voor-renners/veelgestelde-vragen-nieuwe-structuur), geraadpleegd op 12 november 2026

<details><summary>Gegeven antwoord (volledig)</summary>

```
Bij een **Basis-licentie** ben je verzekerd voor aansprakelijkheid tijdens wedstrijden waar je met dit pakket aan mag deelnemen, maar alleen binnen Nederland.

Bij een **Premium-licentie** ben je **wereldwijd** verzekerd voor aansprakelijkheid tijdens wedstrijden, inclusief wedstrijddekking in het buitenland. Daarnaast ontvang je een fysieke licentiepas.

Bron: [kenniscentrum.knwu.nl/nl_NL/voor-renners/veelgestelde-vragen-nieuwe-structuur](https://kenniscentrum.knwu.nl/nl_NL/voor-renners/veelgestelde-vragen-nieuwe-structuur), geraadpleegd op 12 november 2026
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/verzekeringen — 2026
```

</details>


### `knwu-verzet-u15` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 6,70; U15; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `6,55` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor jongens U15 bij wegwielrennen is **6,70 meter** (art. 20.1.007).

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-verzet-u11` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Wat is het maximaal toegestane verzet voor jongens U11 bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 5,90; U11; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `5,78` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor jongens U11 bij wegwielrennen is **5,90 meter** (art. 20.1.007).

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-verzet-u17` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Welk maximaal verzet geldt voor U17 (nieuwelingen) bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 7,68; U17; nieuwelingen; artikel 20.1.007
- **Missende kernfeiten:** `artikel 20.1.007`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `7,01` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor U17 (Nieuwelingen) bij wegwielrennen is **7,68 meter** (art. 20.1.007).

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-nk-dispensatie-u10` — categorie `knwu`, type `strikethrough`, taalniveau `B2`

- **Vraag:** Mag een renner van categorie U10 die dispensatie heeft om in een categorie lager te rijden, meedoen aan het NK?
- **Verwacht antwoord (kernfeiten):** ja; categorie waarvoor; U6 t/m U8; BMX
- **Missende kernfeiten:** `ja`, `categorie waarvoor`, `BMX`
- **Doorhaalwaarde (oude/verkeerde waarde, moet NIET in antwoord):** `niet kwalificeren` — gevonden in antwoord: **False**
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21, art. 20.0.005

<details><summary>Gegeven antwoord (volledig)</summary>

```
Nee, een renner van categorie U10 die dispensatie heeft om in een lagere categorie te rijden, mag **niet** meedoen aan het NK. U6 t/m U8 renners kunnen geen dispensatie krijgen om het NK te rijden, en voor U9 en U10 geldt dat dispensatie om in een lagere categorie te rijden wel is toegestaan, maar **niet** voor deelname aan het NK in die lagere categorie.

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21, art. 20.0.005
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-actuele-versie-titel20` — categorie `knwu`, type `standaard`, taalniveau `B2`

- **Vraag:** Welke versie van Titel 20 Jeugdwielrennen is leidend en waar controleer ik dat?
- **Verwacht antwoord (kernfeiten):** 21-09-2026; kenniscentrum; leidend
- **Missende kernfeiten:** `21-09-2026`
- **Bron ok:** True (verwachte bron: `kenniscentrum.knwu.nl/regelgeving`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** [kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten](https://kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten), geraadpleegd op 12 november 2026

<details><summary>Gegeven antwoord (volledig)</summary>

```
De leidende versie van **Titel 20 Jeugdwielrennen** is de versie van **september 2026**, zoals gepubliceerd op het KNWU Kenniscentrum: [TITEL 20-Jeugd in de wielersport.pdf (versie september 2026)](https://kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten).

Je controleert de actuele versie altijd op: [kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten](https://kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten).

Bron: [kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten](https://kenniscentrum.knwu.nl/regelgeving/reglementen-en-jaarlijkse-besluiten), geraadpleegd op 12 november 2026
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/regelgeving — 2026-09-21
```

</details>


### `knwu-wijziging-nationale-besluiten` — categorie `knwu`, type `standaard`, taalniveau `B2`

- **Vraag:** Wat is er gewijzigd in de Nationale Besluiten 2026 ten opzichte van de vorige versie?
- **Verwacht antwoord (kernfeiten):** geen; wijzigingsmemo; gewijzigd
- **Missende kernfeiten:** `geen`, `wijzigingsmemo`, `gewijzigd`
- **Bron ok:** False (verwachte bron: `kenniscentrum.knwu.nl/regelgeving`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
In de **Nationale Besluiten 2026 (versie 20260918)** zijn de volgende belangrijke wijzigingen doorgevoerd ten opzichte van eerdere versies:

---

**1. Criteriums (Hoofdstuk 2.7)**
- **Premiesprints**:
  - Premiesprints vinden altijd plaats op de finishlijn en worden aangekondigd via microfoon en bel.
  - Een premiesprint mag **niet** plaatsvinden als er nog 1 ronde te gaan is (om verwarring met de laatste ronde te voorkomen).
  - Maximale **25% van de premiesprints** mag op een andere groep dan de kopgroep verreden worden, mits dit duidelijk wordt aangekondigd.
  - Het **reglementair voltooien van de wedstrijd is niet noodzakelijk** om aanspraak te maken op een gewonnen premie tijdens een premiesprint, tenzij dit nadrukkelijk is aangegeven. Premies vervallen wel bij diskwalificatie of sanctie.

- **Leidersprijs**:
  - Iedere ronde wordt 1 punt toegekend aan de renner die als eerste de finish passeert.
  - Om aanspraak te maken op de leidersprijs **moet de renner de wedstrijd reglementair voltooien**.
  - Bij gelijk aantal punten wordt de winnaar bepaald door: winnaar van de laatste sprint, dan klassering in de einduitslag.

- **3-Rondenklassement**:
  - Drie sprints (niet per se opvolgend) tellen mee voor een eigen klassement, aangekondigd via microfoon en bel.
  - Puntenverdeling: 3, 2, 1 voor de eerste drie renners.
  - **Reglementair voltooien van de wedstrijd is niet noodzakelijk** om aanspraak te maken op de premie.
  - Bij gelijk aantal punten wordt de winnaar bepaald door: aantal 1e, 2e, 3e plaatsen in de sprints, dan klassering in de 3e, 2e en 1e sprint.

- **Ronde vergoeding (2.7.4, geïntroduceerd per 26.05.2026)**:
  - Alleen van toepassing op parcoursen **tot 2,8 km** en tot 10 km of 10 ronden voor de finish (afhankelijk van wat later wordt bereikt).
  - Toegekend bij: legitieme val, lekke band, of erkend defect (bijv. gebroken onderdeel dat essentieel is voor veilig voortbewegen).
  - De renner moet zich **zo spoedig mogelijk melden bij de jurywagen** en de official moet het defect goedkeuren.
  - **Na toekenning van een ronde vergoeding mag de renner niet meedingen naar prijzen in de eerstvolgende (premie)sprint.**
  - Bij moedwillig misbruik: diskwalificatie en vervallen van premies.

---

**2. Straffenbarema (Hoofdstuk 12)**
- Het **oude straffenbarema uit Titel 12 is niet meer van toepassing** en vervangen door een **nieuwe sanctietabel die aansluit bij de UCI**.
- **Boetes zijn verlaagd** voor veel overtredingen, bijvoorbeeld:
  - Afwezigheid bij start zonder geldige reden: van **€50–200** naar **€25–100** (renner).
  - Niet aanwezig zijn bij officiële ceremonies: van **€200** naar **€75** (renner) en **€100** (ploegleider).
  - Niet-conforme kleding tijdens podiumverplichtingen: van **€100** naar **€50** (renner en ploegleider).
  - Gebruik van niet-reglementair fietsaccessoire: van **€50 + declassering** naar **waarschuwing + toelichting** (voor jeugd/wedstrijdspecifieke gevallen).

---
**3. Overige wijzigingen**
- **Topcompetitie Mannen**: Wordt **sinds 2025 niet meer verreden**.
- **Topcompetitie Junioren Mannen**: Maximale ploeggrootte is **4–6 renners**, afhankelijk van het aantal aangemelde teams (tot 28 teams: 6 renners; vanaf 29 teams: 5 renners).
- **Ronde vergoeding bij criteriums**: Verplaatst van **2.1.7 naar 2.7.4** (per 26.05.2026).
- **Materiaalwagens**: **Trekhaak is niet toegestaan** uit veiligheidsoverwegingen.
- **Bevoorrading**: Toegestaan vanaf **Junioren** in nationale wedstrijden, mits in een aangewezen zone. De wedstrijdleider kan dit uitbreiden naar andere categorieën.
- **Puntentelling Toekomstcup**: Punten voor de nationale ranglijst (selectie NK’s) worden toegekend volgens **Schema 2** (individueel eindklassement).

---
**4. Baanwielrennen**
- **Daglicentie 17+** is vereist voor deelname aan nationale wedstrijden.
- **Laatste wedstrijd van het seizoen** wordt op **zaterdag** verreden (in plaats van zondag).
- **Cruiser klasse** is heringedeeld na een enquête.
- **Kwalificatie NK**: Methode ‘2de route’ (via nationale en regiowedstrijden) blijft gehandhaafd.

---
**5. Boetes en sancties**
- **Verlaging van boetes** voor veel overtredingen, met name voor jeugd en lagere categorieën (vaak vervangen door **waarschuwing + toelichting**).
- **Uitzonderingen voor jeugd**: Bij overtredingen zoals niet-reglementair accessoire of kleine overtredingen wordt vaker een **waarschuwing** gegeven in plaats van een boete.

---
**6. Algemeen**
- **Digitale lidmaatschapspassen** en **vereenvoudigde licentieaanvragen** zijn geïntroduceerd.
- **Veiligheid en acceptatie**: Maatregelen zoals kortere karavaan en terugbrengen van renners naar de laatste volgauto van de eerstvolgende groep (niet naar oorspronkelijke plaats) zijn genomen om de veiligheid en acceptatie van het wielrennen te verbeteren.

---
**Bron:** Nationale_Besluiten_20260918.md, versie 2026-09-18

---
Wil je een samenvatting van deze wijzigingen in begrijpelijk Nederlands (B1) om te delen met leden of ouders?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
kenniscentrum.knwu.nl/regelgeving — 2026-09-18
```

</details>


### `knwu-categorie-jongen-2013` — categorie `knwu`, type `standaard`, taalniveau `B2`

- **Vraag:** In welke leeftijdscategorie rijdt een jongen geboren in 2013 bij wegwielrennen in 2026?
- **Verwacht antwoord (kernfeiten):** U14; 2013; artikel 20.0.004
- **Missende kernfeiten:** `artikel 20.0.004`
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21, art. 20.0.004

<details><summary>Gegeven antwoord (volledig)</summary>

```
Een jongen geboren in 2013 rijdt in 2026 bij wegwielrennen in leeftijdscategorie **U14**.

Bron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21, art. 20.0.004
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `knwu-categorie-meisje-2015` — categorie `knwu`, type `standaard`, taalniveau `B2`

- **Vraag:** In welke leeftijdscategorie rijdt een meisje geboren in 2015 bij wegwielrennen in 2026?
- **Verwacht antwoord (kernfeiten):** U12; 2015; artikel 20.0.004
- **Missende kernfeiten:** `artikel 20.0.004`
- **Bron ok:** True (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21, art. 20.0.004

<details><summary>Gegeven antwoord (volledig)</summary>

```
Een meisje geboren in 2015 rijdt in 2026 bij wegwielrennen in leeftijdscategorie **U12**.

Bron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21, art. 20.0.004
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `regio-mnc-veldrijden-starttijden` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** Wanneer starten de jeugdcategorieën bij de MNC veldrijden in seizoen 2026-2027?
- **Verwacht antwoord (kernfeiten):** 2026-2027; 11:05; 11:30
- **Missende kernfeiten:** `11:05`, `11:30`
- **Bron ok:** False (verwachte bron: `knwumidden.nl/competities`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['regio-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
Ik vind geen toekomstige startdatum voor de jeugdcategorieën bij de MNC veldrijden in seizoen 2026-2027 in mijn bronnen.

Wil je dat ik dit doorgeef aan de KNWU-agent voor verdere opheldering?
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
knwumidden.nl/competities — 2026-2027
```

</details>


### `regio-nk-kwalificatie` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** Hoe kwalificeer je je voor het NK jeugd in regio Midden-Oost?
- **Verwacht antwoord (kernfeiten):** selectieprocedure; nationale wedstrijden; 5; Mijn KNWU; LJT
- **Missende kernfeiten:** `Mijn KNWU`
- **Bron ok:** True (verwachte bron: `Nationale_Besluiten_20260918`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** Nationale_Besluiten_20260918.md, versie 2026-09-18

<details><summary>Gegeven antwoord (volledig)</summary>

```
Om je te kwalificeren voor het **NK jeugd wegwielrennen** in regio Midden-Oost, gelden de volgende regels:

- De selectie verloopt via een **landelijk klassement**, waarbij de stand per regio wordt gefilterd op basis van de vestigingsplaats van de vereniging.
- De regio’s krijgen een verdeling van startplaatsen naar rato van het aantal licentiehouders in die regio.
- Je moet **geselecteerd** zijn door je regio en minimaal **2 wedstrijden** hebben gereden voor het NK. Hiervoor mag **1 wedstrijd** uit het voorafgaande seizoen worden meegerekend (voor U9 mag 1 wedstrijd uit U8 meetellen).
- Het **Landelijk Jeugd Toernooi (LJT)** is onderdeel van de selectieprocedure. Voor 2026 zijn de LJT-wedstrijden op **zaterdag 30 mei** en **zondag 31 mei**. Je mag maar aan 1 LJT deelnemen in dit weekend. Als je in de top 5 van de dag-uitslag van je regio eindigt en niet al gekwalificeerd bent via het tussenklassement, kwalificeer je je rechtstreeks voor het NK.
- De regio’s moeten uiterlijk **maandag 1 juni 2026 om 23:59 uur** hun opgaaf van geselecteerde renners doorgeven aan wegsport@knwu.nl.

---
Wil je dit antwoord in begrijpelijk Nederlands (B1) om te delen met leden of ouders?

Bron: Nationale_Besluiten_20260918.md, versie 2026-09-18
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
Nationale_Besluiten_20260918 — 2026
```

</details>


### `regio-juiste-knwu-regio` — categorie `regio`, type `standaard`, taalniveau `B2`

- **Vraag:** In welke KNWU-regio ligt WTC Woerden (Woerden, Utrecht)?
- **Verwacht antwoord (kernfeiten):** Midden-Oost
- **Missende kernfeiten:** `Midden-Oost`
- **Bron ok:** False (verwachte bron: `knwu.nl/over-knwu/regios | kenniscentrum.knwu.nl`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** Handboek Veldrijden Jeugd 2026-2027.md, versie 2026-2027

<details><summary>Gegeven antwoord (volledig)</summary>

```
WTC Woerden (Woerden, Utrecht) ligt in **KNWU-regio Midden**.

Bron: Handboek Veldrijden Jeugd 2026-2027.md, versie 2026-2027
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
knwu.nl/over-knwu/regios | kenniscentrum.knwu.nl — 2026
```

</details>


### `knwu-b1-verzet-u15` — categorie `knwu`, type `standaard`, taalniveau `B1`

- **Vraag:** Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?
- **Verwacht antwoord (kernfeiten):** 6,70
- **Missende kernfeiten:** geen
- **Bron ok:** False (verwachte bron: `TITEL_20-Jeugdwielrennen_20260921`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['knwu-agent'])
- **Gevonden bron:** TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21

<details><summary>Gegeven antwoord (volledig)</summary>

```
Het maximaal toegestane verzet voor jongens U15 bij wegwielrennen is **6,70 meter** (art. 20.1.007).

Bron: TITEL_20-Jeugdwielrennen_20260921.md, versie 2026-09-21
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
TITEL_20-Jeugdwielrennen_20260921 — 2026-09-21
```

</details>


### `regio-b1-mnc-starttijden` — categorie `regio`, type `standaard`, taalniveau `B1`

- **Vraag:** Hoe laat starten de jeugdcategorieën bij de MNC veldrijden in seizoen 2026-2027?
- **Verwacht antwoord (kernfeiten):** 11:05; 11:30
- **Missende kernfeiten:** `11:05`, `11:30`
- **Bron ok:** True (verwachte bron: `knwumidden.nl/competities`)
- **Agent ok:** True (verwacht: ``, laatste beurten: ['regio-agent'])
- **Gevonden bron:** —

<details><summary>Gegeven antwoord (volledig)</summary>

```
Ik vind geen starttijden voor de jeugdcategorieën bij de MNC veldrijden in seizoen 2026-2027 in mijn bronnen.
```

</details>

<details><summary>Verwachte bron / versiedatum</summary>

```
knwumidden.nl/competities — 2026-2027
```

</details>


## Bevindingen / patronen

- **Strikethrough-vragen falen vaak op een stringquirk, niet op inhoud.** De checker zoekt het letterlijke `artikel 20.1.007`, maar het model schrijft `art. 20.1.007` — inhoudelijk correct, toch fail. Dat verklaart 4 van de 9 large-fails (`knwu-verzet-u15`, `knwu-verzet-u17`, `knwu-router-verzet-na-regiovraag`, en in medium ook `knwu-categorie-jongen-2013`/`knwu-categorie-meisje-2015` met `artikel 20.0.004`). Uitzondering: `knwu-verzet-u11` in large is een échte strikethrough-fail — het antwoord noemt 5,78 (de baanwaarde) als "ter vergelijking".
- **Large is duidelijk beter in websearch-gedreven KNWU-vragen** (Kenniscentrum-pagina's correct geraadpleegd en geciteerd: licenties/pakketten, verzekering, versiecheck, wijzigingsmemo, NK-dispensatie). Medium citeert vaak een verkeerde/onderliggende pagina, mist het bedrag (€26) of het startrecht-onderscheid, en interpreteert art. 20.0.005 verkeerd (NK-dispensatie beantwoordt "Nee" in plaats van "Ja").
- **Medium wint 3×**: bij de router/verhelderingsvragen (`knwu-verheldering-categorie-via-router`, `knwu-router-verzet-na-regiovraag`) en bij `regio-hvh-kalender-2026` (geeft 29 maart–27 september wél; large zegt "al afgelopen").
- **Harde gate faalt in beide runs** (large 3/7, medium 0/7), vooral door de strikethrough-vragen.

## Benodigde wijzigingen (uit review van de 9 large-fails, 2026-11-12)

**Status: alle 8 wijzigingen doorgevoerd op 2026-11-12** (evalset.yaml, run_eval.py, knwu-agent.md, regio-agent.md, app/mistral_client.py, tests). Herberekening van de bestaande runs met de nieuwe evalset/checker: large 24→28 ok, medium 17→21 ok; `regio-hvh-kalender-2026` slaat bij medium nu om naar FALEN (datums in het verleden), `knwu-verzet-u11` blijft expres falen (doorhaalwaarde 5,78 echt aanwezig).

De `> [!important]`-blokken hierboven zijn de reviewbevindingen per falende vraag. Daaruit volgen deze wijzigingen:

| # | Constatering uit review (vraag-id) | Benodigde wijziging | Bestand |
|---|---|---|---|
| 1 | `knwu-licentie-pakketten`: antwoord is goed — startrecht wordt wél afgedekt ("welke wedstrijden je mag rijden"), maar het letterlijke `startrecht` ontbreekt in de tekst | Kernfeit `startrecht` vervangen door wat een goed antwoord wel bevat (bijv. `daglicentie` / `regionale wedstrijden`), óf checker synoniemen laten matchen | `eval/evalset.yaml` (of `eval/run_eval.py`) |
| 2 | `knwu-verzet-u15` / `knwu-verzet-u11` / `knwu-verzet-u17`: antwoorden goed, maar `art. 20.1.007` matcht niet op kernfeit `artikel 20.1.007` | Checker normaliseren: `art.`/`art` → `artikel` vóór het matchen van kernfeiten | `eval/run_eval.py` |
| 3 | zelfde drie verzet-vragen: artikelnummer hoort in de **Bron**-regel, en geen irrelevante extra's (meetmethode, buitenland, baan/veld-vergelijking incl. 5,78) | Prompt: bij verzetvragen alleen max. verzet + artikel in de bronregel; geen uitleg over meten/andere disciplines/buitenland | `scripts/prompts/knwu-agent.md` |
| 4 | `knwu-verheldering-categorie-via-router`: vraag kaal naar het geboortejaar, zonder lijst met jaartallen; alleen bij 2-3 niet-evidente opties (bijv. discipline) een vervolgkeuze | Prompt: "vraag alleen naar het geboortejaar, zonder voorbeelden/lijst" aanscherpen | `scripts/prompts/knwu-agent.md` (en router-prompt) |
| 5 | `knwu-router-verzet-na-regiovraag`: dubbel met de andere verzet-vragen | Vraag-id verwijderen uit de eval-set | `eval/evalset.yaml` |
| 6 | `regio-hvh-kalender-2026`: antwoord ("al afgelopen, geen datums in het verleden") is juist — logica is aangepast: antwoorden mogen geen datums in het verleden bevatten | Verwachte kernfeiten `29 maart; 27 september` eruit; die datums juist naar `niet_in_antwoord` (verboden, want in het verleden); verwacht iets als `afgelopen`/`geen toekomstige datum` | `eval/evalset.yaml` |
| 7 | `regio-nk-kwalificatie`: verhelderingsvraag (discipline) is juist, maar er volgde geen eindantwoord | Voeg een vervolgbeurt toe zodat de run eindigt met een eindantwoord, bijv. `beurten: ["NK wegwielrennen"]` | `eval/evalset.yaml` |
| 8 | `regio-juiste-knwu-regio`: run strandde op `Mistral API timeout na 60s` | Per-call timeout van de agent verhogen (60s → bijv. 180s) en/of extra retry; Apart: de regio-agent moet zelf antwoorden i.p.v. doorverwijzen naar knwu-agent | `scripts/agents_config.json` (+ evt. `scripts/prompts/regio-agent.md`) |

Opmerking: met wijziging 6 wordt het medium-antwoord op `regio-hvh-kalender-2026` (dat 29 maart/27 september noemde) voortaan ook afgekeurd — dat is de bedoeling onder de nieuwe logica.
