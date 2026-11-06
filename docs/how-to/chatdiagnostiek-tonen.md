# Chatdiagnostiek tonen op een telefoon

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Toon tijdelijke browserdiagnostiek om te bepalen waar het starten of versturen van de chat stopt.

## Voorwaarden

- De versie met `app/static/debug.js` is gedeployd.
- Je gebruikt de browser waarin de fout optreedt.

## Stappen

1. Open `https://chat.famstieltjes.nl/?debug=1`. Herlaad de pagina als het paneel ontbreekt; een bestaande service worker kan nog een oudere app-shell gebruiken.
2. Controleer of bovenaan `Diagnostiek actief` verschijnt, gevolgd door `init-start` en `ready`. Ontbreekt het paneel ook na herladen, meld dit; de diagnostiek is dan niet aantoonbaar geladen.
3. Verstuur een niet-gevoelig testbericht, bijvoorbeeld `Hallo`.
4. Noteer de regels uit het paneel:
   - `ready` ontbreekt: de initialisatie is niet voltooid.
   - `init-failed`: het aanmaken van een veilige client-ID is mislukt. De chat toont een fout en blokkeert versturen; probeer een bijgewerkte browser via HTTPS.
   - `Verstuur aangeklikt` of `Formulier-submit ontvangen`, maar geen `submit`: het chat-submit-handler heeft deze poging niet bereikt.
   - `submit`, maar geen `messages-rendered`: de handler is gestart, maar heeft beide berichten nog niet toegevoegd.
   - `messages-rendered`: het gebruikersbericht en de denkindicator zijn toegevoegd; onderzoek daarna het netwerkverzoek en de verwerking van het antwoord.
   - `JavaScript` of `Promise`: noteer fouttype en eventuele regel/kolom. De volledige foutmelding wordt bewust niet getoond, omdat die gevoelige gegevens kan bevatten.
5. Deel alleen de paneelregels met de beheerder, samen met browser- en iOS-versie. Deel geen screenshot met echte chatinhoud.
6. Open de URL zonder `?debug=1` om het paneel uit te schakelen.

## Controle

Zonder `debug=1` verschijnt geen paneel. De diagnostiek bewaart geen gegevens in browseropslag en verstuurt geen diagnostische gegevens; het normale chatverzoek blijft ongewijzigd. Het paneel toont maximaal 30 regels en bevat geen berichtinhoud, client-ID of volledige foutmeldingen.

De lokale controles zijn `node --test app\tests\test_debug.cjs` en `python -m pytest app\tests -q`. De JavaScript-tests gebruiken de echte chatscripts in een gesimuleerde DOM; een test op de getroffen telefoon blijft nodig.
