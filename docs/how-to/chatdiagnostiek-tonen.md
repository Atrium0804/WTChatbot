# Chatdiagnostiek tonen op een telefoon

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Toon tijdelijke browserdiagnostiek om te bepalen waar het starten of versturen van de chat stopt.

## Voorwaarden

- De versie met `app/static/debug.js` is gedeployd.
- Je gebruikt de browser waarin de fout optreedt.

## Stappen

1. Open `https://chat.famstieltjes.nl/?debug=1`. Open in een geinstalleerde PWA de link **Schermdiagnostiek (#54)** onder **Privacy-notitie** om binnen de app te blijven. Dit start een nieuw gesprek. Herlaad de pagina als het paneel ontbreekt; een bestaande service worker kan nog een oudere app-shell gebruiken.
2. Controleer of bovenaan `Diagnostiek actief` verschijnt, gevolgd door `init-start` en `ready`. Controleer voor schermmetingen ook `"version":"viewport-54-v3"` in een JSON-regel; een oudere versie mist de aanvullende scrollmetingen. Ontbreekt het paneel ook na herladen, meld dit; de diagnostiek is dan niet aantoonbaar geladen.
3. Verstuur een niet-gevoelig testbericht, bijvoorbeeld `Hallo`.
4. Noteer de regels uit het paneel:
   - `ready` ontbreekt: de initialisatie is niet voltooid.
   - `init-failed`: het aanmaken van een veilige client-ID is mislukt. De chat toont een fout en blokkeert versturen; probeer een bijgewerkte browser via HTTPS.
   - `Verstuur aangeklikt` of `Formulier-submit ontvangen`, maar geen `submit`: het chat-submit-handler heeft deze poging niet bereikt.
   - `submit`, maar geen `messages-rendered`: de handler is gestart, maar heeft beide berichten nog niet toegevoegd.
   - `messages-rendered`: het gebruikersbericht en de denkindicator zijn toegevoegd; onderzoek daarna het netwerkverzoek en de verwerking van het antwoord.
   - `JavaScript` of `Promise`: noteer fouttype en eventuele regel/kolom. De volledige foutmelding wordt bewust niet getoond, omdat die gevoelige gegevens kan bevatten.
   - `[DEBUG-54] viewport-fitted`: de viewportaanpassing is uitgevoerd. Het paneel meet in het volgende animatieframe de zichtbare viewport, elementgrenzen en safe-area-insets. `PASS` betekent dat footer, vraagveld en Verstuur-knop binnen de gemeten viewport vallen; native iOS-overlays en tekstvervaging zijn niet meetbaar met deze controle.
   - Tik op het paneel om een actuele `manual`-meting te maken, met en zonder toetsenbord.
   - Kopieer de volledige JSON-regel, inclusief `layout`, `scroll`, `viewport.pageTop`, `viewport.pageLeft` en `bodyTop`. Deze aanvullende waarden onderscheiden de layoutviewport, de pagina-scrollpositie, de zichtbare viewportpositie in het document en de toegepaste CSS-top.
   - Controleer ook zonder diagnostiekpaneel of de kop leesbaar is en de invoerbalk zichtbaar blijft wanneer het toetsenbord opent en sluit. Een `PASS` vervangt deze visuele controle niet.
5. Deel alleen de paneelregels met de beheerder, samen met browser- en iOS-versie. Deel geen screenshot met echte chatinhoud.
6. Open de URL zonder `?debug=1` om het paneel uit te schakelen.

## Statusbalkproef voor #54

1. Bewaar eerst een screenshot van de fout in de geinstalleerde PWA, zonder meetpaneel.
2. Deploy de proef met `apple-mobile-web-app-status-bar-style` op `default` en app-shell-cache `wtchat-shell-v16`. De viewportcode blijft ongewijzigd. Verwijder de bestaande startscherm-app en voeg de gedeployde versie opnieuw toe via Safari, zodat een oude installatie de vergelijking niet verstoort.
3. Controleer dezelfde weergave: is de titel scherp, is de blauwe strook onderaan verdwenen en blijft de invoerbalk zichtbaar met en zonder toetsenbord? Noteer elk resultaat afzonderlijk.

[Apples gearchiveerde beschrijving](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariHTMLRef/Articles/MetaTags.html) plaatst webinhoud bij `default` onder de statusbalk, in plaats van erachter bij `black-translucent`. De uitkomst op de gebruikte iOS-versie moet op het toestel worden vastgesteld; lokale HTML- en layouttests bewijzen dit native gedrag niet.

### Uitkomst: wazige kop komt door `theme-color`

Op iOS 27 vervaagt het systeem in de geinstalleerde PWA de bovenste ±36 css-px onder de statusbalk zodra er een theme-color is: via `<meta name="theme-color">` of via `theme_color` in het manifest. In een Safari-tabblad treedt het niet op. Zonder beide is de kop scherp en is de statusbalk wit. Daarom heeft de app geen theme-color; `test_no_theme_color_because_ios_blurs_top_edge` bewaakt dat.

iOS leest deze instellingen bij installatie: verwijder de startscherm-app en voeg hem opnieuw toe om een wijziging te zien. Zie ook [devswha/ovis#164](https://github.com/devswha/ovis/issues/164): daar geeft `black-translucent` een nog bredere wazige band (±112 px).

## Controle

Zonder `debug=1` verschijnt geen paneel. De diagnostiek bewaart geen gegevens in browseropslag en verstuurt geen diagnostische gegevens; het normale chatverzoek blijft ongewijzigd. Het paneel toont maximaal 30 regels en bevat geen berichtinhoud, client-ID of volledige foutmeldingen.

Zie [Chatlayout testen](test-chatlayout.md) voor de lokale controles. De JavaScript-tests gebruiken een gesimuleerde DOM en de layouttests een echte browserengine; een test op de getroffen telefoon blijft nodig.
