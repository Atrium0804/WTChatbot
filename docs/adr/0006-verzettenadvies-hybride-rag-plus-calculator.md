---
status: accepted
---

# Verzettenadvies: hybride — RAG voor de regel, deterministische calculator-tool voor de rekensom

Post-MVP feature waarmee de chatbot adviseert welk verzet geschikt is voor een renner, gegeven geboortejaar en fiets, en op verzoek controleert of een verzet daadwerkelijk in de handel is. De KNWU specificeert het maximaal toegestane verzet als **ontwikkeling** (afgerolde afstand per omwenteling) per leeftijdscategorie/discipline. Die regelwaarden komen via RAG uit de KNWU-documenten (wisselen per seizoen) — nooit hardcoded in de tool. Een function-calling calculator berekent deterministisch alle combinaties kettingblad × cassette × bandenmaat: `ontwikkeling = (tanden voor / tanden achter) × wielomtrek`, gefilterd op de toegestane maximumontwikkeling op basis van geboortejaar. De beschikbaarheidscheck is een lookup in de cassette-/kettingblad-tabellen.

## Considered options

- **Alleen RAG (het model rekent zelf)** — verworpen: een LLM kan niet betrouwbaar rekenen; in de enumerate-and-filter aanpak is de rekensom deterministisch en testbaar.
- **Tool met hardcoded regelwaarden** — verworpen: de KNWU-regel wisselt per seizoen; hardcoded waarden verouderen stilzwijgend en de eval-set merkt het te laat.
- **Alleen hardware-tabellen, zonder regelcheck** — verworpen: dan is er geen antwoord op "mag dit verzet?", alleen op "bestaat dit?".

## Consequences

- Twee databronnen moeten in sync blijven: KNWU-regels via RAG (automatisch per seizoen) en de hardware-tabellen (`docs/knowledge/bandenmaat-wielomtrek.csv`, `cassette-overzicht.csv`) als versie beheerde CSV in het repo, jaarlijks gereviewd door de beheerder.
- De bandenmaat-tabel is compleet voor de gangbare combinaties (wielmaat × 25/28/30 mm) met een `standaard`-rij per wielmaat (24"→507, 26"→559, 28"→622); bij een ETRTO-code op de band gebruikt de bot de exacte rij. Geen runtime-fallback nodig.
- Een kettingblad dat niet op de crank past (boutsteek/BCD) wordt als expliciete onzekerheid gesignaleerd, nooit als feit.
- Invoerflow: wielmaat (24/26/28") → banddikte (25/28/30 mm), met max. 4 verhelderingsvragen tegelijk in één bericht.
- De eval-set wordt uitgebreid met typische verzetvragen ("mag een U15 met 28-622-banden een 52-14 rijden?").
