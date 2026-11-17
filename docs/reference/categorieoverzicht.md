# Categorieoverzicht

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Het categorieoverzicht is de [deterministische bypass](../../GLOSSARY.md) die leeftijdscategorie, oude categorie-indeling, maximaal toegestaan verzet en licentie in één antwoord toont (#102). Deze pagina somt invoer, beslissingen, seizoensregels, lookup-toestand, data en antwoordvorm op. Waarom de route zo loopt staat in [Hoe een vraag geroute wordt](../explanation/vraag-routing.md). Het toestandsmodel is besloten in [#125](https://github.com/Atrium0804/WTChatbot/issues/125#issuecomment-6930100869), de antwoordopmaak in de [ontwerpwijziging van #102](https://github.com/Atrium0804/WTChatbot/issues/102#issuecomment-6910594855).

## Operaties

Alle drie in `app/lookups.py`, puur (geen netwerk, geen LLM). Datum en regels worden geïnjecteerd.

| Operatie | Invoer | Uitvoer |
| --- | --- | --- |
| `recognize_turn(message, previous_state, today, rules)` | bericht, lookup-toestand van de conversatie (of `None`), appdatum, `knwu_categories.load_rules()` | `Ready` \| `NeedsInformation` \| `NotEligible`, elk met `next_state` |
| `complete_with_intake(needs_information, intake_result, today, rules)` | alleen een `NeedsInformation`; anders `TypeError` | `Ready` \| `NeedsInformation` \| `NotEligible` |
| `render_answer(ready, language_level)` | alleen een `Ready`; anders `TypeError`. `language_level` `B1` of `B2` | markdown-antwoord |

Aanroepers: `POST /chat` en `_run_chat_job` in `app/main.py`, `decide_route` in `app/intake.py`, `plan_entry` in `eval/run_eval.py`.

## Beslissingen

| Beslissing | Wanneer | Volgende toestand | Route |
| --- | --- | --- | --- |
| `Ready` | herkende lookup met complete, consistente invoer en minstens één passende regel; ook de losse lookup KNWU Licentie 17+ en een geboortejaar buiten de jeugdindeling | `completed` | `bypass`, 0 LLM-calls |
| `NeedsInformation` | herkende lookup zonder hoofdingang, of met één jaartal dat alleen de intake als geboortejaar kan bevestigen (bijv. "Welk verzet? 2012") | `pending` | intake; `bypass` (`intake_lookup`) alleen als `complete_with_intake` `Ready` geeft |
| `NotEligible` | alles wat niet positief herkend is, zie [Niet in de bypass](#niet-in-de-bypass) | `none` | inhoudelijke route (`direct-<domein>` of `router`) |

## Invoer

### Hoofdingang

Precies één hoofdingang per bericht.

| Hoofdingang | Herkende vormen | Voorbeeld |
| --- | --- | --- |
| Geboortejaar | kaal jaartal als heel bericht; `geboortejaar NNNN`; `geboren (in) NNNN`; `uit NNNN`; `voor NNNN` | "2014", "jongen uit 2015" |
| Oude categorie | `categorie N`, `cat. N`, `cat N` (N = 1 t/m 7) | "Wat is cat. 3?" |
| Nieuwe leeftijdscategorie | `U<n>`, `JO<n>`, `MO<n>`, `MU<n>`, `VU<n>`; "nieuweling(en)" | "U11", "JO11/MO12", "MU12, VU13" |
| Losse licentie | "licentie 17+" met een vraagwoord | "Welke KNWU Licentie 17+ is nodig?" |
| Alleen gegevens | een bericht met alleen herkende gegevens, gescheiden door komma's, "en" of spaties: geslachtswoord, geboortejaarvorm (ook een kaal jaartal), categorie, oude categorie, discipline. Minstens één hoofdingang; elk ander woord geeft `NotEligible` | "jongen uit 2015, U12, weg", "2015, meisjes" |

Een geboortejaar samen met een categorie: het geboortejaar is de hoofdingang, de categorie een extra filter. Een oude en een nieuwe categorie samen: de oude categorie is de hoofdingang, de nieuwe een filter.

### Filters en normalisatie

| Gegeven | Herkende vormen | Effect |
| --- | --- | --- |
| Geslacht | jongen(s), zoon / meisje(s), dochter | filter; ontbreekt het, dan beide |
| Discipline | weg, de weg, op de weg, wegwielrennen / veld, het veld, in het veld, veldrijden, veldrit, cross | filter; ontbreekt het, dan beide |
| Prefix `JO`, `MU` | | jongens |
| Prefix `MO`, `VU` | | meisjes |
| Prefix `U` | | geen geslachtsfilter |
| `U16` | | wordt `U17 Nieuweling` |
| Gecombineerde categorie | precies twee categorieën, één jongens en één meisjes (`JO11/MO12`) | blijft een paar: jongens U11 en meisjes U12, geen kruisproduct |
| `KNWU Licentie U13` | U-aanduiding direct na "licentie" | geen categoriefilter |

### Niet in de bypass

Deze invoer geeft `NotEligible`. De intake maakt er nooit een bypass van.

| Invoer | Voorbeeld |
| --- | --- |
| Uitleg, bron, versie, kosten, procedure, uitzondering, combinatiewedstrijd, hoger starten (`MEER_DAN_FEIT`) | "Waarom rijdt mijn zoon in U12?" |
| Reglementsonderwerp: wedstrijd, NK, meedoen, verzekering, contributie, dispensatie … (`REGELMENT_ONDERWERP`) | "Mag een kind van 6 meedoen met nationale wedstrijden?" |
| Andere discipline: baan, MTB, BMX (`BUITEN_SCOPE_DISCIPLINE`) | "Welk verzet voor U9 op de baan?" |
| Meerdere renners (`MULTIPLE_RIDERS`) | "Welke categorie voor mijn twee zoons geboren in 2015?" |
| Weg én veld in één bericht, of jongens én meisjes | "Welk verzet voor U11 op de weg en in het veld?" |
| Geslacht in tegenspraak met de prefix | "Welke categorie voor JO11 meisjes?" |
| Meer dan één geboortejaar, of meer categorieën dan één paar | "Welke categorie voor JO11 en U12?" |
| Leeftijd in jaren in plaats van geboortejaar | "Welke categorie voor een 12-jarige?" |
| Expliciet wedstrijdjaar of seizoen | "Welke categorie voor geboortejaar 2015 in 2025?" |
| Onbekende categorie | "Wat is categorie 8 in de nieuwe indeling?" |
| Geboortejaar na het huidige jaar | |
| Invoer die na filteren nul regels overhoudt | "Welke categorie voor geboortejaar 2015 en jongens U11?" |

## Seizoensregels

### Kandidaatseizoenen

Appdatum in jaar J. Het overzicht toont de twee seizoenen in deze volgorde. Dit is een selectieregel, geen definitie van de officiële wedstrijdseizoenen.

| Appdatum | Eerste seizoen | Tweede seizoen |
| --- | --- | --- |
| januari–februari | veld J-1/J | weg J |
| maart–september | weg J | veld J/J+1 |
| oktober–december | veld J/J+1 | weg J+1 |

### Regels per seizoen

| Regel | Waarde |
| --- | --- |
| [Peiljaar](../../GLOSSARY.md) weg | het wedstrijdjaar |
| Peiljaar veld | het eindjaar van het [veldritseizoen](../../GLOSSARY.md) |
| Leeftijd | peiljaar − geboortejaar |
| Leeftijdsbereik | 5 t/m 16; regels daarbuiten vallen weg |
| Categorie zonder geboortejaar | geboortejaren per seizoen afgeleid; kan per seizoen verschillen (jongens U12: weg 2026 → 2015, veld 2026-2027 → 2016) |
| Licentie | per kalenderjaar, onafhankelijk van discipline en geslacht; wisselt die binnen een veldritseizoen, dan "t/m dec J" en "vanaf jan J+1" |
| Oude categorie 1 | jongens U8/U9 en meisjes U9/U10; de kop toont "Oude cat. 1 (JO9/MO10)" |
| Geboortejaar buiten de jeugd | geen regels, geen jeugdcategorie en geen jeugdlicentie in het huidige jaar → `Ready` met "valt buiten de jeugdindeling" |
| Toekomstig seizoen | laatst bekende regels, met het vooruitblikvoorbehoud; geen geldigheidslogica |

## Lookup-toestand

Per conversatie in het geheugen van de app (`lookup_states` in `app/main.py`), los van de feedbackgeschiedenis. Bewaart gevalideerde invoer, geen berekende regels of antwoordtekst.

| Toestand | Inhoud |
| --- | --- |
| `none` | geen profiel |
| `pending` | herkende vraag zonder hoofdingang; bewaarde filters |
| `completed` | gevalideerd profiel: hoofdingang (geboortejaar, categorie, paar of oude categorie), geslacht, discipline, extra categoriefilters |

### Overgangen

| Bericht na een profiel | Resultaat |
| --- | --- |
| Nieuwe hoofdingang als kort vervolg ("2017", "en voor 2017?", "U13", "cat. 4", "jongen uit 2017") | vervangt geboortejaar- en categoriefilters; geslacht en discipline blijven tenzij het bericht ze noemt |
| "alleen meisjes" na `JO11` | meisjes U11 |
| "alleen meisjes" na `JO11/MO12` | alleen meisjes U12 |
| "alleen meisjes" na een oude categorie | de meisjescategorieën van die oude categorie |
| "alleen veldrijden" / "weg" | vervangt alleen de discipline |
| Kaal jaartal na `pending` ("Welk verzet?" → "2012") | volledig overzicht, beide disciplines |
| Complete zelfstandige vraag | erft niets |
| Afgewezen of inhoudelijke beurt ("Waarom?") | toestand `none`; een later fragment grijpt niet terug |

### Revisie

| Moment | Gedrag |
| --- | --- |
| Geaccepteerd `POST /chat` | revisie +1 en de nieuwe toestand vastgelegd vóór enige `await` |
| Rate-limited of ongeldig verzoek | geen beurt, geen revisie |
| Background job met intake-aanvulling | publiceert alleen als zijn revisie nog de nieuwste is; anders trace-event `lookup_state` met `reason: stale_revision` |

## Verzetdata

`app/knwu_categories.json`, sectie `verzetten`:

| Sleutel | Inhoud |
| --- | --- |
| `bron`, `versie`, `artikel` | Titel 20 hoofdstuk 1, versie 2026-09-21, art. 20.1.007 |
| `per_geslacht.jongens.<categorie>.<discipline>` | meters (getal), `"vrij"` of `null` (NVT) |
| `per_geslacht.meisjes.<categorie>.<discipline>` | idem |
| `correcties` | goedgekeurde broncorrecties met `bronwaarden`, `brondocument`, `bronpagina`, `artikel` en `toelichting` |

Disciplines in de data: `weg`, `veld` en `baan`. `baan` staat er alleen voor de driftcontrole; het antwoord toont alleen weg en veld.

`knwu_categories.max_gear(category, discipline, gender, rules)` vereist een expliciet geslacht en geeft een `ValueError` bij onbekende invoer. `None` is alleen een geldige NVT-bronwaarde.

### Broncorrectie

| Geslacht | Categorie | Discipline | Waarde | Bron |
| --- | --- | --- | --- | --- |
| meisjes | U9 | veld | vrij | Titel 20 PDF, pagina 8, art. 20.1.007: meisjes U9 staat dubbel, met veld NVT en veld vrij |

`tests/test_knwu_categories.py` vergelijkt beide geslachtskolommen met de bron en staat alleen deze ene dubbele rij toe.

## Antwoordvorm

| Onderdeel | Vorm |
| --- | --- |
| Kop | `**Geboortejaar 2014**`, `**Oude cat. 3 (JO11/MO12)**`, `**JO11/MO12**`, `**JO11**` of `**U11**` |
| Blokkop | `### <Discipline> <seizoen> · <Jongens\|Meisjes>`; bij categorie-invoer `· geboortejaar NNNN` erachter |
| Volgorde | seizoenen chronologisch, jongens vóór meisjes, oplopend geboortejaar |
| Regels per blok | `- **Categorie:** U14 (oude cat. 5)` of `(oude cat. n.v.t.)`; `- **Verzet:** 6,30 meter`, `vrij` of `NVT (niet van toepassing)`; `- **Licentie:** U13 (t/m dec 2026), U17 (vanaf jan 2027)` |
| Slot | vooruitblikvoorbehoud, de slotvraag "Moet ik de KNWU-documenten doorzoeken voor een gedetailleerder antwoord?" (`DISCLAIMER_LIBRARY`), één `Bron:`-regel als laatste regel |
| Opmaak | geen ingesprongen lijstregels; de renderer blijft ongewijzigd |

### Bronregel

Ook bij B1, als gerichte uitzondering op [ADR-0009](../adr/0009-agent-architectuur-snelheid.md). Elk document staat één keer in de regel; de clubbron is gelabeld.

| Taalniveau | Bronregel bij het overzicht |
| --- | --- |
| B1 | `Bron: TITEL_20-Jeugdwielrennen_20260921 - ALGEMENE BEPALINGEN.md, versie 2026-09-21; TITEL_20-Jeugdwielrennen_20260921 - Hoofdstuk 1 - WEDSTRIJDEN, ALGEMEEN.md, versie 2026-09-21; WebsiteWTCjeugd: website-tekst KNWU - leeftijdscategorieën (clubbron, oude indeling)` |
| B2 | dezelfde regel met artikelen: `(artikel 20.0.004 en artikel 20.0.002)` achter ALGEMENE BEPALINGEN, `(artikel 20.1.007)` achter Hoofdstuk 1 |

De losse lookup KNWU Licentie 17+ noemt alleen ALGEMENE BEPALINGEN, bij B2 met artikel 20.0.002.

## Tests

| Bestand | Dekt |
| --- | --- |
| `app/tests/test_lookups.py` | herkenning, profielovergangen, seizoenen, antwoordvorm en bronregel |
| `app/tests/test_app.py` | vervolgvragen, revisievolgorde en 0 modelcalls via `POST /chat` |
| `app/tests/fixtures/routecontract.yaml` | route per gesprek |
| `app/tests/test_intake.py` | `decide_route` met de drie beslissingen |
| `tests/test_knwu_categories.py` | driftcontrole van de data tegen Titel 20 |
| `tests/test_run_eval.py` | eval-replay van `beurten` en de bypass-entries met de `peildatum` |
