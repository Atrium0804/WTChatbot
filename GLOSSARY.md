# WTChatbot

De kennischatbot voor wielrenclubs: beantwoordt vragen over KNWU-regelgeving, licenties, wedstrijden en clubzaken op basis van de eigen documenten (RAG), met het KNWU Kenniscentrum als online autoriteit.

## Bronnen en routing

**Kenniscentrum**:
Het online KNWU-kenniscentrum (kenniscentrum.knwu.nl). Autoritaire bron voor de nieuwste versies van regelgeving (met versiedata en wijzigingsmemo's), licentiepakketten/tarieven en verzekeringen.
_Avoid_: "de KNWU-site", "de website van de KNWU" als vage aanduiding

**Bibliotheek (Library)**:
De documentverzameling in Mistral Studio waarover RAG-retrieval plaatsvindt. Elke club heeft er twee: de WTC/Regio-bibliotheek en de KNWU-bibliotheek.
_Avoid_: doclib, documentmap (die termen horen bij de Vibe-spiegel, niet bij de chatbot)

**WTC/Regio-bibliotheek**:
De club- en regiodocumenten (MNC, ZMC, Hans van den Hengel, clubreglementen). Eerste bron voor vragen over regionale wedstrijden.

**KNWU-bibliotheek**:
De nationale regelgevingsdocumenten (Titel 20, Nationale Besluiten, Handboek Veldrijden). Enige toegestane bron, naast het Kenniscentrum, voor nationale/KNWU-vragen.

**Bronvolgorde**:
Vaste routering per vraagtype: regionale wedstrijdvragen eerst WTC/Regio-bibliotheek (met expliciete fallback naar KNWU), nationale/KNWU-vragen alleen KNWU-bibliotheek en/of Kenniscentrum.
_Avoid_: "zoek overal", ongescopeerde retrieval

**Wijzigingsmemo**:
De officiële KNWU-publicatie per reglementsversie op het Kenniscentrum die opsomt wat er gewijzigd is. Bron voor "wat is er veranderd"-vragen; oude documentversies blijven alleen in het repo-archief, nooit in de Library.

**Zichtbare revisies**:
Regelgeving-PDF's bevatten doorgestreepte (vervallen) en nieuw toegevoegde tekst door elkaar. Doorgestreepte tekst is nooit de huidige regel en wordt nooit geciteerd.
_Avoid_: "de schone versie" (die bestaat niet)

## Taal

**Taalniveau B1**:
Standaardniveau van alle antwoorden (gem. zinslengte 10-15 woorden, max 20). Op verzoek kan de gebruiker B2 krijgen.
_Avoid_: "makkelijke taal", "eenvoudig Nederlands"

**Taalniveau B2**:
Uitgebreider niveau op verzoek (max 20 woorden gem., max 25). Bij elk B2-antwoord wordt actief aangeboden het (deel)antwoord naar B1 om te zetten, o.a. om te delen met ouders.

## Kwaliteit en beheer

**Verzin niets**:
De bot verzint nooit regels, data of bedragen; bij ontbrekende informatie, onzekerheid of conflicterende bronnen wordt dit expliciet gesignaleerd in het antwoord.

**Eval-set**:
Vaste set van ±20 typische clubvragen met verwacht antwoord en bron. Launch-gate: ≥90% correct; wordt her-run na elke Library-update.
_Avoid_: testset, testvragen (in deze context)

**Verzettenadvies**:
De geplande uitbreiding (post-MVP) waarmee de chatbot adviseert welk verzet geschikt is voor een renner, gegeven geboortejaar en fiets. Hybride: RAG voor de KNWU-regel, een deterministische calculator-tool voor alle mogelijke combinaties kettingblad × cassette × bandenmaat, plus een beschikbaarheidscheck in de handel.

**Verzet**:
De afstand die een fiets aflegt bij één volle pedaalomwenteling, in meters — de gangbare term in de wielersport. De KNWU drukt het maximaal toegestane jeugdverzet uit in meters per omwenteling. De bandenmaat (via de wielomtrek) zet een tandwielverhouding om in verzet: `verzet (m) = wielomtrek (mm) × (tanden voor / tanden achter) / 1000`.
_Avoid_: "ontwikkeling" voor deze afstand; "verzet" voor de tandwielverhouding zelf (dat is de overbrenging, bijv. 52×14)

**Beheerder**:
De benoemde eindverantwoordelijke (plus vervanger) voor ntfy-alerts, feedback-triage in `/admin/feedback`, Library-updates bij seizoenstart en het archief van oude versies. Staat met naam/rol in `docs/operations.md`.
