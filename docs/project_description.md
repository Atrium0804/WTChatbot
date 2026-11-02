# Projectbeschrijving - WTChatbot

Je schrijft een chatbot voor een wielrenvereniging. De chatbot wordt gebruikt door trainers om vragen van ouders te beantwoorden en door ouders en leden die rechtstreeks met de chatbot chatten. De chatbot haalt informatie uit gezaghebbende bronnen, zodat alleen juiste informatie wordt verstrekt.

De ADR's in `docs/adr/` zijn gegenereerde, ongereviewde drafts — aanpasbaar als dat een beter product oplevert (zie wayfinder-map #2).

## Onderwerpen

De chatbot beantwoordt vragen over de volgende gebieden:

- KNWU-zaken: vragen over landelijke wielersportzaken rond regelgeving, competities en nationale wedstrijden en -kampioenschappen, licentiezaken en verzekeringen, en hieraan gerelateerde procedures.
- Vragen over regionale wedstrijden en competities
- Vragen over clubzaken en -activiteiten van WTC Woerden
- Vragen over technische (verzet)aanpassingen, fietsafstelling en -onderhoud (post-MVP)
- Verzetadvies (post-MVP)

### Verzetadvies (post-MVP)

- De chatbot kan adviseren over toegestane verzetten bij het jeugdwielrennen en over mogelijke aanpassingen:

  - De verzetten zijn vastgelegd door de KNWU en gelden per categorie
  - Het verzet is de afstand die de fiets aflegt bij één pedaalomwenteling
  - Het maximale verzet wordt bepaald door de verhouding van het aantal tanden op het grootste kettingblad (voor) en het aantal tanden op het kleinste tandwiel van de cassette, vermenigvuldigd met de wielomtrek: {aantal tanden voor} / {aantal tanden achter} × {wielomtrek}
  - Het bereik van de versnellingen van een fiets is de verhouding tussen het verzet van de zwaarste versnelling en het verzet van de lichtste versnelling
  - Een geldig verzet is een verzet dat kleiner is dan het maximale verzet
  - Er zijn meerdere combinaties van voorblad/cassette die een geldig verzet opleveren
  - De chatbot heeft beschikking over:
    - een bestand met gangbare cassettes en de tandwielverhoudingen van deze cassettes
    - een bestand met gangbare kettingbladen en de tandverdeling
    - een bestand met gangbare bandenmaten (ETRTO) en de te gebruiken wielomtrek
  - Om het verzet aan te passen moeten de volgende onderdelen op elkaar afgestemd zijn:
    - de trapas(lagers) moeten passen in het frame. Deze kunnen gemonteerd zijn met een schroefverbinding of een persverbinding
    - het meest gangbaar voor de trapas zijn: een trapas met vierkante montagevlakken; een crankstel met een vaste trapas die door de lagers gestoken wordt
    - het crankstel moet passen op de trapas
    - het gatenpatroon van het kettingblad (aantal bouten en boutsteek (BCD)) moet overeenkomen met het crankstel
    - bij een configuratie met een enkel kettingblad (voor), of bij een dubbel crankstel (twee kettingbladen voor) waarbij het grootste kettingblad wordt verwijderd om tot een geldig verzet te komen, dient een kettingblad met een narrow-wide vertanding gebruikt te worden of een kettinggeleider, om aflopen van de ketting te voorkomen
  - Het advies kan meerdere configuraties omvatten:
    - een configuratie die met het minste aantal technische wijzigingen behaald kan worden (een andere cassette of een ander voorblad)
    - een configuratie waarbij geen jeugdcassette (kleinste tandwiel >13 tanden) gebruikt wordt, maar een reguliere cassette (kleinste tandwiel <13 tanden)
    - dicht bij elkaar liggende configuraties, zodat de gebruiker een configuratie kan kiezen op basis van de beschikbaarheid van de benodigde onderdelen
    - Hierbij speelt mee:
      - een 1x-configuratie heeft voordelen omdat het schakelen van de voorderailleur voor jongere kinderen vaak zwaar en lastig is
      - een 2x-configuratie leidt vaak tot te grote verzetten, waarbij jeugdcassettes gebruikt moeten worden; deze zijn minder goed verkrijgbaar
      - voor jongere kinderen levert het bereik van een 1x-crankstel met een reguliere cassette al voldoende bereik op
      - voor oudere jeugd kan het (bij het wegwielrennen) wenselijk zijn om een dubbel crankstel te monteren om voldoende bereik te hebben voor hoge snelheden
      - de maximale snelheid is te berekenen door uit te gaan van een cadans van 110 rpm
  - Bij een verzet dat net niet toegestaan is: vraag of de renner alleen regionale wedstrijden fietst; dan volstaat het afstellen van de derailleur om het kleinste tandwiel onbereikbaar te maken. Als de renner nationale wedstrijden fietst, dan dient het verzet helemaal te voldoen. Adviseer dan ook om de exacte wielomtrek te meten, zodat het advies niet gebaseerd is op mogelijk foutieve referentiewaarden

