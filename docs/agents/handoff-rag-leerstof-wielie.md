# Handoff: leerstof "Hoe verwerkt een AI documenten (RAG), en waarom gaat het mis?"

**Datum:** 2026-11-13
**Repo:** `C:\git_prive\WTChatbot` (Atrium0804/WTChatbot)
**Gebruiker:** beheerder van Wielie, de clubbot. Kent het domein (KNWU-reglementen, wielrennen) en het project goed, maar heeft **weinig kennis van hoe RAG werkt**: hoe een PDF tekst wordt, wat chunks en embeddings zijn, wat zoeken via betekenis (semantisch zoeken) inhoudt, wat top-k is, en hoe een agent zoekt. Schrijft en denkt in het Nederlands.

## Doel van de volgende sessie

Maak **leerstof (learning/teach)** waarmee de gebruiker begrijpt:

1. Hoe een document in de praktijk door een RAG-pijplijn gaat: PDF → tekst/markdown → chunks → embeddings → zoekopdracht → top-k chunks → antwoord van het model.
2. **Waarom** antwoorden dan incompleet of fout worden.
3. Welke knoppen er zijn (documentstructuur, chunking, prompt, model, eval) en wat elke knop wel en niet oplost.

Gebruik de **echte casus hieronder** als rode draad. De gebruiker leert het best van zijn eigen bug. Vermijd abstracte theorie zonder voorbeeld.

## De casus (bewezen in deze sessie)

Symptoom: bij "hoe kwalificeer ik me voor het NK wegwielrennen (jeugd)" noemt Wielie het **Landelijk Jeugd Toernooi (LJT)** en de eis van **minimaal 2 wedstrijden** niet. Soms haalt hij er **LJC**-regels van mountainbike bij. De twee conversaties staan in `C:\git_prive\WTChatbot\wielie-feedback.md` (items 10 en 11). Dat bestand bevat gebruikersvragen: niet kopiëren naar git of leerstof, alleen geanonimiseerd parafraseren.

Bevindingen, op volgorde van belang (elk is een les op zich):

| # | Mechanisme | Bewijs |
|---|---|---|
| 1 | **Structuurverlies bij het omzetten van PDF naar markdown.** `scripts/clean_pdf.py` maakt van koppen platte tekst. De PDF heeft de hiërarchie wél in de opmaak (NB: 20pt = discipline-hoofdstuk, 15pt = paragraaf, vet genummerd = subparagraaf, 12/13pt = kopjes). | Bronsectie: `knowledge-documents/knwu/Nationale_Besluiten_20260918.md` r. 1536–1651 ("NK Weg Jeugd"). |
| 2 | **Chunking op vaste lengte (~2000 tekens) knipt door koppen heen.** De LJT-chunk begint midden in een zin ("met een officiële licentie van hun bond…") en bevat nergens "weg" of "NK Weg Jeugd". Een **verweesde chunk**. | Opgehaalde snippets van conversatie 10 staan in de session-map (zie hieronder), `snippets.txt`. |
| 3 | **Opgehaald ≠ gebruikt.** In een rode run zat de LJT-chunk op rang 8 van 10 tussen de resultaten, maar het model liet hem weg, omdat het niet kon zien bij welk NK hij hoort. | Loop-uitvoer `out_medium_1.txt`; de rangvolgorde staat in het sessielogboek. |
| 4 | **Disciplineverwarring.** De MTB-chunk "JEUGD / Kwalificatie eisen … LJC" (NB p. 51, r. ~2457) mist ook zijn context en scoort hoog op "kwalificatie NK jeugd". | Die chunk kwam in 5 van 5 medium-runs mee; met kopjespad in 0 van 5. |
| 5 | **Het model bepaalt de zoekopdracht.** mistral-medium doet steeds 1 zoekactie, mistral-large 5–10. Promptinstructies als "zoek per kopje" of "volg verwijzingen" negeert medium (0 van 5 groen). | `out_h2gen_*.txt` |
| 6 | **Vervolgvragen zonder nieuwe retrieval.** In conversatie 10 zocht de bot alleen in beurt 1; beurt 2–5 zijn gebouwd op oude chunks plus invulling (zo kwam "LJC" erin). | `python scripts/trace_conversation.py <id uit feedback-rapport>` toont per beurt de tools. |
| 7 | **Kruisverwijzingen over documenten heen.** Titel 20 art. 20.2.008 zegt "de deelnameprocedure staat in de Nationale Besluiten". Een LLM "volgt" een verwijzing alleen met een nieuwe zoekactie, en die vindt weer verweesde chunks. | `knowledge-documents/knwu/TITEL_20-Jeugdwielrennen_20260921.md` art. 20.2.008. |
| 8 | **Niet-determinisme.** Dezelfde vraag aan large is in ongeveer 1 op 3 runs fout. Eén keer testen bewijst dus niets; je hebt een reproductiekans nodig. | Baseline: large 3 van 4, medium 1 van 5 groen. |

Experimentresultaten (5 runs per variant, scenario "kwalificeren NK weg" + "2015"; groen = LJT genoemd, "2 wedstrijden" genoemd, geen LJC):

| Variant | Groen |
|---|---|
| Productie, large | 3 van 4 (1 run crashte) |
| Medium (zoals conversatie 10) | 1 van 5 |
| Prompt "volg verwijzingen / zoek per kopje" (generiek) | 0 van 5 |
| Prompt "kwalificatie heet selectieprocedure" | 1 van 5 |
| **Markdown met kopjespad in elke kop** (prototype) | **4 van 5**; MTB-chunk 0 van 5, alle wegchunks 10 van 10 opgehaald |
| Kopjespad + "noem procedures volledig" | 2 van 5 |

