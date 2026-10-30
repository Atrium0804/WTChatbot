# Bandenmaten en wielomtrek

**Doel:** naslagtabel voor het vertalen van een bandenmaat naar de wielomtrek. Nodig voor het verzettenadvies: de KNWU-regelgeving drukt het maximaal toegestane verzet uit als afstand per volle omwenteling (in meters), en de bandenmaat bepaalt hoeveel meters een bepaalde verhouding (grootste blad voor / kleinste tandwiel achter) daadwerkelijk afrolt.

**Veldbeschrijving:**

- **Banddikte**: bandenbreedte in millimeters (eerste deel van de ETRTO-aanduiding).
- **Velgdiameter**: ETRTO velgdiameter (bead-seat-diameter) in millimeters (tweede deel van de ETRTO-aanduiding).
- **Wielmaat**: gangbare inch-aanduiding van het wiel.
- **Wielomtrek**: afgerolde omtrek in millimeters. Waarden met * zijn berechnet (zie Rekenregel); de overige waarden komen uit de brontabel.
- **Standaard**: `ja` = de rij die de chatbot-flow gebruikt bij lookup op (wielmaat, banddikte) zonder ETRTO-code. Per wielmaat is één standaard velgdiameter festgelegt: 24"→507, 26"→559, 28"→622. Voor 24" volstaat deze standaard (zeldzame fietsjes, niet vooraf op te meten).

Let op: er bestaan meerdere velgdiameters onder dezelfde wielmaat (bijv. 507, 520 en 540 zijn allemaal 24"; 559 is 26" en 622 is 28"). Staat de **ETRTO-code op de bandenzijkant** (banddikte-velgdiameter, bijv. 28-622), dan is die leidend en gebruikt de bot de exacte rij. De standaardkolom dekt de gangbare combinaties (wielmaat × banddikte 25/28/30 mm).

## Tabel

| Banddikte | Velgdiameter | Wielmaat | Wielomtrek (mm) | Standaard |
| --- | --- | --- | --- | --- |
| 25 | 507 | 24" | 1750* | ja |
| 28 | 507 | 24" | 1769* | ja |
| 30 | 507 | 24" | 1781* | ja |
| 37 | 507 | 24" | 1830 | |
| 47 | 507 | 24" | 1890 | |
| 50 | 507 | 24" | 1925 | |
| 23 | 520 | 24" | 1793 | |
| 28 | 540 | 24" | 1795 | |
| 32 | 540 | 24" | 1905 | |
| 25 | 559 | 26" | 1913 | ja |
| 28 | 559 | 26" | 1932* | ja |
| 30 | 559 | 26" | 1945* | ja |
| 32 | 559 | 26" | 1950 | |
| 37 | 559 | 26" | 2005 | |
| 40 | 559 | 26" | 2010 | |
| 23 | 622 | 28" | 2096 | |
| 25 | 622 | 28" | 2105 | ja |
| 28 | 622 | 28" | 2136 | ja |
| 30 | 622 | 28" | 2146 | ja |
| 32 | 622 | 28" | 2155 | |
| 33 | 622 | 28" | 2159 | |
| 35 | 622 | 28" | 2168 | |
| 38 | 622 | 28" | 2180 | |

\* berekend met de rekenregel hieronder.

## Rekenregel

De wielomtrek volgt bij benadering uit:

```
wielomtrek (mm) ≈ π × (velgdiameter + 2 × banddikte)
```

Controle: 47-507 geeft π × (507 + 94) ≈ 1888 mm, tegen 1890 mm in de tabel — de tabelwaarden zijn dus de theoretische omvang, niet gemeten waarden. De tabel is compleet voor de gangbare combinaties (wielmaat × 25/28/30 mm); de ontbrekende waarden zijn met deze formule uitgerekend (gemarkeerd met *). Houd er rekening mee dat de werkelijke omtrek ±1–2 % afwijkt door bandenspanning en slijtage.

## Gebruik bij verzetcontrole

Verzet (afstand per omwenteling) in meters:

```
verzet (m) = wielomtrek (mm) × (tanden voor / tanden achter) / 1000
```

Voorbeeld: 28-622-banden (omtrek 2136 mm) met 52 × 14 geeft 2136 × 52/14 / 1000 ≈ 7,93 m per omwenteling. Of dat verzet is toegestaan, hangt af van de leeftijdscategorie/discipline volgens de KNWU-regelgeving.

Machineleesbare versie: `docs/knowledge/bandenmaat-wielomtrek.csv`.
