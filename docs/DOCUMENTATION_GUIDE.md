# Documentatiegids

Deze gids beschrijft hoe we ontwikkelaarsdocumentatie in deze repo schrijven. Hij geldt voor mensen en AI-agents.

## Wat valt hieronder

Ontwikkelaarsdocumentatie in `docs/` volgt [Diátaxis](https://diataxis.fr/). Buiten deze gids vallen:

- [adr/](adr/): architectuurbesluiten volgens [TEMPLATE.md](adr/TEMPLATE.md);
- [agents/](agents/): instructies voor AI-agents;
- [knowledge/](knowledge/) en `knowledge-documents/`: **inhoud voor de chatbot**, geen documentatie over de code. Meng die twee niet.

## Kies eerst de categorie

Elke pagina hoort bij precies één categorie en staat in de bijbehorende map. Mengt een pagina categorieën, splits hem dan en link de delen naar elkaar.

| Categorie | Map | Vraag van de lezer | Voorbeeld |
| --- | --- | --- | --- |
| Tutorial | [tutorials/](tutorials/) | "Leer me de basis" | Eerste keer de chatbot lokaal draaien |
| How-to | [how-to/](how-to/) | "Hoe doe ik X?" | Nieuw document aan een bibliotheek toevoegen |
| Explanation | [explanation/](explanation/) | "Waarom werkt het zo?" | Hoe bronvolgorde en retrieval samenwerken |
| Reference | [reference/](reference/) | "Wat zijn de exacte details?" | Overzicht van tools en environment variables |

## Schrijfregels

- **Taal:** Nederlands. Code, identifiers en commando's blijven zoals ze in de code staan.
- **Opmaak:** één H1, koppen in sentence case, bestandsnaam in kebab-case. Geen `Last updated`-regel; git houdt dat bij.
- **Eerst zoeken:** breid een bestaande pagina uit in plaats van een bijna-dubbele te maken.
- **Linken, niet herhalen:** verwijs naar ADR's, [GLOSSARY.md](../GLOSSARY.md) en code in plaats van hun inhoud over te nemen.
- **Termen** volgens [GLOSSARY.md](../GLOSSARY.md).
- **Klopt het?** Toets elke uitspraak over code, commando's of configuratie aan de bron voordat je hem opschrijft.
- **Index bijwerken:** zet een nieuwe pagina in de `README.md` van haar map.
- **Diagrammen** in Mermaid, geen screenshots van diagrammen.

## AI-gegenereerde pagina's

Zet direct onder de titel van een pagina die nog niet door een mens is nagelezen:

```markdown
> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.
```

Verwijder de melding zodra iemand de pagina heeft gecontroleerd.
