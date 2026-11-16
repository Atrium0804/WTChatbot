# Research: verlaagde reasoning en modelopties bij Mistral (Conversations API met tools/handoffs)

- **Issue:** #129 (kind van map #128)
- **Datum:** 16 november 2026
- **Bronnen:** docs.mistral.ai (model-cards, reasoning, pricing, lifecycle, tools, handoffs) en de broncode van de `mistralai` Python-SDK (lokaal geïnstalleerd: 3.6.0, de versie in `requirements.txt`; vergeleken met `main` op GitHub, laatste release v3.7.0).

## Kort antwoord

1. **Onze huidige config reasont al op het hoogste niveau.** `mistral-large-latest` is een alias van **Mistral Large 4** (`mistral-large-4-0`). Dat model reasont **altijd**. Zonder `reasoning_effort` geldt `high`. [R1] [M1]
2. **De reasoning-schakelaar is `reasoning_effort`.** Je zet die per agent in `completion_args`, en die werkt ook in de Agents- en Conversations-endpoints. [R1] [S1] `prompt_mode` hoort bij de oude Magistral-modellen. Het zit niet in `CompletionArgs`, dus je kunt het niet per agent zetten. [D1] [S2]
3. **Toegestane waarden verschillen per model:**
   - **Large 4:** `low`, `medium` of `high`. Geen `none`.
   - **Small 4 (`mistral-small-2603`)** en **Medium 3.5:** `none` tot en met `high`. Met `none` denkt het model minimaal en komt er geen thinking-chunk mee. [R1]
4. **Magistral is uit productie.** Alle Magistral-modellen zijn deprecated of retired. De vervangers zijn Small 4 of Medium 3.5 met `reasoning_effort`. [D1] [O1]
5. **Ministral 3 is niet gedocumenteerd voor Agents en Built-In Tools.** De model-cards van Ministral 3 (3B/8B/14B) noemen "Agents & Conversations" en "Built-In Tools" niet. Die van Small 4, Large 4, Medium 3.5 en Large 3 doen dat wel. [M2] [M3] [M4] [M5]
6. **Mistral publiceert geen TTFT-cijfers.** Reasoning-tokens komen wel vóór het antwoord, dus een hogere effort betekent later het eerste antwoordtoken. [R1]

## 1. Model-ids (gepind, zonder `-latest`) en deprecations

Mistral benoemt nieuwe modellen volgens `model-name-major-minor`. Aliassen zijn `-latest` (over generaties heen) en `-major`. "Using an alias may expose you to silent updates in model behavior and pricing." GA-modellen krijgen 6 maanden deprecation-termijn. Na retirement geeft het model een `404`. [L1]

| Familie | Model | Gepinde id | Aliassen | Status | Reasoning |
| --- | --- | --- | --- | --- | --- |
| large | Mistral Large 4 (v26.10, 5 nov 2026) | `mistral-large-4-0` | `mistral-large-4`, `mistral-large-latest` | GA | altijd aan: `low`/`medium`/`high` (default `high`) |
| large | Mistral Large 3 (v25.12) | `mistral-large-2512` | geen | Deprecated 31-10-2026, retired 30-04-2027 → Large 4 | geen (instruct; model-card linkt alleen chat-completion) |
| medium | Mistral Medium 3.5 (v26.04) | `mistral-medium-3-5` | `mistral-medium-3`, `mistral-medium-latest` | Deprecated 31-10-2026, retired 30-04-2027 → Large 4 | `reasoning_effort` (incl. `none`) |
| medium | Mistral Medium 3.1 / 3 | `mistral-medium-2508` / `mistral-medium-2505` | geen | retired 31-08-2026 | n.v.t. |
| small | Mistral Small 4 (v26.03) | `mistral-small-2603` | `mistral-small-latest` | GA | `reasoning_effort` (incl. `none`) |
| small | Mistral Small 3.2 | `mistral-small-2506` | geen | retired 31-07-2026 | n.v.t. |
| ministral | Ministral 3 14B / 8B / 3B (v25.12) | `ministral-14b-2512` / `ministral-8b-2512` / `ministral-3b-2512` | `ministral-{14b,8b,3b}-latest` | GA | geen (model-card linkt alleen chat-completion) |
| magistral | Magistral Medium 1.2 / Small 1.2 | `magistral-medium-2509` / `magistral-small-2509` | `magistral-*-latest` | retired 31-07-2026 → Medium 3.5 / Small 4 | n.v.t. |

Bronnen: modellenoverzicht met deprecation-tabel [O1], model-cards [M1]–[M5], native reasoning (deprecated) [D1]. De aliassen staan in de `names`-lijst van elke model-card-pagina.

Gevolgen voor `scripts/architectures/huidig.json`:

