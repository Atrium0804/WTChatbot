# this file is used to test the RAG-document handling in Mistral Studio
#
# https://docs.mistral.ai/api/endpoint/beta/libraries
# https://docs.mistral.ai/api/endpoint/beta/libraries/documents
# https://docs.mistral.ai/api/endpoint/beta/libraries/accesses

import os
from dotenv import load_dotenv
from mistralai.client import Mistral

# connect to Mistral API
load_dotenv()
mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))  # client blift hele script bestaan

# returns a list of libraries (max 100), page= is deprecated
res = mistral.beta.libraries.list(page_size=100, page=0)
print(res)

# returns all libraries:
page_token=None
while True:
    res=mistral.beta.libraries.list(page_size=100, page_token=page_token)
    for lib in res.data:
        print(lib.model_dump_json(indent=2))
    if res.next_page_token is None:
        break
    page_token=res.next_page_token

