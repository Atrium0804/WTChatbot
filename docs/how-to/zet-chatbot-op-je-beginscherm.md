# Zet de chatbot op je beginscherm

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

De chatbot van WTC Woerden kun je installeren als webapp (PWA): Wheely krijgt dan een eigen icon op je beginscherm en opent als losse app. Gebruik hiervoor altijd de beveiligde link `https://chat.famstieltjes.nl` — de installatie werkt alleen via HTTPS (een service worker registreert niet op plain HTTP).

## Android (Chrome)

1. Open `https://chat.famstieltjes.nl` in Chrome.
2. Tik rechtsboven op het menu (drie verticale puntjes) en kies **App installeren** (bij sommige versies: "Toevoegen aan beginscherm" en dan **Installeren**).
3. Bevestig met **Installeren**. Wheely verschijnt op je beginscherm.

## iPhone (Safari)

1. Open `https://chat.famstieltjes.nl` in Safari.
2. Tik op het deelblad-icoon (vierkant met pijl omhoog) en kies **Zet op beginscherm**.
3. Tik rechtsboven op **Voeg toe**. Wheely verschijnt op je beginscherm met het club-icon.

## Let op

- Via het LAN-adres zonder HTTPS (alleen voor test) werkt de installatie niet; gebruik altijd de HTTPS-link.
- Na installatie opent de chatbot standalone, zonder browserbalk.
- Privacy: de chatbot onthoudt niets tussen sessies en de service worker bewaart nooit je vragen of antwoorden — alleen de app-shell wordt lokaal gecached (zie [ADR-0007](../adr/0007-fase-1-op-nas-achter-npm.md)).
