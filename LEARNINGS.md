# LEARNINGS

Terugkerende problemen, oorzaak en fix. Nieuwste entry bovenaan.

Formaat per entry:

- **YYYY-MM-DD** — probleem — oorzaak — fix

- **2026-11-12** — reviewronde 1 item 2: vraag "met welk verzet moet ik rijden?" werd afgewezen als "valt niet onder KNWU-regelgeving" en doorverwezen naar het clubsecretariaat — oorzaak: de router stuurde wél door naar de knwu-agent (zie router-agent.md), maar de scope-regel in `knwu-agent.md` noemde "verzet" niet, dus wees de agent de vraag af zónder zijn bronnen te raadplegen (trace: geen tool-call op beurt 1); Titel 20 art. 20.1.007 bevat wél de maximale verzetten — fix: "verzet" expliciet in de scope van `knwu-agent.md` +stedtregel met art. 20.1.007 (weg/baan) en "veldrijden: verzet vrij"; `_shared.md` kreeg de regel dat scope-twijfel éérst via de eigen bronnen wordt beslecht; prompt-test in `tests/test_create_agents.py`.

- **2026-11-12** — reviewronde 1: geboortejaar 2025 kreeg "JO11" als categorie — oorzaak: `find_birth_years` (`app/context.py`) liet alleen geboortejaren mét jeugdleeftijdscategorie door, dus bij een kaal jaartal buiten de jeugdindeling injecteerde de proxy geen categorie-contextregel en rekende het model zelf (fout) — fix: een kaal jaartal of een jaartal bij "geboortejaar"/"geboren" krijgt altijd een contextregel, desnoods "valt buiten de jeugdindeling" (`app/context.py`; regressietests in `app/tests/test_context.py`).

- **2026-11-05** — eval run 4 (na prompt-wijzigingen #31) gate NIET gehaald: 9/23 (39,1%), regio 0/5, club 0/5 — oorzaak: vanaf vraag 11 gaf de Mistral API HTTP 402 Payment Required (tegoed op), dus 13 entries kregen geen antwoord; daarnaast 1 echt content-fail: `knwu-nk-dispensatie-u10` (strikethrough, harde gate) miste kernfeit `BMX` — fix: BMX-uitzondering expliciet in `knwu-agent.md` NK-regel; agents re-deployed via `create_agents.py --apply`. Re-run van de gate blokkeert op API-tegoed (top-up nodig).
