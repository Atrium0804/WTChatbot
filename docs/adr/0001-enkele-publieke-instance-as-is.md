---
status: accepted
---

# Enkele publieke instance, as-is — geen multi-tenancy

De chatbot is één publieke, anonieme instance op chat.wtcwoerden.nl met de documenten die erin zitten (WTC/Regio-bibliotheek + KNWU-bibliotheek). Andere wielrenclubs mogen de bot as-is gebruiken met diezelfde informatie. Er is geen multi-tenancy, geen club-selector, geen per-club configuratie, en WTC host/onderhoudt geen instances voor andere clubs.

## Considered options

- **Members-only (login via ClubApp)** — verworpen: voegt een auth-laag toe aan de proxy zonder winst; de onderliggende kennis (KNWU-reglementen, clubreglementen) is sowieso publiek, en login drukt de adoptie.
- **Multi-tenant instance met club-selector** — verworpen: club-/regiodocumenten zijn club-specifiek; per-club config en data-isolatie in de proxy zijn ballast op deze schaal.
- **Aparte instance per club (WTC host ze)** — verworpen: WTC wil de supportlast niet; KNWU-documenten zijn publiek, dus duplicatie kost niets — maar de club koos bewust voor as-is gebruik.

## Consequences

- De WTC/Regio-documenten zijn in principe zichtbaar voor elke bezoeker. Dit is bewust geaccepteerd: het zijn club- en regiodocumenten die sowieso publiek zijn.
- Er is geen manier om per-club/personalisatie toe te voegen zonder deze ADR te herzien.
