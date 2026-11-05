# WTChatbot

De kennischatbot voor wielrenclubs: beantwoordt vragen over KNWU-regelgeving, licenties, wedstrijden en clubzaken op basis van de eigen documenten (RAG), met het KNWU Kenniscentrum als online autoriteit.

## Bronnen en routing

**Kenniscentrum**:
Het online KNWU-kenniscentrum (kenniscentrum.knwu.nl). Autoritaire bron voor de nieuwste versies van regelgeving (met versiedata en wijzigingsmemo's), licentiepakketten/tarieven en verzekeringen.
_Avoid_: "de KNWU-site", "de website van de KNWU" als vage aanduiding

**Bibliotheek (Library)**:
De documentverzameling in Mistral Studio waarover RAG-retrieval plaatsvindt. Elke club heeft er vijf: de KNWU-bibliotheek, de Regio-library, de Club-library, de Algemeen-library en een archief-library met oude versies (alleen voor wijzigingsvragen).
_Avoid_: doclib, documentmap (die termen horen bij de Vibe-spiegel, niet bij de chatbot)

**Regio-library**:
De regiodocumenten (MNC, Hans van den Hengel-competitie). Eerste bron voor vragen over regionale wedstrijden in regio Midden; bij MNC/HvH-vragen met expliciete fallback naar de KNWU-bibliotheek.

**Club-library**:
De clubdocumenten van WTC Woerden (ZMC, clubreglementen, WTC-jeugddocumenten). Eerste bron voor clubvragen, samen met wtcwoerden.nl via websearch; geen fallback naar de KNWU-bibliotheek.

**Algemeen-library**:
De algemene kennisdocumenten (bijv. trainingsleer, het motiveren van kinderen). Te raadplegen bij algemene vragen die geen KNWU-, regio- of clubvraag zijn.

**KNWU-bibliotheek**:
De nationale regelgevingsdocumenten (Titel 20, Nationale Besluiten, Handboek Veldrijden). Enige toegestane bron, naast het Kenniscentrum, voor nationale/KNWU-vragen.

**Bronvolgorde**:
Vaste drie-wegs routering per vraagtype: KNWU-vragen alleen KNWU-bibliotheek en/of Kenniscentrum; regio-vragen (MNC, Hans van den Hengel) eerst Regio-library (fallback KNWU); clubvragen Club-library + wtcwoerden.nl.
_Avoid_: "zoek overal", ongescopeerde retrieval

**Wijzigingsmemo**:
De officiële KNWU-publicatie per reglementsversie op het Kenniscentrum die opsomt wat er gewijzigd is. Eerste bron voor "wat is er veranderd"-vragen; daarna de rode revisies in het actuele document, dan een vergelijking met de oude versie uit de archief-library / het repo-archief (`knowledge-documents/archive/`).

**Zichtbare revisies**:
Regelgeving-PDF's bevatten doorgestreepte (vervallen) en nieuw toegevoegde tekst door elkaar. Doorgestreepte tekst is nooit de huidige regel en wordt nooit geciteerd. De KNWU publiceert geen versie zonder zichtbare revisies.
_Avoid_: "de schone versie" (die bestaat niet; bedoel je onze eigen afgeleide tekst, zeg dan opgeschoonde versie)

**Opgeschoonde versie**:
De markdown die wij zelf van een KNWU-PDF met zichtbare revisies maken: doorgestreepte tekst eruit, rode tekst gemarkeerd als gewijzigd. Staat in de actuele library in plaats van het PDF; het is geen officiële KNWU-publicatie.
_Avoid_: "schone versie", "gecleande PDF"

**Opschoonrapport**:
Het rapport dat `scripts/clean_pdf.py` naast elke opgeschoonde versie schrijft (`knowledge-documents/review/`): bovenaan de twijfelgevallen die een mens afvinkt, daaronder alle weggehaalde stukken per pagina met context.

**Twijfelgeval**:
Een plek in het opschoonrapport waar het script mogelijk iets mist of te veel weghaalt: doorgehaalde tekst die niet rood is, een bijna-doorhaling (rode tekst met een lijn net buiten de doorhaalband, blijft staan), of rode tekst in een document zonder enige gevonden doorhaling.

**Knowledge-documents**:
De lokale bronmap (`knowledge-documents/`) met per library één submap (`knwu/`, `regio/`, `club/`, `archive/`). Bron van waarheid voor de sync naar de Mistral-libraries. Uitzondering: `review/` bevat opschoonrapporten en wordt nooit gesynct.
_Avoid_: "kennismap", "documentenmap"

**Sync**:
Het local → remote synchroniseren van `knowledge-documents/` met de bijbehorende Mistral-libraries: de submapnaam is gelijk aan de librarynaam, en remote documenten zonder lokale tegenhanger worden uit de actieve library verwijderd. Archiveren van oude versies gebeurt handmatig (zie ADR-0005).

## Renners en wedstrijden

**Leeftijdscategorie**:
De categorie waarin een renner start (bijv. U13, nieuwelingen, junioren). Volgt uit geboortejaar, geslacht, discipline en seizoen, met uitzonderingen (meisjes een U-categorie lager, afwijkende indeling in het veldritseizoen, dispensatie). Gebruikers kennen meestal het geboortejaar en geslacht van de renner, niet de leeftijdscategorie.
_Avoid_: "categorie" zonder toevoeging, "klasse", "leeftijdsklasse"

**Wedstrijdcategorie**:
De indeling van een wedstrijd naar niveau (bijv. Cat. II nationale wedstrijd, regionale wedstrijd).
_Avoid_: "categorie" zonder toevoeging

## Taal

**Taalniveau B1**:
Niveau op verzoek (gem. zinslengte 10-15 woorden, max 20).
_Avoid_: "makkelijke taal", "eenvoudig Nederlands"

**Taalniveau B2**:
Standaardniveau van alle antwoorden (max 20 woorden gem., max 25; heroverweging na 2 maanden feedbackdata). Bij elk B2-antwoord wordt actief aangeboden het (deel)antwoord naar B1 om te zetten, o.a. om te delen met ouders.

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
