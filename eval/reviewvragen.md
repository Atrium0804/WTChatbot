# Reviewvragen

Vaste scenario's voor de [Reviewronde](../GLOSSARY.md). Ze zijn afgeleid van de 22 negatieve feedbackitems uit de eerste testweek (6-11 november 2026). Elk scenario bestaat uit een beginvraag met de vervolgberichten die je in dezelfde conversatie stelt, en de controlepunten: wat er de vorige keer misging en wat een goed antwoord daarom wel of niet bevat.

Hoe je een ronde doorloopt staat in [Doorloop een reviewronde](../docs/how-to/doorloop-een-reviewronde.md). Dit bestand bevat geen ruwe vragen, antwoorden of conversatie-ID's (de repo is publiek): de vragen zijn herschreven tot een herhaalbare testvraag.

Later worden deze scenario's cases in de [Eval-set](../docs/reference/eval-set.md).

## Gebruik

- Start voor elk scenario een **nieuwe conversatie**.
- Stel de beurten in volgorde. Stelt de bot eerst een verhelderingsvraag, beantwoord die dan met het gegeven tussen haakjes en ga daarna verder.
- Beoordeel elk antwoord met de feedbackknop. Bij een duim omlaag noem je in de toelichting het scenario-ID (bijv. `S03`) en het controlepunt dat niet klopt.
- Beoordeel naast de controlepunten altijd de algemene punten hieronder.

## Algemene controlepunten

Deze gelden voor elk antwoord (zie *Verzin niets* en *Taalniveau B1* in [GLOSSARY.md](../GLOSSARY.md)):

- **Bron**: het antwoord is onderbouwd met de eigen bronnen. Ontbreekt informatie, is de bron niet actueel of spreken bronnen elkaar tegen, dan zegt de bot dat.
- **Geen aannames**: de bot vult geen plaats, discipline, geslacht, categorie of seizoen in die niet in het gesprek staan.
- **Datums**: bij "volgende" of "komende" noemt de bot alleen data vanaf vandaag.
- **Relevantie**: geen informatie waar niet om gevraagd is; geen verhelderingsvraag als het antwoord al uit het gesprek volgt.
- **Toon**: zakelijk, geen emoji's, geen vulzinnen; taalniveau B1 tenzij "Uitgebreid" aan staat.
- **Leeftijdscategorie, licentie en wedstrijdcategorie** worden niet door elkaar gehaald.

## Scenario's

### S01 — Leeftijdscategorie bij een geboortejaar

Herkomst: feedbackitems 1 en 10.

Beurten:

1. In welke leeftijdscategorie rijdt mijn zoon?
2. 2015

Variant: start opnieuw en antwoord bij beurt 2 met `2017`.

Variant: start opnieuw en antwoord bij beurt 2 met `2025` (buiten de jeugdindeling).

Controlepunten:

- Noemt de leeftijdscategorie uit de contextregel: voor 2015 U12 op de weg in 2026 en U13 in het veldritseizoen 2026-2027.
- Bij 2025 neemt de bot de contextregel over ("valt buiten de jeugdindeling") en zegt dat er geen jeugdleeftijdscategorie is; geen categorie verzinnen (reviewronde 1).
- Geen informatie over nieuwelingen of andere categorieën die niet gevraagd zijn.
- Noemt de licentie niet als leeftijdscategorie; de licentie alleen als daarnaar gevraagd wordt.

### S02 — Volgende MNC-wedstrijd

Herkomst: feedbackitems 2, 3 en 21.

Beurten:

1. Wanneer is de volgende Midden Nederland Competitie?
2. Alleen als de bot iets noemt dat al voorbij is: "Die datum ligt in het verleden."

Variant: start met "Wanneer is de volgende wedstrijd?" (zonder MNC).

Controlepunten:

- Vraagt niet opnieuw of het om de MNC gaat als dat al in de vraag staat.
- Onderscheidt de twee competities: MNC veldrijden (cross) en MNC wegwielrennen (Hans van den Hengel-competitie). Ze vallen in een ander seizoen.
- Noemt alleen data vanaf vandaag. Staat er geen toekomstige datum in de bron, dan zegt de bot dat.

### S03 — Verzet

Herkomst: feedbackitems 4 en 11; reviewronde 1 item 2.

Beurten:

1. Welk verzet mag mijn zoon gebruiken?
2. (op de vraag naar het geboortejaar) 2015
3. (op de vraag naar de discipline) eerst `weg`; start daarna opnieuw en antwoord `veldrijden`

Controlepunten:

- Wijst een verzetvraag NOOIT af als "buiten KNWU-regelgeving" (reviewronde 1 item 2: "met welk verzet moet ik rijden?" kreeg een doorverwijzing naar het clubsecretariaat); raadpleegt Titel 20 art. 20.1.007.
- Bepaalt eerst de leeftijdscategorie en de discipline en geeft dan een gericht antwoord, geen overzicht van alle categorieën.
- Veldrijden: het verzet is vrij. Weg: het maximale verzet voor die leeftijdscategorie uit Titel 20.
- Noemt geen minimaal verzet dat niet in de bron staat.
- Geen tandwieladvies (kettingblad x cassette) als daar niet om gevraagd is; dat hangt af van de wielmaat.

### S04 — Een categorie lager rijden

Herkomst: feedbackitems 5 en 18.

Beurten:

