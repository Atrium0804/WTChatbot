# Handoff: Oplossen Feedback-Kwaliteitsproblemen WTChatbot

**Datum:** 2026-11-11  
**Vorige agent:** Mistral Vibe (analyse gesprek)  
**Volgende agent:** [te bepalen]  
**Status:** Onderzoek afgerond, implementatie vereist

---

## 📌 Samenvatting Probleem

Uit analyse van **22 negatieve feedback-items** (6-11 nov 2026) blijkt dat de WTChatbot-agents **systematisch de regels uit `_shared.md` niet volgen**, wat leidt tot:

1. **Tone of Voice overtredingen** (item 20)
2. **Verzonnen feiten** (items 11, 13, 22)
3. **Verouderde data** (items 2, 3, 8, 16, 17, 21)
4. **Foute bronvermeldingen** (items 7, 9, 12, 15)
5. **Overbodige informatie** (items 1, 4, 12, 20)

---

## 🔍 Root Cause Analyse

### ✅ Bevestigde oorzaken:

#### 1. **Router-agent mist `_shared.md` in prompts** (100% bevestigd)
- **Locatie:** `scripts/agents_config.json`
- **Huidige config:**
  ```json
  {
    "name": "router-agent",
    "prompt_files": ["router-agent.md"]  // ❌ MISSING: "_shared.md"
  }
  ```
- **Impact:** 
  - Item 20: `"Hoi! Waar kan ik je mee helpen? 😊"` (emoji + informeel)
  - Router-agent volgt geen "Verzin niets", "Toon en stijl", etc.

#### 2. **Agents niet herdeployed na `_shared.md` updates** (hoog waarschijnlijk)
- `_shared.md` bestaat sinds voor issue #44 (2026-11-09)
- knwu/regio/club/archief **hebben wel** `_shared.md` in config
- MAAR: Als `create_agents.py --apply` niet draaide, gebruiken Mistral-agents **oude prompts**
- **Impact:** Alle overtredingen behalve Tone of Voice

#### 3. **Libraries niet gesynct** (waarschijnlijk)
- regio-agent gebruikt `regio`-library
- Als library **oude MNC/Hans van den Hengel data** bevat, geeft agent verouderde antwoorden
- **Impact:** Items 2, 3, 8, 16, 17, 21

#### 4. **Contextregels niet gerespecteerd** (onbevestigd)
- App zou contextregels met `vandaag` moeten sturen
- Agents **moeten** past dates filteren per `_shared.md`:
  > "De datum in dat blok is vandaag. Een datum vóór vandaag ligt in het verleden. Vraagt de gebruiker naar de volgende of komende wedstrijd, noem dan alleen data vanaf vandaag"
- **Vermeden:** Items met data in verleden (2, 3, 8, 16, 17, 21)

---

## ✅ Werk Al Gedaan

### Analyse
- [x] 22 negatieve feedback-items geanalyseerd
- [x] Patroonanalyse per oorzaak (5 categorieën)
- [x] Agent traces uitgevoerd voor 10+ conversaties
- [x] `_shared.md` en alle agent-prompts gelezen
- [x] `agents_config.json` geïnspecteerd
- [x] Root causes geïdentificeerd

### Bevindingen
- **router-agent**: Mist `_shared.md` → Tone of Voice probleem
- **knwu-agent**: Heeft `_shared.md` maar gebruikt verouderde data/foute bronnen
- **regio-agent**: Heeft `_shared.md` maar geeft verouderde wedstrijddata
- **Alle agents**: Mogen niet herdeployed zijn met actuele prompts

---

## 🎯 Wat Moet Gebeuren (Volgende Stappen)

### 🔴 **Criticaal (Direct uitvoeren)**

#### 1. Fix `agents_config.json`
**File:** `scripts/agents_config.json`

**Wijziging:**
```json
{
  "name": "router-agent",
  "description": "Router-agent: bepaalt het vraagtype (KNWU/regio/club) en doet de handoff",
  "prompt_files": ["_shared.md", "router-agent.md"],  // ✅ VOEG "_shared.md" TOE
  "handoffs": ["knwu-agent", "regio-agent", "club-agent"]
}
```

**Verificatie:**
```bash
cd /c/git_prive/WTChatbot
grep -A 5 '"name": "router-agent"' scripts/agents_config.json
```

#### 2. Herdeploy alle agents
**Command:**
```bash
cd /c/git_prive/WTChatbot
.venv\Scripts\python scripts\create_agents.py --apply
```

**Verificatie:**
- Controleer output: alle 5 agents moeten "updated" zijn
- Noteer nieuwe agent IDs in `.env` (MISTRAL_AGENT_ID, MISTRAL_AGENT_ID_KNWU, etc.)

#### 3. Sync alle libraries
**Command:**
```bash
cd /c/git_prive/WTChatbot
.venv\Scripts\python scripts\sync_libraries.py --apply
```

