# Chatlayout testen

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Controleer dat de invoerbalk binnen het zichtbare browsergebied blijft bij openen, toetsenbordgebruik en schermwijzigingen.

## Voorwaarden

- Python en Node.js zijn beschikbaar.
- De project-venv staat in `.venv`.
- Voer de commando's uit vanuit de repo-root.

## Stappen

1. Installeer de testdependencies en browsers:

   ```powershell
   .venv\Scripts\python -m pip install -r app\requirements-dev.txt
   .venv\Scripts\python -m playwright install chromium webkit
   ```

2. Draai de echte layouttests in beide browserengines:

   ```powershell
   .venv\Scripts\python -m pytest app\tests\test_layout.py -q --browser chromium --browser webkit
   ```

   De tests starten zelf een lokale server. Ze laden de echte HTML, CSS en scripts en controleren elementgrenzen en scrollgedrag. De toetsenbordtests spelen vastgelegde viewportmaten en events na; ze openen geen native toetsenbord. De chat-API is gestubd en service workers zijn in deze tests geblokkeerd zodat zij de API-stub niet omzeilen.

3. Controleer de overige app- en JavaScript-tests:

   ```powershell
   .venv\Scripts\python -m pytest app\tests -q
   node --test "app\tests\*.cjs"
   ```

4. Deploy volgens [app/README.md](../../app/README.md) en controleer op echte apparaten:

   | Omgeving | Handelingen |
   | --- | --- |
   | iPhone-PWA en Safari | Openen, vraagveld aantikken, toetsenbord sluiten, draaien en heropenen |
   | Android-PWA en Chrome | Dezelfde handelingen |
   | Desktopbrowser | Venster verkleinen, lang antwoord tonen en gesprek scrollen |

5. Controleer bij elke handeling:
   - De titel is leesbaar.
   - Het invoerveld en de hele Verstuur-knop zijn zichtbaar en bedienbaar.
   - Bij een lang gesprek scrollen de berichten zonder de header of invoerbalk weg te duwen.
   - Na sluiten van het toetsenbord en heropenen past de layout weer bij het zichtbare venster.
   - Pinch-zoom blijft mogelijk.

6. Gebruik bij een afwijking [Chatdiagnostiek tonen](toon-chatdiagnostiek-op-je-telefoon.md). Noteer de meting na `viewport-fitted`, samen met de browser- en OS-versie. Deel geen echte chatinhoud.

## Controle

De automatische tests moeten slagen. Dat bevestigt niet de native statusbalk, safe-area-insets of het toetsenbord van een specifieke telefoon. Markeer apparaatcontroles pas als geslaagd nadat ze daadwerkelijk zijn uitgevoerd.
