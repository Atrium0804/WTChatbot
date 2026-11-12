---
description: "Actualiseer het KNWU-overzicht voor weg en veld met traceerbare primaire bronnen, inclusief afbeeldingen en bronconflicten."
argument-hint: "Peildatum, wegjaar/veldseizoen en eventueel een beperkt onderwerp"
agent: agent
---

# Actualiseer het KNWU-structuurdocument

Werk het [onderzoeksdocument](../../knowledge-documents/ik-wil-weten-hoe-de-licentiestructuur-en-wedstrijd.md) bij. Dit is een afgeleid overzicht, geen officieel reglement.

## Afbakening

- Gebruik de opgegeven peildatum, het wegjaar, het veldseizoen en de eventuele onderwerpbeperking. Ontbreken die, gebruik dan de uitvoeringsdatum en benoem welke perioden je controleert. Leid het veldseizoen niet af van uitsluitend het kalenderjaar.
- Stel gerichte vragen zodra een onduidelijkheid over scope of tegenstrijdige bronnen een keuze van de gebruiker vereist; voorkom langdurig speculatief zoekwerk.
- Wijzig alleen dit overzicht. Vervang niet ongevraagd bronbestanden en wijzig geen app, agents-configuratie, evaluaties, glossary of `versions.json`. Is een echte bronvervanging nodig, meld dat als afzonderlijke taak waarvoor de `knwu-documentwissel`-skill bedoeld is.
- Behoud bestaande, niet door jou gemaakte wijzigingen.

## Bronnen en autoriteit

Volg [CODING_PRINCIPLES](../../CODING_PRINCIPLES.md), [CONTRIBUTING](../../CONTRIBUTING.md) en de bronhierarchie uit [ADR-0003](../../docs/adr/0003-rag-over-eigen-documenten-kenniscentrum-autoriteit.md), inclusief het amendment. Gebruik de termen uit [GLOSSARY](../../GLOSSARY.md).

Gebruik inhoudelijk uitsluitend aantoonbare KNWU-bronnen: KNWU-documenten in de repo, `knwu.nl`, `kenniscentrum.knwu.nl` en bestanden die deze sites als bron linken. Een hostingdomein zoals `static.helpjuice.com` is toegestaan als de KNWU-link de herkomst aantoont. Club- en regiobronnen zijn niet automatisch landelijke KNWU-regels.

Begin met het bronnenregister en de voetnoten in het overzicht, de [lokale KNWU-documenten](../../knowledge-documents/knwu/) en:

- [Veelgestelde vragen nieuwe structuur](https://kenniscentrum.knwu.nl/nl_NL/voor-renners/veelgestelde-vragen-nieuwe-structuur)
- [Reglementen en jaarlijkse besluiten](https://kenniscentrum.knwu.nl/nl_NL/regelgeving/reglementen-en-jaarlijkse-besluiten)

Het overzicht zelf is geen onafhankelijke bron. Onderscheid geldend reglement, uitleg, beleidsvoornemen en historische situatie. Volg bij conflicten de ADR en benoem de afwijking expliciet; combineer geen strijdige bronnen tot een schijnbaar zekere regel.

## Werkwijze

1. Lees het overzicht inclusief metadata, bronconflicten, open vragen, bronregister en voetnoten. Bepaal per onderwerp welke primaire bronnen en versies nodig zijn.
2. Controleer via de KNWU-hub welke documenten actueel en voor de gekozen periode toepasselijk zijn. Vergelijk die met de lokale versies; gebruik bij verschil de toepasselijke primaire versie voor dit overzicht en meld de lokale achterstand. Een paginawijzigingsdatum is geen ingangsdatum van een regel.
3. Controleer tekst, afbeeldingen, tabellen en PDF's. Lees informatie die alleen in een afbeelding staat visueel. Onderscheid in PDF's doorgehaalde regels van geldende toevoegingen; vertrouw niet alleen op platte tekstextractie. Gebruik lokale [opschoonrapporten](../../knowledge-documents/review/) waar relevant. Lukt bron- of beeldinspectie niet, meld precies welke claims niet controleerbaar zijn; vul ze niet uit aannames aan.
4. Controleer binnen de gekozen scope minimaal:
   - Licenties per leeftijd, pakketten, startrechten, prijzen en verzekeringsdekking; onderscheid licentie van startcategorie/klasse en kalendercategorie.
   - Jeugdleeftijden, gecombineerde jongens-/meisjesgroepen en leeftijdsbepaling voor wegjaar versus veldseizoen.
   - Junioren, beloften, elite en masters; deelnamekeuzes en eventuele uitsluitingen.
   - Wegklassen, promotie/degradatie en toepasselijke puntennormen; veldklassen en hun eigen voorwaarden.
   - Regionale/clubwedstrijden, nationale en internationale wedstrijden, NK en relevante competities, inclusief kwalificatievoorwaarden.
   - Historische overgangsjaren en de bestaande bronconflicten; verwijder onzekerheid alleen met aantoonbaar bewijs.
5. Registreer voor iedere gebruikte bron titel, uitgever/herkomst, URL of lokaal pad, documentversie, artikel/pagina/tabel en controledatum. Noteer apart de ingangsdatum of het seizoen als dat expliciet vermeld is. Leg bij afbeeldingen ook de bronpagina en afbeeldings-URL of PDF-pagina vast, met een leesbare transcriptie van relevante gegevens. Noteer bij lokale bronnen de commit-SHA indien beschikbaar.
6. Werk alle geraakte onderdelen consistent bij: samenvatting, tijdlijn, tabellen, Mermaid-diagrammen, overzichtsmatrix, bronconflicten, open vragen, betrouwbaarheid, bronregister en voetnoten. Citeer iedere nieuwe of gewijzigde inhoudelijke claim. Los ook achterhaalde onderhoudsvragen op, zoals de al uitgevoerde verplaatsing naar `knowledge-documents`.
7. Werk metadata alleen bij voor wat daadwerkelijk is gecontroleerd. Bij een volledige hercontrole mag de onderzoeksdatum veranderen, met vermelding van resterende onzekerheden. Bij een gedeeltelijke controle behoud je die datum en noteer je onderwerp, periode en controledatum afzonderlijk in de metadata. Behoud de status als afgeleide synthese en de verwijzing naar deze prompt.

## Klaar als

- Iedere gewijzigde claim is terug te voeren op een toepasselijke primaire KNWU-bron met versie en vindplaats.
- Afbeeldingsinformatie is gecontroleerd of expliciet als niet verifieerbaar gemarkeerd.
- Leeftijd, licentie, klasse, wedstrijdstatus, wegjaar en veldseizoen zijn nergens onbedoeld vermengd.
- Alle geraakte tabellen, diagrammen en verwijzingen sluiten op elkaar aan; geen verweesde voetnoten of kapotte lokale links.
- Onopgeloste bronconflicten en beperkingen zijn zichtbaar; metadata claimt geen ruimere controle dan uitgevoerd.
- Alleen de afgesproken bestanden zijn gewijzigd. Controleer de diff en gebruik aanwezige documentvalidatie indien relevant; start geen app-tests voor uitsluitend Markdown-wijzigingen.

Geef na afloop een korte samenvatting van de gecontroleerde periode/onderwerpen, inhoudelijke wijzigingen, resterende conflicten en eventuele afzonderlijke bronvervanging die nog nodig is.