## Afbakening

- De chatbot beantwoordt enkel vragen over de disciplines wegwielrennen en veldrijden, beide voor de jeugd en nieuwelingen. Vragen over andere disciplines of over volwassenwielrennen worden vriendelijk geweigerd.
- De chatbot beantwoordt geen vragen over KNWU-bestuurszaken, -jaarverslagen en conceptkalenders.
- Vragen die niets met wielrennen, de KNWU of de club te maken hebben, worden vriendelijk geweigerd.

## Tone of Voice

- Zie het aparte document `docs/Tone_of_voice.md`.
- Taalniveau: standaard B2, B1 op verzoek (heroverweging na 2 maanden feedbackdata). Bij elk B2-antwoord biedt de chatbot aan om (een deel van) het antwoord naar B1 om te zetten.

## Bronnen

- De chatbot gebruikt enkel gezaghebbende bronnen:
  - Vragen over KNWU-zaken worden enkel beantwoord met informatie uit KNWU-bronnen: documenten van de KNWU uit de documentenbibliotheek en informatie van de KNWU-site: Kenniscentrum
    - https://kenniscentrum.knwu.nl/regelgeving - gezaghebbende bron voor wedstrijden, kwalificatieprocedures, licenties
    - https://kenniscentrum.knwu.nl/mijnknwu - gezaghebbende bron over administratieve zaken: KNWU-lidmaatschap, licentieaanvragen
    - https://kenniscentrum.knwu.nl/algemeen - gezaghebbende bron voor regio-indeling en tarieven
    - https://kenniscentrum.knwu.nl/toekomstcup - gezaghebbende bron voor U17-wedstrijden van de Toekomstclub
    - https://mijn.knwu.nl/calendar/ - gezaghebbende bron voor nationale wedstrijden
  - Websearch-fallback (ADR-0004): als de documenten in de bibliotheken geen (sluitend) antwoord geven, wordt de websearch-tool ingezet met scope beperkt tot een allowlist van de gezaghebbende domeinen: knwu.nl (incl. kenniscentrum.knwu.nl), knwumidden.nl en wtcwoerden.nl - nooit het open web. Licentievragen raadplegen altijd óók het Kenniscentrum; verzekeringsvragen primair via de sectie Verzekeringen van het Kenniscentrum.
  - Vragen over regionale wedstrijden worden alleen beantwoord voor de regio Midden. Vragen over andere regio's worden vriendelijk geweigerd.
    - https://www.knwumidden.nl/competities - gezaghebbende bron voor wedstrijdreglementen van de Midden Nederland Competitie/Hans van den Hengelcompetitie en de wedstrijdkalender van deze competities
  - Vragen over clubzaken:
    - github-repo met website-teksten - gezaghebbende bron voor WTC Woerden Jeugd
    - website WTCwoerden.nl - gezaghebbende bron voor clubzaken, te weten:
      - https://www.wtcwoerden.nl/index.php?page=Agenda&sid=1 - clubactiviteiten
      - https://www.wtcwoerden.nl/index.php?page=674&sid=1 - contributietarieven
      - https://www.wtcwoerden.nl/index.php?page=956&sid=1 - Gedragscode
      - https://www.wtcwoerden.nl/index.php?page=607&sid=1 - vertrouwenspersoon
  - Parktool.com - gezaghebbende bron voor fietsonderhoud

## Belangrijk