**Verificatie:**
- Controleer dat `knwu`, `regio`, `club`, `archive` libraries up-to-date zijn
- Check document versies in Mistral library dashboard

### 🟡 **Important (Binnen 1 week)**

#### 4. Verifieer contextregels implementatie
- **App-side:** Check of app daadwerkelijk contextregels met `vandaag` meestuurd
- **Test:** Start een testconversatie en check of agents past dates filteren
- **Debug:** Gebruik `trace_conversation.py` om contextregels in de input te zien

**Testcommando:**
```bash
.venv\Scripts\python scripts\trace_conversation.py --date 2026-11-11
```

#### 5. Valideer document content
- **Focus:** knwu-agent en regio-agent libraries
- **Check:**
  - Zitten er **doorgehaalde waarden** in documenten? → Moeten verwijderd
  - Zitten er **verouderde datums** in? → Moeten geüpdatet
  - Zitten er **conflicterende regels** in? → Moeten opgelost

#### 6. Test met bekend probleem
**Testcase:** Vraag naar "volgende MNC wedstrijd"

**Expected:**
- Geen data vóór vandaag (2026-11-11)
- Alleen toekomstige datums
- Zakelijke toon (geen emoji's, "Hoi!", etc.)

**Actual (voor fix):**
- Data in verleden (bv. 5 april 2026, 6 september 2026)

---

## 📋 Suggested Skills voor Volgende Agent

1. **`code-review`** - Review de wijzigingen in `agents_config.json` en verifieer de deploy
2. **`tdd`** - Schrijf tests voor de kritische scenario's (Tone of Voice, past dates, etc.)
3. **`diagnosing-bugs`** - Als problemen blijven: diepgaande debug van agent prompts en contextregels

---

## 📊 Success Metrics

| Metric | Doel | Meetmethode |
|--------|------|-------------|
| Tone of Voice compliance | 0 overtredingen | Handmatige review nieuwe feedback |
| Geen verouderde data | 0 items | Feedback analyse |
| Geen verzonnen feiten | 0 items | Feedback analyse |
| Agent prompt compliance | 100% | Code review `agents_config.json` |

---

## 🔗 Gerelateerde Resources

- **Feedback bron:** `wielie-feedback.md` (22 negatieve items)
- **Config:** `scripts/agents_config.json`
- **Prompts:** `scripts/prompts/`
- **Scripts:** 
  - `scripts/create_agents.py` (deploy agents)
  - `scripts/sync_libraries.py` (sync document libraries)
  - `scripts/trace_conversation.py` (debug conversaties)
- **Issue:** #44 (contextregels geïntroduceerd)
- **Documentatie:** `docs/how-to/raadpleeg-feedback-voor-triage.md`

---

## ⚠️ Risico's & Afhankelijkheden

| Risico | Impact | Mitigatie |
|--------|--------|-----------|
| Agents niet herdeployed | Problemen blijven | Verifieer deploy output |
| Libraries niet gesynct | Verouderde data blijft | Verifieer library sync |
| Contextregels niet werkend | Past dates blijven | Test met trace_conversation.py |
| Nieuwe bugs geïntroduceerd | Regressie | Test voor en na deploy |
| MISTRAL_API_KEY ontbreekt | Deploy mislukt | Check `.env` file |

---

## 💡 Aannames

1. Mistral API key in `.env` is geldig en heeft voldoende rechten
2. `create_agents.py` en `sync_libraries.py` werken correct
3. Document libraries bevatten de juiste bronnen
4. Contextregels worden door de app gestuurd (moet geverifieerd)
5. Feedback database wordt niet gereset tijdens deploy

---

## ✅ Acceptatie Criteria

- [ ] `scripts/agents_config.json` heeft `"_shared.md"` in router-agent `prompt_files`
- [ ] Alle 5 agents zijn herdeployed met `create_agents.py --apply`
- [ ] Alle libraries zijn gesynct met `sync_libraries.py --apply`
- [ ] `.env` bevat geüpdate agent IDs
- [ ] Testconversatie toont **geen** Tone of Voice overtredingen
- [ ] Testconversatie toont **geen** data in verleden
- [ ] Testconversatie toont **geen** verzonnen feiten
- [ ] Testconversatie volgt **alle** regels uit `_shared.md`

---

## 📝 Notities

- Feedback items 1-6 (vóór 2026-11-09) kunnen **niet** getraced worden met `app_conversation_id` (pre-#44)
- Gebruik `--date` flag voor deze: 
  ```bash
  .venv\Scripts\python scripts\trace_conversation.py --date 2026-11-06
  ```
- Post-#44 items (7-22) kunnen **wel** direct getraced worden met `app_conversation_id`
- Voor debug: Gebruik `trace_conversation.py <conversation-id>` voor gedetailleerde agent flow

---

**Einde handoff document**  
**Locatie:** `C:/Temp/wtchatbot-feedback-fix-handoff.md`