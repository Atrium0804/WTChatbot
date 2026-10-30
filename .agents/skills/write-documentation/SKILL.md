---
name: write-documentation
description: 'Schrijf, wijzig, splits of beoordeel ontwikkelaarsdocumentatie in docs/ van WTChatbot volgens de Diátaxis-standaard. Gebruik voor: documenteren, pagina schrijven, how-to/reference/explanation/tutorial maken, procedure of tool beschrijven, documentatie herstructureren of beoordelen. Triggers: "documenteer", "schrijf documentatie", "maak een how-to", "maak een reference", "leg uit in documentatie", "Diátaxis", "update de docs".'
argument-hint: 'Geef het onderwerp op, bijv. "nieuw document aan de KNWU-bibliotheek toevoegen"'
---

# Documentatie schrijven (Diátaxis)

Schrijf of wijzig ontwikkelaarsdocumentatie volgens de standaard. De regels staan in [docs/DOCUMENTATION_GUIDE.md](../../../docs/DOCUMENTATION_GUIDE.md). Deze skill geeft de werkvolgorde en herhaalt die regels niet.

## Wanneer gebruiken

- Een nieuwe pagina schrijven in `docs/tutorials/`, `docs/how-to/`, `docs/explanation/` of `docs/reference/`.
- Een bestaande pagina ingrijpend wijzigen, splitsen of ordenen per Diátaxis-categorie.
- Een procedure, tool of configuratie vastleggen zodat anderen die kunnen hergebruiken.
- Documentatie beoordelen tegen de standaard.

## Niet gebruiken voor

- ADR's: gebruik `docs/adr/TEMPLATE.md` of de skill `domain-modeling`.
- Termen in `GLOSSARY.md`: gebruik de skill `domain-modeling`.
- Chatbot-inhoud in `docs/knowledge/` of `knowledge-documents/`: dat is kennis voor de bot, geen ontwikkelaarsdocumentatie.

## Procedure

### Stap 1 - Lees de standaard

Lees `docs/DOCUMENTATION_GUIDE.md` en gebruik die als bron voor alle keuzes hieronder.

### Stap 2 - Kies de categorie

- Kies de categorie met de tabel onder "Kies eerst de categorie" in de gids.
- Past de inhoud in meer dan één categorie? Stel dan een splitsing voor met bestandsnamen en laat de gebruiker die bevestigen voordat je schrijft.
- Is de categorie onduidelijk, vraag het de gebruiker.

### Stap 3 - Zoek bestaande documentatie

Zoek op het onderwerp in `docs/`, `docs/adr/` en `GLOSSARY.md`. Breid een bestaande pagina uit in plaats van een tweede pagina te maken. Link naar ADR's in plaats van hun inhoud te herhalen.

### Stap 4 - Lees de bron

Lees de code, configuratie of prompt die je beschrijft. Schrijf niets op dat je niet hebt gecontroleerd en noteer wat je niet kon verifiëren.

### Stap 5 - Schrijf de pagina

- Volg de "Schrijfregels" uit de gids: Nederlands, één H1, koppen in sentence case, kebab-case bestandsnaam.
- Gebruik de structuur die bij de categorie past:
  - **Tutorial:** doel, benodigdheden, genummerde stappen met zichtbaar resultaat, volgende stap.
  - **How-to:** doel in één zin, voorwaarden, genummerde stappen, controle dat het gelukt is.
  - **Explanation:** context, hoe het werkt, afwegingen met links naar ADR's.
  - **Reference:** korte inleiding, daarna tabellen of lijsten zonder uitleg of instructies.
- Plaats de pagina in de map van de categorie.

### Stap 6 - Werk de index bij

Voeg de pagina toe aan de `README.md` van de categoriemap en vervang daar zo nodig de regel `_Nog geen pagina's._`.

### Stap 7 - Controleer

- Elke relatieve link verwijst naar een bestaand bestand.
- De pagina mengt geen categorieën.
- Voeg de AI-waarschuwing uit de gids toe als nog geen mens de pagina heeft beoordeeld.

### Stap 8 - Rapporteer

Geef de gebruiker een korte samenvatting: welke pagina's je hebt gemaakt of gewijzigd, in welke categorie, wat je aan de bron hebt geverifieerd en wat niet.
