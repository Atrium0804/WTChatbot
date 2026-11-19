---
status: accepted
---

# Verzetadvies: aparte verzet-agent met een deterministische rekentool

Wielie controleert of het verzet van een fiets binnen het maximaal toegestane verzet valt en stelt aanpassingen voor (issue #147). Dit vervangt ADR-0006. Het maximaal toegestane verzet komt uit `app/knwu_categories.json` (art. 20.1.007, met drift-check), dezelfde bron als de deterministische bypass, en niet via RAG. De rekensom (wielomtrek uit de ETRTO-maat, zwaarste en lichtste verzet, bereik, grootste toegestane blad en kleinste toegestane kransje) staat in Python (`app/verzet_advies.py`); het taalmodel rekent nooit. Een aparte `verzet-agent` (zonder library en zonder websearch) voert het gesprek en roept de rekentool aan via function calling. De richtlijnen en compatibiliteitstips staan in de prompt van die agent.

De feature geldt alleen voor wegwielrennen: bij veldrijden is het verzet vrij. De uitkomst draagt de voetnoot "berekend voor wegwielrennen". De ETRTO-maat is verplicht invoer; de wielmaat in inches wordt nooit gebruikt om te rekenen.

## Considered options

- **Hybride met RAG voor de grens (ADR-0006)** — verworpen: de grens staat al gestructureerd in `knwu_categories.json` met een drift-check; RAG voegt alleen kans op fouten toe.
- **Helemaal in de app, zonder taalmodel (zoals de bypass)** — verworpen: de dialoog (invoer uitvragen, uitleg, richtlijnen) wordt dan een stijf template en de herkenning van invoer als "50/34, 11-28, 25-622" vraagt veel regex.
- **Intake haalt de getallen eruit en een bestaande agent formuleert het antwoord** — verworpen: geen interactieve dialoog bij ontbrekende invoer.
- **Wielomtrek uit de tabel met standaardwaarden per wielmaat** — verworpen: de wielmaat is te grof en de tabelwaarden wijken af van de formule; de formule met de ETRTO-maat is eenduidig.

## Consequences

- De app krijgt een function-call-lus (maximaal 3 aanroepen per beurt, foutafhandeling, fase "Ik bereken je verzet…", trace-logging). Dit is nieuw: tot nu toe deden alle agents alleen retrieval en websearch.
- De rekentool valideert de invoer (kleinste kransje 9–16T, grootste kransje 23–59T, voorblad 32–60T, banddikte 23–40 mm, velgdiameter 406, 507, 520, 540, 559, 584 of 622 mm) en weigert daarbuiten, zodat de agent niets hoeft te raden.
- De agent geeft nooit zelf een grens op: die komt alleen uit de tool, met bron en versie.
- Er komt een nieuwe route `direct-verzet` (intake-domein) en een nieuwe env-variabele `MISTRAL_AGENT_ID_VERZET`. De bypass biedt bij een initiële verzetvraag hulp aan; een positief antwoord start de verzet-agent met de bypass-gegevens als context.
- De Park Tool-verwijzingen in de prompt komen uit een vaste lijst; de agent verzint geen links.
- `knowledge-documents/bandenmaat-wielomtrek.md` is geen rekenbron meer en gaat uit de library.
