# this file is used to test the RAG-document handling in Mistral Studio
#
# https://docs.mistral.ai/api/endpoint/beta/libraries
# https://docs.mistral.ai/api/endpoint/beta/libraries/documents
# https://docs.mistral.ai/api/endpoint/beta/libraries/accesses

import os
import json
from dotenv import load_dotenv
from mistralai.client import Mistral
from time import perf_counter

# config
rag_folder = "knowledge_documents"
rag_libraries = [
    {"name": "knwu" , "description": "RAG-libary voor KNWU-kennis"},
    {"name": "regio", "description": "RAG-library voor regio-kennis"},
    {"name": "club" , "description": "RAG-libary voor club-kennis"},
]

# connect to Mistral API
load_dotenv()
started = perf_counter()

mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))  # client blift hele script bestaan
print(f"Request: {perf_counter() - started:.2f}s;")



######################
# create libraries if missing
######################

# returns all exsiting libraries:
page_token=None
all_libraries =[]
print("Fetching all libraries:")
while True:
    paged_libraries=mistral.beta.libraries.list(page_size=100, page_token=page_token)
    all_libraries += paged_libraries.data
    if paged_libraries.next_page_token is None:
        break
    page_token=paged_libraries.next_page_token
print(f"Existing libraries: {[l.name for l in all_libraries]}")


# determine which libraries are missing
missing_libraries =[]
for lib in rag_libraries:
    if lib["name"] not in [l.name for l in all_libraries]:
        missing_libraries.append(lib["name"])
if not missing_libraries:
    print("All required libraries exist")
else:
    print("Missing some libraries")
    print(missing_libraries)

# create the missing libraries
for lib in missing_libraries:
    started = perf_counter()
    mistral.beta.libraries.create(name=lib)
    print(f"Request: {perf_counter() - started:.2f}s;")
    print(f"Created library {lib}")
print("Done")

##################
## document sync
#################
# get all documents in the local folder
local_docs = os.listdir(rag_folder)
print(f"Local docs: {local_docs}")

# get all documents in the remote folder
remote_docs = []
for lib in all_libraries:
    remote_docs += [d.name for d in mistral.beta.libraries.documents.list(library_id=lib.id).data]
print(f"Remote docs: {remote_docs}")

# upload missing docs



# # delete all libraries
# print("Deleting all libraries")
# for lib in all_libraries:
#     print(f"Deleting {lib.name}")
#     response=mistral.beta.libraries.delete(library_id=lib.id)