1. Mag mijn zoon een leeftijdscategorie lager rijden?
2. (op de vraag naar het geboortejaar) 2018

Controlepunten:

- Geen losse zin als "dit geldt niet als de renner met dispensatie rijdt" zonder uitleg.
- Noemt dispensatie alleen als het relevant is, en legt dan in één zin uit wat het is.

### S05 — Licentie bij een geboortejaar

Herkomst: feedbackitem 6.

Beurten:

1. Welke licentie heeft mijn zoon nodig? Hij is geboren in 2012.

Controlepunten:

- Noemt de licentie voluit: KNWU Licentie U17.
- Gebruikt de contextregel; geen oude licentienamen (U15, 15+).

### S06 — Adres van een MNC-cross

Herkomst: feedbackitems 7, 8 en 9.

Beurten:

1. Wat is het adres van de MNC-cross in Hilversum?
2. En de datum van Hilversum?

Controlepunten:

- Noemt alleen een adres dat in de bronnen staat. Staat Hilversum niet in de adreslijst of het MNC-reglement, dan zegt de bot dat.
- Noemt geen datum die voorbij is.
- Verwijst niet naar het KNWU-contact; de vraag gaat niet over de KNWU.

### S07 — Meedoen aan een wedstrijd

Herkomst: feedbackitem 12.

Beurten:

1. Mag ik meedoen aan een wedstrijd?
2. (op de vraag naar het soort wedstrijd) Regio
3. (op de vraag naar het geboortejaar) 2019

Controlepunten:

- Geeft antwoord op de vraag of het mag en wat daarvoor nodig is.
- Geen afstandslimiet of andere details waar niet om gevraagd is.

### S08 — Wat nodig is voor een NK

Herkomst: feedbackitem 13.

Beurten:

1. Wat heb je nodig om mee te doen aan een NK?
2. (op de vervolgvraag) Wegwielrennen, geboren in 2018
3. Waar baseer je dit op?

Controlepunten:

- Het **eerste** inhoudelijke antwoord klopt en is onderbouwd met de KNWU-bronnen; de bot hoeft het niet pas na doorvragen te corrigeren.
- Bij beurt 3 noemt de bot de bron met artikel, en die bron zegt ook echt wat de bot beweert.

### S09 — Starttijd MNC-cross

Herkomst: feedbackitems 14, 15 en 16.

Beurten:

1. Hoe laat start de MNC?
2. (op de vraag naar de discipline) Veldrijden
3. (op de vraag naar de leeftijdscategorie) U8

Controlepunten:

- Stelt geen verhelderingsvraag waarvan het antwoord al uit het gesprek volgt.
- Vertaalt de oude indeling van het MNC-reglement correct en noemt beide aanduidingen, bijv. *categorie 1 (JO8/MO9 en JO9/MO10)*. Leest een categorienummer niet als leeftijd.
- Geen locatie of andere bewering zonder bron; nette opmaak.

### S10 — NK veldrijden jeugd

Herkomst: feedbackitem 17.

Beurten:

1. Wanneer is het NK veldrijden voor de jeugd?

Controlepunten:

- Noemt het eerstvolgende NK (na vandaag), of zegt dat de datum niet in de bronnen staat.
- Noemt geen NK dat al geweest is als "het komende".

### S11 — Clubvragen

Herkomst: feedbackitem 16 (vervolgvragen in dezelfde conversatie).

Beurten:

1. Wanneer is de ZMC?
2. Waar is het clubhuis van WTC Woerden?

Controlepunten:

- Antwoordt alleen uit de Club-library (ZMC-reglement en Website-teksten); geen websearch en geen KNWU-bronnen.
- Noemt alleen data vanaf vandaag.

### S12 — Verzekering en vragen buiten de scope

Herkomst: feedbackitems 18 en 19.

Beurten:

1. Moet ik me verzekeren als ik een wedstrijd rij?
2. Hoe duur is een Mac mini?
3. Met welke bandendruk moet ik rijden bij het veldrijden?

Controlepunten:

- Beurt 1: geen opmerking over dispensatie; die is hier niet relevant.
- Beurt 2: zegt kort dat dit buiten de scope valt.
- Beurt 3: noemt alleen wat in de bronnen staat, of zegt dat het er niet in staat. Geen onbegrijpelijke of verzonnen termen (zoals "achtervering").

### S13 — Begroeting

Herkomst: feedbackitem 20.

Beurten:

1. Hoi

Controlepunten:

- Zakelijk antwoord volgens de toon: geen emoji, geen "Hoi!", geen uitroep.

### S14 — Fietswissel bij het veldrijden

Herkomst: feedbackitem 22.

Beurten:

1. Mag je tijdens het veldrijden van fiets wisselen bij een nationale wedstrijd?
2. Waar baseer je dit op?

Controlepunten:

- Antwoordt voor de jeugd: bij de jeugd is een fietswissel niet toegestaan. Regels voor oudere categorieën noemt de bot alleen als ernaar gevraagd wordt.
- Bij beurt 2 noemt de bot de bron met artikel uit de KNWU-bibliotheek.

## Rondelog

Per ronde alleen tellingen en scenario-ID's, geen ruwe feedback.

| Ronde | Datum | Model | Scenario's met duim omlaag | Wijzigingen daarna |
| --- | --- | --- | --- | --- |
| | | | | |
