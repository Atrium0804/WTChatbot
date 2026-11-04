# Research: mistralai 3.6.0 — exacte SDK-signatures (agent create / library-koppeling / conversation / delete)

Ticket: "Research: mistralai 3.6.0 — exacte SDK-signatures voor agent create / library-koppeling / conversation / delete" (issue #19)
Onderdeel van map: "Wayfinder map — pilot-agent programmatisch aanmaken & gebruiken met Python (mistralai)" (issue #18)

Onderzocht: read-only, via lokale introspectie van de geïnstalleerde SDK (`.venv/Lib/site-packages/mistralai`, dist-info bevestigt `Version: 3.6.0`) met `inspect.signature` en door request/response-modellen lokaal te construeren (géén live API-calls), gekruis refereerd met de officiële docs op docs.mistral.ai.

## 0. Import en client-opzet in 3.6.0

In 3.6.0 is de package-layout `mistralai.client.*` — er is géén top-level `mistralai/__init__.py` met exports:

```py
from mistralai.client import Mistral   # GEEN `from mistralai import Mistral` in 3.6.0
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
```

Top-level attributen op de client in 3.6.0: `agents, audio, batch, beta, chat, classifiers, embeddings, events, files, fim, models, ocr, realtime, responses, workflows` — let op: **`client.conversations` bestaat NIET**; conversations zitten alléén onder `client.beta.conversations`. `client.agents` bestaat wél, maar heeft alléén `complete`/`stream` (chat met een agent zónder conversation-state) — géén create/list/delete. Bron: `.venv/Lib/site-packages/mistralai/client/sdk.py`, geverifieerd via `dir(client)`.

## (a) Agent aanmaken — `client.beta.agents.create`

Bron: `.venv/Lib/site-packages/mistralai/client/beta_agents.py:17` (POST `/v1/agents`).

```py
agent = client.beta.agents.create(
    model="mistral-large-4",                      # str, required
    name="knwu-agent-pilot",                      # str, required
    description="Pilot-agent voor KNWU-vragen.",  # OptionalNullable[str]
    instructions="Beantwoord ...",                # OptionalNullable[str]
    tools=[{"type": "document_library", "library_ids": ["<library-id>"]}],
    completion_args={"temperature": 0, "response_format": {"type": "text"}},
)  # -> models.Agent (heeft .id, .model, .name, .version, ...)
```

Volledige signature (vereenvoudigd, alleen relevante params):

```
beta.agents.create(*, model: str, name: str,
    instructions: OptionalNullable[str] = Unset,
    tools: Optional[Iterable[CreateAgentRequestTool]] = None,   # union incl. DocumentLibraryTool
    completion_args: Optional[CompletionArgs | dict] = None,
    guardrails=Unset, description: OptionalNullable[str] = Unset,
    handoffs=Unset, metadata=Unset, version_message=Unset, ...) -> Agent
```

**Let op: er is géén aparte `temperature`-param op `create`** — sampling-parameters gaan via `completion_args` (`models.CompletionArgs`, `.venv/.../models/completionargs.py`), velden: `stop, presence_penalty, frequency_penalty, temperature, top_p, max_tokens, random_seed, prediction, response_format, tool_choice ('auto'|'none'|'any'|'required'), reasoning_effort ('none'|'minimal'|'low'|'medium'|'high'|'xhigh'|'max')`.

`response_format` (`models.ResponseFormat`): `{"type": "text" | "json_object" | "json_schema", "json_schema": {"name": str, "schema_definition": dict, "description": str?, "strict": bool?}}` (`models/responseformat.py`, `models/jsonschema.py`).

Docs cross-check: docs.mistral.ai/studio/agents/agents-api ("Creating an Agent", `client.beta.agents.create(...)`) en de update-voorbeeld met `completion_args={"temperature": 0.3, "top_p": 0.95}` — bevestigt dat temperature in `completion_args` hoort.

## (b) Document library koppelen — via `tools[]`, géén aparte param

Er is in 3.6.0 **géén dedicated `document_library`-param** op `create`; de library koppel je via de tool-list:

```py
tools=[{"type": "document_library", "library_ids": ["01a1411d-e9bc-747c-98c8-2808dae2094e"]}]
```

`models.DocumentLibraryTool` (`models/documentlibrarytool.py`): `library_ids: List[str]` (required), `type: Literal['document_library']`, optioneel `tool_configuration` (`models.ToolConfiguration`: `include`/`exclude`/`requires_confirmation`: `List[str]`). Lokaal geverifieerd: `models.CreateAgentRequest(..., tools=[{"type": "document_library", "library_ids": [...]}])` serialiseert correct.

Docs cross-check: docs.mistral.ai/studio/libraries, sectie "Connecting Libraries to agents":
`tools=[{"type": "document_library", "library_ids": [new_library.id]}]` — idem.

Library opzoeken: `client.beta.libraries.list(*, page_size=100, page=0, search=...)` en `client.beta.libraries.get(*, library_id)` (`.venv/.../client/libraries.py`).

## (c) Conversation starten, bericht sturen, antwoord ophalen — beta-only in 3.6.0

In 3.6.0 is er **geen non-beta conversations-endpoint**: `client.conversations` bestaat niet op de SDK; alles zit onder `client.beta.conversations` (`client/conversations.py`, bediend via `Beta._init_sdks`). Bron: `sdk.py`, `beta.py`, geverifieerd via `hasattr(client, 'conversations') == False`.

```py
# 1) start conversation met agent + eerste user-bericht in één call (POST /v1/conversations)
resp = client.beta.conversations.start(
    agent_id=agent.id,
    inputs="Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?",
    # inputs acceptereert ook: [{"role": "user", "content": "..."}]  (ConversationInputs = str | List[InputEntries])
)  # -> ConversationResponse{conversation_id, outputs, usage}

conversation_id = resp.conversation_id

# 2) vervolgbericht sturen (POST /v1/conversations/{conversation_id})
resp2 = client.beta.conversations.append(
    conversation_id=conversation_id,
    inputs="...",
)  # -> ConversationResponse

# 3) antwoord lezen uit de response, of uit de history
history = client.beta.conversations.get_history(conversation_id=conversation_id)  # GET .../history -> ConversationHistory{entries}
msgs = client.beta.conversations.get_messages(conversation_id=conversation_id)     # GET .../messages -> ConversationMessages{messages}
```

Signatures (vereenvoudigd):

```
beta.conversations.start(*, inputs: str | List[InputEntries], store=Unset,
    handoff_execution=Unset, instructions=Unset, tools=Unset, completion_args=Unset,
    guardrails=Unset, name=Unset, description=Unset, metadata=Unset,
    agent_id: OptionalNullable[str] = Unset, agent_version=Unset,
    model: OptionalNullable[str] = Unset, ...) -> ConversationResponse   # POST /v1/conversations
beta.conversations.append(*, conversation_id: str, inputs=None, store: bool = True,
    handoff_execution='server', completion_args=None, tool_confirmations=Unset, ...) -> ConversationResponse  # POST /v1/conversations/{id}
beta.conversations.get_history(*, conversation_id: str, ...) -> ConversationHistory  # GET /v1/conversations/{id}/history
beta.conversations.get_messages(*, conversation_id: str, ...) -> ConversationMessages # GET /v1/conversations/{id}/messages
beta.conversations.list(*, page=0, page_size=100, metadata=Unset, ...) -> list
beta.conversations.get/delete(*, conversation_id: str, ...)
```

**Assistant-antwoord extractie** (lokaal geverifieerd door `ConversationResponse` te construeren): `resp.outputs` is een list van `ConversationResponseOutput` (union: `MessageOutputEntry | AgentHandoffEntry | ToolExecutionEntry | FunctionCallEntry`); het assistant-bericht is het entry met `type == "message.output"` en `role == "assistant"`, met `content` als string óf list van chunks; tekst-chunks hebben `type == "text"` en `.text`:

```py
for out in resp.outputs:
    if getattr(out, "type", None) == "message.output":
        for chunk in out.content:            # content kan str of List[MessageOutputContentChunks]
            if getattr(chunk, "type", None) == "text":
                print(chunk.text)
```

Docs cross-check: docs.mistral.ai/studio/agents/agents-api — `client.beta.conversations.start(agent_id=..., inputs="Who is Albert Einstein?")` met opmerking dat `inputs=[{"role": "user", "content": ...}]` ook mag; `append(conversation_id=..., inputs=...)`; `get_history(conversation_id=...)`; response-vorm `{"conversation_id": ..., "outputs": [{"content": "..."}]}`.

**Alternatief zonder conversation-state** (handig om te testen): `client.agents.complete(*, messages=[{"role": "user", "content": "..."}], agent_id=..., response_format=..., max_tokens=..., ...) -> ChatCompletionResponse` — POST `/v1/agents/completions` (`.venv/.../client/agents.py:15`). Let op: `agents.complete` heeft in 3.6.0 óók géén `temperature`-param (alleen max_tokens/stop/penalties/seed/response_format/...), dus temperature regelen kan alleen via `completion_args` op agent- of conversation-niveau.

## (d) Agents listen en deleten — beta-only in 3.6.0

```py
agents = client.beta.agents.list()                    # GET /v1/agents -> List[Agent]
# filters: page=0, page_size=20, name=..., search=..., id=..., sources=..., metadata=...
client.beta.agents.get(agent_id=agent.id)             # GET /v1/agents/{agent_id}
client.beta.agents.update(agent_id=..., name=..., instructions=..., tools=..., completion_args=..., ...)  # PATCH-achtig
client.beta.agents.delete(agent_id=agent.id)          # DELETE /v1/agents/{agent_id} -> None
```

`client.agents.list()` bestaat in 3.6.0 NIET (bevestigt de verificatie in de map-Notities). Bron: `beta_agents.py` (create=POST `/v1/agents`, list=GET `/v1/agents`, get/update/delete=`/v1/agents/{agent_id}`), geverifieerd via `inspect.signature` + `inspect.getsource`.

## Minimaal geverifieerd snippet (create → chat → delete) — basis voor `python-learning/scripts/agent_pilot.py`

Alle parameternamen hieronder zijn lokaal gevalideerd tegen de 3.6.0-modellen (`models.CreateAgentRequest`, `ConversationRequest`, `ConversationAppendRequest` construeren zonder netwerk):

```py
import os
from dotenv import load_dotenv
from mistralai.client import Mistral  # 3.6.0: géén `from mistralai import Mistral`

load_dotenv()
KNWU_LIB_ID = "01a1411d-e9bc-747c-98c8-2808dae2094e"  # library `knwu`

with Mistral(api_key=os.getenv("MISTRAL_API_KEY")) as client:
    # (a) agent aanmaken: temperature zit in completion_args, library via tools[]
    agent = client.beta.agents.create(
        model="mistral-large-4",
        name="knwu-agent-pilot",
        description="Pilot-agent voor KNWU-reglementvragen.",
        instructions="Beantwoord alleen op basis van de gekoppelde KNWU-library; vermeld de bron.",
        tools=[{"type": "document_library", "library_ids": [KNWU_LIB_ID]}],
        completion_args={"temperature": 0, "response_format": {"type": "text"}},
    )

    # (c) conversation starten met agent_id + user-vraag
    resp = client.beta.conversations.start(
        agent_id=agent.id,
        inputs="Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?",
    )

    # assistant-antwoord uit outputs halen
    for out in resp.outputs:
        if getattr(out, "type", None) == "message.output":
            content = out.content if isinstance(out.content, list) else [out.content]
            for chunk in content:
                if getattr(chunk, "type", None) == "text":
                    print(chunk.text)

    # (d) agent weer verwijderen
    client.beta.agents.delete(agent_id=agent.id)
```

Volgorde voor de pilot: `beta.agents.create` → `beta.conversations.start(agent_id=..., inputs=...)` → lees `resp.outputs` (of `beta.conversations.get_history(conversation_id=...)`) → `beta.agents.delete(agent_id=...)`. Eventueel vooraf `beta.agents.list(name="knwu-agent-pilot")` om opruimen na te gaan.

## Bronnen

- SDK (primair, lokaal): `.venv/Lib/site-packages/mistralai-3.6.0.dist-info/METADATA` (Version: 3.6.0); `client/sdk.py`, `client/beta.py`, `client/beta_agents.py`, `client/agents.py`, `client/conversations.py`, `client/libraries.py`; modellen: `client/models/completionargs.py`, `documentlibrarytool.py`, `toolconfiguration.py`, `responseformat.py`, `jsonschema.py`, `conversationrequest.py`, `conversationappendrequest.py`, `conversationinputs.py`, `conversationresponse.py`, `conversationhistory.py`, `messageinputentry.py`, `messageoutputentry.py`, `messageoutputcontentchunks.py`, `textchunk.py`. Geïnspecteerd met `inspect.signature` / `model_fields` via `.venv/Scripts/python.exe`.
- Docs (cross-check): https://docs.mistral.ai/studio/agents/agents-api (create/update/start/append/get_history, `inputs` als string of `[{"role","content"}]`); https://docs.mistral.ai/studio/libraries ("Connecting Libraries to agents": `tools=[{"type": "document_library", "library_ids": [...]}]`); API-spec: https://docs.mistral.ai/api/#tag/beta.agents en `#tag/beta.conversations`.
- Repo: `scripts/create_agents.py` (bevestigt `from mistralai.client import Mistral` + `mistral.beta.agents.create(model=..., name=..., completion_args={"response_format": {"type": "text"}})`).
