# Coding principles

Deze principes gelden voor alle Python-code in deze repo (chatbot, tools, ingestie, evals). Ze zijn bedoeld voor mensen én AI-agents.

## Structuur

- **Voorspelbare indeling.** Groepeer code per feature (bijv. `tools/`, `ingest/`, `evals/`), niet per technische laag. Gedeelde utilities alleen voor echt gedeelde zaken.
- **Eén duidelijk entry point** per script of service. Geen verborgen initialisatie bij import.
- **Geen duplicatie die dezelfde fix op meerdere plekken vraagt.** Haal gedeelde structuur eruit vóórdat je een tweede vergelijkbaar bestand maakt.

## Code

- **Plat en expliciet boven abstracties.** Geen klassenhiërarchieën, metaprogramming of slimme trucs als een functie volstaat.
- **Lineaire control flow, kleine functies** (richtlijn 10–50 regels) met één duidelijk doel.
- **Expliciete state.** Geef parameters mee; geen globals of verborgen module-state.
- **Type hints** op publieke functies en tool-signatures.
- **Beschrijvende namen**, Engels in code; domeintermen volgens [GLOSSARY.md](GLOSSARY.md).

```python
# Goed: plat, expliciet, testbaar
def calculate_gear_development(chainring: int, sprocket: int, wheel_circumference_m: float) -> float:
    if sprocket <= 0:
        raise ValueError(f"sprocket must be > 0, got {sprocket}")
    return chainring / sprocket * wheel_circumference_m
```

## Chatbot-specifiek

- **Tools zijn pure functies** met getypeerde in- en output en zonder netwerk- of LLM-afhankelijkheid waar mogelijk. Zo zijn ze los te testen (zie de calculator uit [ADR-0006](docs/adr/0006-verzettenadvies-hybride-rag-plus-calculator.md)).
- **LLM- en API-aanroepen achter één dunne laag**, zodat tests die laag kunnen mocken en de provider vervangbaar blijft.
- **Retrieval is altijd per bibliotheek gescoped** ([ADR-0003](docs/adr/0003-rag-over-eigen-documenten-kenniscentrum-autoriteit.md)).
- **Antwoorden dragen bron + versiedatum.** Code die antwoorden opbouwt mag die metadata niet laten vallen.
- **Prompts staan in aparte bestanden**, niet als lange strings verspreid door de code.

## Fouten, logging en secrets

- **Informatieve fouten** met context en een actie (`"Library 'KNWU' not found; check MISTRAL_LIBRARY_ID in .env"`). Geen kale `except: pass`.
- **Log op grenzen** (inkomende vraag, tool-call, LLM-call, fout), niet in elke functie. Log geen secrets of volledige persoonsgegevens.
- **Secrets alleen via `.env`/environment variables**, nooit in code of commits. Lever een `.env.example` met lege waarden.

## Tests

- Test **observeerbaar gedrag**, niet implementatiedetails. Tests zijn deterministisch: geen echte LLM- of netwerkcalls in unit tests.
- Minimum per wijziging:
  - nieuwe functie of tool → happy path + één foutgeval;
  - bugfix → test die de bug reproduceert;
  - gewijzigd gedrag → aangepaste tests.
- Antwoordkwaliteit (bronvolgorde, "verzin niets") bewaak je met de eval-set, niet met unit tests.