- `"model": "mistral-large-latest"` wijst sinds de release van Large 4 (5 nov 2026) naar `mistral-large-4-0`. Dat model reasont standaard op `high`.
- De router-agent gebruikt `mistral-small-latest`, en dat wijst naar `mistral-small-2603`.
- Mistral documenteert niet wat Small 4 zonder `reasoning_effort` doet. Zet de waarde daarom expliciet.

## 2. Reasoning-schakelaar en hoe je die per agent zet

### `reasoning_effort` (actueel)

- **Enum in de SDK:** `none`, `minimal`, `low`, `medium`, `high`, `xhigh` en `max` (`mistralai/client/models/reasoningeffort.py`). [S1] Dat een waarde in de enum staat, betekent niet dat elk model die accepteert. [R1]
- **Small 4 en Medium 3.5:**
  - `high`: er komt een volledige thinking-chunk vóór het antwoord.
  - `none`: het model "thinks minimally and the thinking chunk is omitted from the response". [R1]
- **Large 4:** alleen `low`, `medium` en `high`. "Mistral Large 4 does not accept `none`, `minimal`, `xhigh`, or `max`." Daarnaast: "Mistral Large 4 always reasons … Use `low` for the least reasoning. It still returns a thinking chunk and uses reasoning tokens." [R1]
- **Agents en Conversations:** "`reasoning_effort` is also available on the Agents and Conversations endpoints via the API, inside the `completion_args` field." [R1]
- **In de SDK** is `reasoning_effort` een veld van `CompletionArgs` ("White-listed arguments from the completion API"). Dat geldt zowel voor de geïnstalleerde 3.6.0 als voor `main`. [S1] `client.beta.agents.create/update` en `client.beta.conversations.start/append` accepteren `completion_args`. [S3]

### `prompt_mode` (verouderd)

`prompt_mode` (`"reasoning"` of `null`) bepaalde alleen de standaard-systeemprompt van de Magistral-modellen. [D1] De parameter bestaat in de SDK op `ChatCompletionRequest` en `AgentsCompletionRequest`, maar **niet** in `CompletionArgs`. [S2] Je kunt hem dus niet per agent of conversation zetten. Voor ons is hij niet relevant meer.

### Wat er in `scripts/create_agents.py` ontbreekt

