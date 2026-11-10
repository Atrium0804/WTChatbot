# WTChatbot

De kennischatbot voor wielrenclubs: beantwoordt vragen over KNWU-regelgeving, licenties, wedstrijden en clubzaken op basis van de eigen documenten (RAG), met het KNWU Kenniscentrum als online autoriteit.

## Bronnen en routing

**Kenniscentrum**:
Het online KNWU-kenniscentrum (kenniscentrum.knwu.nl). Autoritaire bron voor **welke versie** van een reglement de nieuwste is (met versiedata en wijzigingsmemo's), en voor licentiepakketten/tarieven en verzekeringen. Voor de **inhoud** van een regel is de reglementstekst zelf leidend (Titel 20, Nationale Besluiten), ook boven de uitlegpagina's van het Kenniscentrum.
_Avoid_: "de KNWU-site", "de website van de KNWU" als vage aanduiding

**Bibliotheek (Library)**:
De documentverzameling in Mistral Studio waarover RAG-retrieval plaatsvindt. Elke club heeft er vijf: de KNWU-bibliotheek, de Regio-library, de Club-library, de Algemeen-library en een archief-library met oude versies (alleen voor wijzigingsvragen).
_Avoid_: doclib, documentmap (die termen horen bij de Vibe-spiegel, niet bij de chatbot)

**Regio-library**:
De regiodocumenten, Eerste bron voor vragen over regionale wedstrijden in regio Midden Ooost; vragen over wedstrijdregelgeving met expliciete fallback naar de KNWU-bibliotheek.

**Club-library**:
De clubdocumenten van WTC Woerden (ZMC, clubreglementen, WTC-jeugddocumenten). Eerste bron voor clubvragen.

**Algemeen-library**:
De algemene kennisdocumenten (bijv. trainingsleer, het motiveren van kinderen). Te raadplegen bij algemene vragen die geen KNWU-, regio- of clubvraag zijn.

**KNWU-bibliotheek**:
De nationale regelgevingsdocumenten (Titel 20, Nationale Besluiten, Handboek Veldrijden). Enige toegestane bron, naast het Kenniscentrum, voor vragen over KNWU, landelijke of club/regio-overkoepelende wedstrijdregels en de organisatie van nationale wedstrijden en nationaal kampioenschappen (NK).

**Bronvolgorde**:
Vaste drie-wegs routering per vraagtype: KNWU-vragen alleen KNWU-bibliotheek en/of Kenniscentrum; regio-vragen (MNC, Hans van den Hengel) eerst Regio-library (fallback KNWU); clubvragen Club-library + wtcwoerden.nl.
_Avoid_: "zoek overal", ongescopeerde retrieval



**Zichtbare revisies**:
Regelgeving-PDF's bevatten doorgestreepte (vervallen) en nieuw toegevoegde tekst door elkaar. Doorgestreepte tekst is nooit de huidige regel en wordt nooit geciteerd. De KNWU publiceert geen versie zonder zichtbare revisies.
_Avoid_: "de schone versie" (die bestaat niet; bedoel je onze eigen afgeleide tekst, zeg dan opgeschoonde versie)

**Opgeschoonde versie**:
De markdown die wij zelf van een KNWU-PDF met zichtbare revisies maken: doorgestreepte tekst eruit, rode tekst gemarkeerd als gewijzigd, tabellen als markdown-tabel. Staat in de actuele library in plaats van het PDF; het is geen officiële KNWU-publicatie.
_Avoid_: "schone versie", "gecleande PDF"

**Opschoonrapport**:
Het rapport dat `scripts/clean_pdf.py` naast elke opgeschoonde versie schrijft (`knowledge-documents/review/`): bovenaan de twijfelgevallen die een mens afvinkt, daaronder alle weggehaalde stukken per pagina met context.

**Twijfelgeval**:
Een plek in het opschoonrapport waar het script mogelijk iets mist of te veel weghaalt: doorgehaalde letters of cijfers die niet rood zijn (een los doorgehaald opsommingsteken telt niet), een bijna-doorhaling (rode tekst met een lijn net buiten de doorhaalband, blijft staan), of rode tekst in een document zonder enige gevonden doorhaling.

**Knowledge-documents**:
De lokale bronmap (`knowledge-documents/`) met per library één submap (`knwu/`, `regio/`, `club/`, `archive/`). Bron van waarheid voor de sync naar de Mistral-libraries. Uitzondering: `review/` bevat opschoonrapporten en wordt nooit gesynct.
_Avoid_: "kennismap", "documentenmap"

**Sync**:
Het local → remote synchroniseren van `knowledge-documents/` met de bijbehorende Mistral-libraries: de submapnaam is gelijk aan de librarynaam, en remote documenten zonder lokale tegenhanger worden uit de actieve library verwijderd. Archiveren van oude versies gebeurt handmatig (zie ADR-0005).

## Renners en wedstrijden

**Leeftijdscategorie**:
De categorie waarin een renner start (bijv. U13, nieuwelingen, junioren). De categorie-indeling is gebaseerd op het geboortejaar. Wedstrijden kunnen gereden worden per categorie, of met meerdere categorieen tegelijk, waarbij jongens en meisjes van een verschillend geboortejaar samen rijden (bijv jongens U9 en meisjes U10). Zo'n wedstrijdcategorie wordt dan aangeduid met 'JO9/MO10' (jongens onder 9, meisjes onder 10). Na categorie U15 komen de categorieen voor jongeren
Als er verwezen wordt naar een categorie met een nummer, dan wordt zo'n gecombineerde categorie bedoeld:
1 - JO9/MO10
2 - JO10/MO11
3 - JO11/MO12
4 - JO12/MO13
5 - JO13/MO14
6 - JO14/MO15
7 - JO15

_Avoid_: "categorie" zonder toevoeging, "klasse", "leeftijdsklasse"

**Veldritseizoen**:
Het wedstrijdseizoen veldrijden, dat over twee kalenderjaren loopt (Titel 20: september t/m maart). Een renner rijdt het hele veldritseizoen in de leeftijdscategorie waarin hij per 1 januari van dat seizoen valt, in het najaar dus een categorie hoger dan op de weg (bv. een jongen geboren in 2015: U12 op de weg in 2026, U13 in het veldritseizoen 2026-2027).
_Avoid_: "winterseizoen", "crossseizoen" zonder jaartallen


**Licentie**:
De wedstrijdlicentie die de KNWU aan een renner verleent; die geeft het startrecht. Welke licentie een renner nodig heeft, volgt alleen uit het geboortejaar, niet uit discipline of geslacht. Indeling seizoen 2026 (Titel 20, art. 20.0.002): **KNWU Licentie U13** (het jaar waarin je 5 t/m 12 wordt) en **KNWU Licentie U17** (13 t/m 16); vanaf 17 jaar de **KNWU Licentie 17+**. Namen en leeftijdsgrenzen kunnen per seizoen wijzigen (tot 2025: U15 en 15+); Titel 20 is leidend. Eén licentie omvat meerdere leeftijdscategorieën (bv. seizoen 2026: een jongen geboren in 2020 heeft een KNWU Licentie U13 en rijdt in leeftijdscategorie U7). Altijd een KNWU-licentie: ook als een regio- of clubdocument naar een licentie verwijst; regio's en clubs geven zelf geen licenties uit.
_Avoid_: "licentiecategorie" (de KNWU-bronnen gebruiken dat woord ook voor ploegklassen en de oktober-regeling), "licentietype", "regiolicentie"; alleen de U-aanduiding ("U13") als je de licentie bedoelt

**Licentiepakket**:
De variant van een licentie — Basis, Plus of Premium — die bepaalt welk buitenlands startrecht, welke verzekeringsdekking en welke extra's een renner heeft. Alleen de KNWU Licentie U17 en 17+ hebben pakketten; de KNWU Licentie U13 kent één variant.
_Avoid_: "pakket" zonder context, "licentiesoort"

**KNWU-lidmaatschap**:
Verplicht voor licentiehouders; zonder licentie voldoende voor alleen trainingen en clubactiviteiten (geen wedstrijden).

**Wedstrijdcategorie**:
De indeling van een wedstrijd naar niveau (bijv. Cat. II nationale wedstrijd, regionale wedstrijd).
_Avoid_: "categorie" zonder toevoeging

## Taal

**Taalniveau B1**:
Standaardniveau van alle antwoorden (gem. zinslengte 10-15 woorden, max 20). De app biedt een zichtbare keuze voor B2 ("Antwoorden: Uitgebreid"); de keuze staat in localStorage op het apparaat en de proxy injecteert er per bericht een contextregel van (issue #52).
_Avoid_: "makkelijke taal", "eenvoudig Nederlands"

**Taalniveau B2**:
Niveau op verzoek, gekozen in de app (gem. max 20 woorden, max 25). Bij elk B2-antwoord wordt actief aangeboden het (deel)antwoord naar B1 om te zetten, o.a. om te delen met ouders.

## Kwaliteit en beheer

**Verzin niets**:
De bot verzint nooit regels, data of bedragen; bij ontbrekende informatie, onzekerheid of conflicterende bronnen wordt dit expliciet gesignaleerd in het antwoord.

**Bronconflict**:
Een verschil over dezelfde regel tussen de reglementstekst (Titel 20, Nationale Besluiten) en een andere bron, zoals een uitlegpagina van het Kenniscentrum. De bot antwoordt volgens de reglementstekst, noemt het verschil kort in het antwoord, en het verschil wordt zonder vraagtekst gesignaleerd aan de beheerder.
_Avoid_: "fout in de bron", "tegenstrijdigheid" als vage aanduiding

**Eval-set**:
Vaste set van ±20 typische clubvragen met verwacht antwoord en bron. Launch-gate: ≥90% correct; wordt her-run na elke Library-update.
_Avoid_: testset, testvragen (in deze context)

**Feedbackgeschiedenis**:
De reeks laatste vraag/antwoord-paren (turns) van een conversatie die bij een duim-omlaag samen met de feedback wordt opgeslagen, puur voor triage — standaard de laatste 10 turns binnen één sessie. De laatste turn staat ook los als vraag/antwoord bij de feedback-row.
_Avoid_: "chatlog", "conversatielog", "de hele conversatie opslaan"

**Verzettenadvies**:
De geplande uitbreiding (post-MVP) waarmee de chatbot adviseert welk verzet geschikt is voor een renner, gegeven geboortejaar en fiets. Hybride: RAG voor de KNWU-regel, een deterministische calculator-tool voor alle mogelijke combinaties kettingblad × cassette × bandenmaat, plus een beschikbaarheidscheck in de handel.

**Verzet**:
De afstand die een fiets aflegt bij één volle pedaalomwenteling, in meters — de gangbare term in de wielersport. De KNWU drukt het maximaal toegestane jeugdverzet uit in meters per omwenteling. De bandenmaat (via de wielomtrek) zet een tandwielverhouding om in verzet: `verzet (m) = wielomtrek (mm) × (tanden voor / tanden achter) / 1000`.
_Avoid_: "ontwikkeling" voor deze afstand; "verzet" voor de tandwielverhouding zelf (dat is de overbrenging, bijv. 52×14)

**Beheerder**:
De benoemde eindverantwoordelijke (plus vervanger) voor ntfy-alerts, feedback-triage (nu via `scripts/feedback_report.py`, zie [how-to: feedback raadplegen voor triage](docs/how-to/feedback-triage.md); permanent: `/admin/feedback`), Library-updates bij seizoenstart en het archief van oude versies. Staat met naam/rol in `docs/operations.md`.

## Delivery

**Webapp (PWA)**:
De chatbot als installeerbare webapp op de telefoon: manifest + service worker + iconen in `app/static/` installatie vereist HTTPS (zie ADR-0007).
_Avoid_: "app" (suggereert een store-app — via Capacitor is een apart post-MVP-pad), "bladwijzer", "link op het beginscherm"
