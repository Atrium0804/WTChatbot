# Pilot: leer programmatisch een Mistral-agent aanmaken, gebruiken en opruimen.
# Beslissingen volgens wayfinder-map #18: model mistral-large-4, temperature 0,
# library-only (géén websearch-tool), de agent wordt aan het eind gedeletet.
# Herbruikbaar als template voor de overige agents: library/agentnaam/vraag via CLI-args.
import argparse
import os
from mistralai.client import Mistral
from dotenv import load_dotenv
load_dotenv()                      # laadt .env uit de repo-root

parser = argparse.ArgumentParser(description="Pilot-agent aanmaken, één vraag stellen, opruimen.")
parser.add_argument("--library", default="knwu", help="naam van de te koppelen library")
parser.add_argument("--agent-name", default="knwu-agent-pilot", help="naam van de pilot-agent")
parser.add_argument("--question",
                    default="Wat is het maximaal toegestane verzet voor jongens U15 bij wegwielrennen?")
args = parser.parse_args()

model = "mistral-large-4"          # geverifieerd in GET /v1/models (research/agent-api-docs.md)

mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

# 1. Zoek de library op naam (--library)
lib = next((l for l in mistral.beta.libraries.list(search=args.library).data), None)
if lib is None:
    raise SystemExit(f"library '{args.library}' niet gevonden — draai eerst: python scripts/sync_libraries.py --apply")
print("library gevonden:", lib.id, "|", lib.name)

# 2. Maak de pilot-agent aan. Een library koppel je via tools=[{"type": "document_library", ...}]
agent = mistral.beta.agents.create(
    model=model,
    name=args.agent_name,
    description=f"Pilot-agent (leren) — library: {args.library}",
    instructions=(
        "Je bent de kennischatbot van WTC Woerden. Beantwoord vragen ALLEEN op basis "
        "van de documenten in je gekoppelde library. Verzin niets; zeg het als het "
        "antwoord er niet in staat. Eindig met: Bron: <documentnaam>, versie <datum>. "
        "Bij een rode revisie (oude waarde doorgehaald, nieuwe ernaast in de tabel) "
        "noem je ALLEEN de vigerende waarde. Noem bij een regelementsvraag ook het "
        "artikelnummer (bijv. artikel 20.1.007)."
    ),
    tools=[{"type": "document_library", "library_ids": [lib.id]}],
    # top_p=1 is verplicht bij temperature 0 (greedy sampling) op mistral-large-4
    completion_args={"temperature": 0, "top_p": 1, "response_format": {"type": "text"}},
)
print("agent aangemaakt:", agent.id)

# 3. Start één conversation met de agent. `inputs` mag een plain string zijn.
resp = mistral.beta.conversations.start(agent_id=agent.id, inputs=args.question)

# 4. Print het antwoord: outputs bevat o.a. tool.execution- en message.output-entries;
#    in message.output zitten content-chunks (text + tool_reference) — filter op type == "text".
print("\n=== Antwoord ===")
for out in resp.outputs:
    if getattr(out, "type", None) == "message.output":
        for chunk in (out.content if isinstance(out.content, list) else [out.content]):
            if getattr(chunk, "type", None) == "text":
                print(chunk.text)

# 5. Cleanup: verwijder de agent wieder, dan een korte run-samenvatting
mistral.beta.agents.delete(agent_id=agent.id)
print("\n=== Run-samenvatting ===")
print(f"agent {agent.id} aangemaakt -> 1 conversation ({resp.conversation_id}), "
      f"{resp.usage.total_tokens} tokens, agent gedeletet.")