Het script stuurt bij elke agent dezelfde globale `config["completion_args"]` mee. Per agent kun je alleen `model` overschrijven (#83). Per-agent reasoning vraagt dus een kleine uitbreiding: een optionele per-agent `completion_args` (of alleen `reasoning_effort`) die over de globale heen wordt gemerged. Dit volgt hetzelfde patroon als de model-override.

De app filtert `thinking`-chunks al uit `message.output` (`app/mistral_client.py`). Reasoning-output breekt de antwoordextractie dus niet.

## 3. Tool-ondersteuning van kleinere modellen

- **Built-in tools hebben de Conversations- of Agents-API nodig.** `web_search` (en `web_search_premium`, `code_interpreter`) werken alleen daar, niet in Chat Completions. [T1] [W1] De websearch-pagina zegt dat de tool "allows any of our models to access the web". [W1]
- **De model-cards verschillen in wat ze noemen.** Per model noemen de cards "Agents & Conversations" en "Built-In Tools" als feature:
  - **Large 4:** ja [M1]
  - **Small 4:** ja [M2]
  - **Medium 3.5:** ja [M4]
  - **Large 3:** ja [M5]
  - **Ministral 3 14B (en 8B/3B):** nee, alleen Function Calling, Structured Outputs, Document QnA, Chat Completions en Batching [M3]

  Voor `document_library` en handoffs is Ministral dus **niet** officieel gedocumenteerd.
- **Handoffs:** de handoffs-pagina gebruikt `mistral-large-latest` als voorbeeld. Mistral noemt geen modelrestricties en publiceert geen betrouwbaarheidscijfers per model. [H1]
- **Conclusie:** voor `document_library`, `web_search` en handoffs is **Small 4 (`mistral-small-2603`) de kleinste gedocumenteerde optie**. Hoe betrouwbaar die tool-calls zijn (juiste handoff, wel of niet zoeken), publiceert Mistral niet. Dat moet onze eigen eval-set uitwijzen. Hier ligt ook het raakvlak met #131.
- **Let op:** de tools- en handoffs-pagina's waarschuwen "The Agents API v1 is about to be deprecated. Build new agents with the Agents SDK" (Managed Agents, public preview). [T1] [H1] Dit staat los van de modelkeuze, maar is relevant voor de map.

## 4. Prijzen en latency

Prijzen in USD per miljoen tokens, volgens de pricing-pagina. [P1]

| Model | Input | Cached input | Output |
| --- | --- | --- | --- |
| Mistral Large 4 (`mistral-large-4-0`) | $0.70 | $0.07 | $2.10 |
| Mistral Small 4 (`mistral-small-2603`) | $0.15 | $0.015 | $0.60 |
| Ministral 3 14B (`ministral-14b-2512`) | $0.20 | $0.02 | $0.20 |
| Ministral 3 8B (`ministral-8b-2512`) | $0.15 | $0.015 | $0.15 |
| Ministral 3 3B (`ministral-3b-2512`) | $0.10 | $0.01 | $0.10 |

Medium 3.5 en Large 3 staan als deprecated modellen niet meer op de pricing-pagina. [P1]

Reasoning-tokens zijn output-tokens. Large 4 op `high` kost dus naar verhouding veel output ($2.10/MTok). Van `high` naar `low` gaan scheelt tokens, maar haalt de reasoning niet weg. [R1] De web-search- en library-calls zelf worden apart afgerekend. Die prijzen vallen buiten deze research.

**Time-to-first-token.** Mistral publiceert geen TTFT- of tokens-per-seconde-cijfers per model. De model-cards tonen alleen een kwalitatieve "Speed"-balk en de selectiegids bevat geen getallen. [O1]

Wel gedocumenteerd:

- Bij `reasoning_effort="high"` streamt eerst de thinking-fase en pas daarna het antwoord. [R1] Bij `none` (alleen Small 4 en Medium 3.5) is er geen thinking-chunk.
- Voor voorspelbaardere TTFT biedt Mistral een betaalde "Priority Tier" aan. [O1]

Werkelijke verschillen moeten we zelf meten, bijvoorbeeld met de eval-runner, met per agent dezelfde vragen op `high`, `low` en `none`.

## Aanbevolen opties voor de map

Dit zijn opties, nog geen besluit.

| Optie | Model | `reasoning_effort` | Tools en handoffs gedocumenteerd | Prijs in/out per MTok |
| --- | --- | --- | --- | --- |
| A (huidig, maar expliciet) | `mistral-large-4-0` | `high` | ja | 0.70 / 2.10 |
| B (minder reasoning, zelfde model) | `mistral-large-4-0` | `low` of `medium` | ja | 0.70 / 2.10, minder output-tokens |
| C (geen reasoning, klein) | `mistral-small-2603` | `none` | ja | 0.15 / 0.60 |
| D (router/klein met beetje reasoning) | `mistral-small-2603` | `low` | ja | 0.15 / 0.60 |
| Niet doen | `ministral-*-2512` | n.v.t. | **niet gedocumenteerd** voor Agents en Built-In Tools | 0.10–0.20 |
| Niet doen | `mistral-large-2512`, `mistral-medium-3-5` | – | ja, maar deprecated (retired 30-04-2027) | – |

## Bronnen

- [O1] Models overview, met deprecation-tabel: https://docs.mistral.ai/models
- [L1] Model lifecycle policy: https://docs.mistral.ai/inference/model-lifecycle
- [R1] Reasoning: https://docs.mistral.ai/inference/conversations/reasoning
- [D1] Native reasoning (deprecated), Magistral en `prompt_mode`: https://docs.mistral.ai/resources/deprecated/native-reasoning
- [M1] Mistral Large 4: https://docs.mistral.ai/models/mistral-large-4-0
- [M2] Mistral Small 4: https://docs.mistral.ai/models/mistral-small-4-0-26-03
- [M3] Ministral 3 14B: https://docs.mistral.ai/models/ministral-3-14b-25-12 (8B: `/models/ministral-3-8b-25-12`, 3B: `/models/ministral-3-3b-25-12`)
- [M4] Mistral Medium 3.5: https://docs.mistral.ai/models/mistral-medium-3-5-26-04
- [M5] Mistral Large 3: https://docs.mistral.ai/models/mistral-large-3-25-12
- [P1] API pricing: https://docs.mistral.ai/inference/pricing
- [T1] Agent tools: https://docs.mistral.ai/studio/agents/agent-tools
- [W1] Websearch: https://docs.mistral.ai/studio/agents/agent-tools/websearch
- [H1] Handoffs: https://docs.mistral.ai/studio/agents/handoffs
- [S1] SDK `CompletionArgs` en `ReasoningEffort`: https://github.com/mistralai/client-python/blob/main/src/mistralai/client/models/completionargs.py, https://github.com/mistralai/client-python/blob/main/src/mistralai/client/models/reasoningeffort.py
- [S2] SDK `MistralPromptMode` (alleen in chat- en agents-completion-requests): https://github.com/mistralai/client-python/blob/main/src/mistralai/client/models/mistralpromptmode.py
- [S3] SDK `beta.agents.create/update` en `beta.conversations.start` met `completion_args`: https://github.com/mistralai/client-python/blob/main/src/mistralai/client/beta_agents.py, https://github.com/mistralai/client-python/blob/main/src/mistralai/client/conversations.py
