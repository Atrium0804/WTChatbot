---
status: accepted
---

# Bij duim-omlaag slaan we de feedbackgeschiedenis op: de laatste 10 turns (vraag/antwoord) per conversatie

Tot nu toe bewaarde de server bij duim-omlaag alleen de laatste vraag en het laatste antwoord. Voor triage is dat onvolledig: een "fout" antwoord is vaak pas te beoordelen vanuit de bredere context van het gesprek. Daarom houdt de FastAPI-proxy per conversatie een in-memory rolling window bij van de laatste `FEEDBACK_HISTORY_TURNS` (standaard 10) turns. Bij duim-omlaag wordt dat als JSON-array opgeslagen in de nieuwe `history`-kolom van de feedback-tabel; `question`/`answer` blijven de laatste turn, zodat het triage-rapport backwards compatible blijft. Per turn wordt het antwoord afgekapt op 2000 tekens (consistent met de toelichting). Bestaande DB's (o.a. op de NAS) migreren bij de volgende app-start via `ALTER TABLE` in `store.init_db`.

## Considered options

- **Alleen de laatste turn (status quo)** — verworpen: onvolledige informatie voor triage.
- **Client stuurt de berichtenlijst mee naar /feedback** — verworpen: spoofable, grotere payload, en de server ziet in /chat elke turn sowieso al.
- **Aparte tabel feedback_turns** — verworpen: zelfde resultaat, maar meer join-complexiteit in rapport en purge.
- **Meer dan 10 turns of onbeperkt** — verworpen: data-minimisatie; 10 dekt de gangbare context, de 30-dagenretentie begrenst de rest.

## Consequences

- Meer content in de DB bij duim-omlaag (max. 10 turns × 2000 tekens per row); retentie blijft 30 dagen met automatische purge, duim-omhoog blijft een kale teller. Privacy-notitie in de chat-UI en de privacy-paragrafen in de docs zijn aangepast.
- De historie leeft in-memory per sessie: na een server-restart is het window leeg en slaat duim-omlaag een lege historie op — dezelfde beperking als de voormalige `last_exchange`.
- `scripts/feedback_report.py` rendert de historie per negatieve row (oudste eerst, laatste turn gemarkeerd) en kan ook oude rows zonder `history`-kolom tonen.
- De counter (`FEEDBACK_HISTORY_TURNS`, env-var, default 10) stuurt zowel de cap van het in-memory window als de slice die wordt opgeslagen.
