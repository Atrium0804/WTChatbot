# LEARNINGS

Terugkerende problemen, oorzaak en fix. Nieuwste entry bovenaan.

Formaat per entry:

- **YYYY-MM-DD** — probleem — oorzaak — fix

- **2026-11-05** — eval run 4 (na prompt-wijzigingen #31) gate NIET gehaald: 9/23 (39,1%), regio 0/5, club 0/5 — oorzaak: vanaf vraag 11 gaf de Mistral API HTTP 402 Payment Required (tegoed op), dus 13 entries kregen geen antwoord; daarnaast 1 echt content-fail: `knwu-nk-dispensatie-u10` (strikethrough, harde gate) miste kernfeit `BMX` — fix: BMX-uitzondering expliciet in `knwu-agent.md` NK-regel; agents re-deployed via `create_agents.py --apply`. Re-run van de gate blokkeert op API-tegoed (top-up nodig).