- Beantwoord vragen over KNWU- en regiozaken enkel op basis van de genoemde gezaghebbende bronnen.
- RAG-retrieval is gescoped per bibliotheek: club- en regiovragen via de WTC/Regio-bibliotheek (met expliciete fallback naar de KNWU-bibliotheek), nationale/KNWU-vragen alleen via de KNWU-bibliotheek en/of het Kenniscentrum. Nooit ongescopeerde retrieval over beide bibliotheken tegelijk.
- Vermeld bij elk antwoord de bron en de versiedatum van het gebruikte document.
- Benoem als je geen informatie hebt in de gezaghebbende bronnen om de vraag te beantwoorden.
- Benoem als je tegenstrijdige informatie tegenkomt in de gezaghebbende bronnen en vermeld dan het KNWU-contact: +31 (0)85 070 1900 (di-vr 8.30-12.00 uur).
- De bronnen van de KNWU bevatten documenten die inmiddels vervangen zijn door recentere versies. Controleer altijd of de informatie die je gebruikt de geldende versie is.
- Documenten in de KNWU- en WTC/Regio-bibliotheken zijn de actuele versies; oude versies staan in een aparte archief-library (alleen voor wijzigingsvragen) en in `knowledge-documents/archive/`. Verouderde documenten worden gesignaleerd aan de beheerder.
- Documenten van de KNWU bevatten zichtbare revisies met rode doorgehaalde tekst. Doorgehaalde rode tekst is niet meer geldig en moet uitgesloten worden. Niet-doorgehaalde rode tekst is de vervangende, actuele tekst. Gebruik nooit doorgehaalde tekst.
- Vragen over wijzigingen ("wat is er veranderd?") beantwoord je in bronvolgorde: (1) de officiële wijzigingsmemo van het Kenniscentrum bij het betreffende document, (2) de rood gemarkeerde revisies in het actuele document, (3) als laatste fallback: vergelijk de oude en nieuwe versie uit de archief-library / het repo-archief (`knowledge-documents/archive/`).
- Als meerdere bronnen informatie leveren, dan is de gezaghebbende hiërarchie: KNWU-informatie, Regio-informatie, club-informatie.
- Verzin niets. Benoem als er onvoldoende informatie is om een goed antwoord te geven.
- Doe geen aannames. Stel maximaal 4 verhelderingsvragen tegelijk, in één bericht, en alleen als het antwoord daardoor verandert.

---

## Implementatie

- Hosting: de chatbot wordt gehost op een VPS (Docker + Caddy voor automatische HTTPS) met een FastAPI-proxy. De chatbot gebruikt LLM's van Mistral AI. De API-key staat server-side in een .env-bestand op de server, nooit in de code of in git.
- Delivery: bij MVP live op het tijdelijke domein wtchat.famstieltjes.nl (definitief: chat.wtcwoerden.nl), ingebed op de clubsite via een iframe (artikel/pagina). In de ClubApp via de Website-module (webview) is post-MVP. Mobiel/responsive ontwerp is een vereiste. CORS en Content-Security-Policy (frame-ancestors) zijn beperkt tot de clubsite-origin.
- Beveiliging en misbruik: rate limiting (bijvoorbeeld 10 vragen per uur per IP-hash) en een maximale vraaglengte.
- Privacy en retentie: chatlogs (vraag, antwoord, bronnen, conversation_id, timestamp) worden 90 dagen bewaard (SQLite op de VPS) en daarna automatisch gepurge. IP's worden alleen als salted hash opgeslagen. Geen geheugen tussen sessies: elke bezoeker start een nieuwe conversatie. Er staat een korte privacy-notitie in de chat-UI.
- Bij MVP controleer je handmatig of de documenten in de bibliotheken nog actueel zijn: bij elke library-update vervang je het document, archiveer je de oude versie, werk je versions.json bij en re-run je de eval-set; verouderde documenten signaleert de chatbot in-chat. Post-MVP: periodieke cron-versiecheck tegen het Kenniscentrum, met ntfy-melding aan de beheerder.
- Documentbeheer bij updates: vervang het document in de bibliotheek, archiveer de oude versie in het repo-archief (knowledge-documents/archive/, met datum in de bestandsnaam), werk versions.json bij (documentnaam → versiedatum) en re-run de eval-set.
- De chatbot moet signaleren en vastleggen:
  - Verouderde documenten
  - Ontbrekende vragen
  - Vragen die out-of-scope zijn, zodat we de chatbot kunnen uitbreiden
  - Vragen waarvan de gebruiker aangeeft dat het antwoord niet klopt
- Feedback- en learnings-loop: feedbackknoppen (positief/negatief) onder elk antwoord met een optioneel tekstveld bij negatieve feedback; triage via een beheerder-only admin-pagina; terugkerende problemen en toegepaste fixes vastleggen in LEARNINGS.md.
- Ontwikkelproces: trunk-based branching met conventional commits; unit-tests (pytest, geen live API-calls in CI); eval-set van ±20 typische clubvragen met verwacht antwoord/bron en een launch-gate van ≥90% correct mét correcte bron (re-run na elke bibliotheek-update); CI met lint → typecheck → tests → secrets-scan.
