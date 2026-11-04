# testje met RAG document search
import os
from dotenv import load_dotenv
from mistralai.client import Mistral
from time import perf_counter

rag_libraries = [
    {"name": "knwu" , "description": "RAG-libary voor KNWU-kennis"},
    {"name": "regio", "description": "RAG-library voor regio-kennis"},
    {"name": "club" , "description": "RAG-libary voor club-kennis"},
]

load_dotenv()
timer_started = perf_counter()
mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


response = mistral.chat.complete(
    model="mistral-medium-latest",
    messages=[
        {
            "role": "user",
            "content": "wat is categorie u9",
        }
    ],
    documents=[{"type": "file", "id": library.id}],
)

print(response.choices[0].message.content)