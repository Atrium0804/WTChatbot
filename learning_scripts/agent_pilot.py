# dit script maakt agents nieuwe agents aan, ook al bestaat er al een met dezelfde naam
import os
from mistralai.client import Mistral
from dotenv import load_dotenv
load_dotenv()                      # laadt .env uit de repo-root


model = "mistral-large-latest"


mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


# find and return the knwu library
libraries = mistral.beta.libraries.list(page_size=100)
knwu = next(
    (lib for lib in mistral.beta.libraries.list(search="knwu").data), None)
if knwu is None:
    raise SystemExit(
        "knwu-library niet gevonden — draai eerst: python scripts/sync_libraries.py --apply")
print(knwu.model_dump_json())

# create agent
agent_name = "knwu-agent-pilot"
agent_description = "KNWU agent"
agent_instructions = (
    "Je bent de kennischatbot van WTC Woerden. Beantwoord vragen ALLEEN op basis "
    "van de documenten in je gekoppelde library. Verzin niets; zeg het als het "
    "antwoord er niet in staat. Eindig met: Bron: <documentnaam>, versie <datum>."
)
knwu_agent = mistral.beta.agents.create(
    model=model,
    description=agent_description,
    instructions=agent_instructions,
    name=agent_name,
    tools=[
        {"type": "document_library", "library_ids": [
            knwu.id]}  # <- zo koppel je de library
        ],
    completion_args={"temperature": 0     # <-- bepaalt de creativiteit
                        , "response_format": {"type": "text"}
                        },
)
print("agent aangemaakt:", knwu_agent.id)

agent_name = "web-agent-pilot"
agent_description = "web agent"
agent_instructions = (
    "Je bent de kennischatbot van WTC Woerden, je beantwoord vragen met de websearch tool"
)
web_agent = mistral.beta.agents.create(
    model=model,
    description=agent_description,
    instructions=agent_instructions,
    name=agent_name,
    tools=[{
        "type": "web_search",  # <- zo gebruik je de webtool
    }],
    completion_args={
        "temperature": 0,
        "response_format": {"type": "text"},
    },
)


print("agent aangemaakt:", web_agent.id)


# use agent to ask question
print("\n=== query a document ===")
question = "Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen"
resp = mistral.beta.conversations.start(agent_id=knwu_agent.id, inputs=question)
print("\n=== Agent response ===")
print(resp.model_dump_json(indent=2))
for out in resp.outputs:
    if getattr(out, "type", None) == "message.output":
        for chunk in (out.content if isinstance(out.content, list) else [out.content]):
            if getattr(chunk, "type", None) == "text":
                print(chunk.text)


print("\n=== query the web ===")
question = "Wanneer is wtc woerden opgericht"
resp = mistral.beta.conversations.start(agent_id=web_agent.id, inputs=question)
print("\n=== Agent response ===")
print(resp.model_dump_json(indent=2))
for out in resp.outputs:
    if getattr(out, "type", None) == "message.output":
        for chunk in (out.content if isinstance(out.content, list) else [out.content]):
            if getattr(chunk, "type", None) == "text":
                print(chunk.text)

# delete agent after use
# mistral.beta.agents.delete(agent_id=agent.id)