Kernles voor de leerstof: **de kwaliteit wordt grotendeels bepaald vóórdat het model iets ziet**, namelijk in de documentvoorbereiding (structuur, chunk-context). Promptregels compenseren dat slecht.

## Bruikbare artefacten (session-map, buiten de repo)

`C:\Users\Ivo.Stieltjes_nsp\.copilot\session-state\8b5106bf-9f06-46b2-8eaa-0f0beb9bb159\files\`

- `nk_loop.py`: één testconversatie tegen de knwu-agent, of inline met `NK_INLINE=1 NK_MODEL=… NK_EXTRA=<promptbestand> NK_LIB=<library-id>`. Print de queries, welke stukken opgehaald zijn (markers) en de OK/RED-checks.
- `runner.ps1 -Scenario conv11 -N 5 -Tag x`: N parallelle runs met een score.
- `enrich_nb.py`: prototype dat koppen uit de PDF-opmaak haalt en markdown-koppen met pad schrijft (253 van 257 koppen gematcht).
- `snippets.txt`: de echte opgehaalde chunks van conversatie 10. Ideaal lesmateriaal om te laten zien hoe een chunk eruitziet.
- `out_*.txt`: ruwe uitvoer per experiment.

Zie hoe Mistral zoekresultaten teruggeeft: in de conversation-history (`GET /v1/conversations/{id}/history`, entries `tool.execution` → `info.result`) staan **snippets alleen bij mistral-medium**, bij large alleen titel en beschrijving. Gebruik dus medium als je retrieval wilt laten zien.

## Openstaand en blokkades

- **Mistral gaf HTTP 402 Payment Required** aan het einde van de sessie (bestedingslimiet). Live demo's of experimenten werken pas weer na ophoging. Controleer eerst of de productiebot nog draait. De tijdelijke testlibrary `wtc-test-nk7` is al verwijderd.
- **Fix gebouwd (2026-11-13), nog niet live.** `scripts/clean_pdf.py` schrijft koppen met kopjespad (profielen in `scripts/kopprofielen.json`) en splitst Titel 20 en de Nationale Besluiten met `--split` per hoofdstuk; de documenten in `knowledge-documents/knwu/` zijn opnieuw gegenereerd. Zie het amendement van 2026-11-13 in `docs/adr/0005-library-bevat-alleen-actuele-versies.md`. Nog te doen zodra het Mistral-tegoed werkt: library-sync, `create_agents.py --apply` (bronvoorbeelden in de prompts) en de eval-entry `knwu-nk-weg-jeugd-kwalificatie`. De leerstof kan dit als "zo lossen we het op" gebruiken: vergelijk een chunk uit `snippets.txt` met dezelfde passage in `Nationale_Besluiten_20260918 - 2. WEGWIELRENNEN.md`.
- Er is nog geen eval-entry voor dit knwu-scenario. `regio-nk-kwalificatie` in `eval/evalset.yaml` verwacht al "LJT".

## Aanpak voor de leerstof (suggestie)

- Volg `docs/DOCUMENTATION_GUIDE.md` (Diátaxis). Waarschijnlijk een **tutorial** ("Volg één vraag door de RAG-pijplijn van Wielie") plus een **explanation** ("Waarom RAG-antwoorden incompleet worden: chunking, retrieval, generatie"). Bekijk het bestaande leerplan `docs/knwu-kennischatbot-leerplan.md` en de map `lessons/` (nu leeg) of `docs/tutorials/` voor de plek. Vraag het de gebruiker als het niet duidelijk is.
- Laat de gebruiker **zelf** dingen zien: één chunk uit `snippets.txt` lezen en raden waar hij bij hoort; de PDF-pagina 31–33 naast de markdown leggen; `trace_conversation.py` draaien; (na de 402) `runner.ps1` met medium tegen de huidige library.
- Behandel ook de vragen die de gebruiker zelf stelde, als denkoefening met het antwoord uit de experimenten: "prioriteren Handboek → NB → Titel 20?", "altijd alle drie raadplegen?", "altijd verwijzingen volgen?", "documenten per hoofdstuk opslaan?", "eenmalig onderzoek opslaan als document?" (zie `knowledge-documents/ik-wil-weten-hoe-de-licentiestructuur-en-wedstrijd.md` als voorbeeld van zo'n samengevat document, met het risico van een tweede bron van waarheid).
- Begrippen eerst afstemmen met `GLOSSARY.md` (Bibliotheek, Opgeschoonde versie, Opschoonrapport, Eval-set, Reviewronde). Nieuwe termen als *chunk*, *verweesde chunk*, *kopjespad*, *top-k* en *reproductiekans* kunnen in de GLOSSARY, via de skill `domain-modeling`.
- Leg niet uit hoe Mistral precies chunkt alsof het vaststaat. Gemeten is: snippets van ~1900–2000 tekens en 10 per zoekactie. De rest is onbekend; laat de `research`-skill primaire bronnen (Mistral-docs) zoeken als je het wilt onderbouwen.

## Suggested skills

- **write-documentation**: verplicht voor alles in `docs/` (Diátaxis, repo-conventies).
- **research**: om Mistral-documentatie over libraries, chunking en document_library te verifiëren voordat je beweringen in de leerstof zet.
- **domain-modeling**: als er nieuwe RAG-termen in `GLOSSARY.md` komen.
- **grilling**: optioneel, om na de leerstof het begrip van de gebruiker te toetsen.
- Later, voor de fix: **tdd** (seams S1–S3 hierboven) en **diagnosing-bugs** (de loop in de session-map hergebruiken).
