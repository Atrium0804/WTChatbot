# this file shows how to upload, list and delete files to api workspace

# this example uses 'purpose=ocr' as those can be uploaded and processed to api workspace
# for RAG use cases, the api workspace is legacy and library endpoints should be used
# https://docs.mistral.ai/api/endpoint/beta/libraries

# main learnings:
# - use API documentation instead of SDK docs
# - files in API workspace are not visible in web console
# - file listing returns only first 20 results, need to count total files/use paginated processing for proper file operation



# python SDK: https://github.com/mistralai/client-python

import os
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

print(f"connect API...")
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])


# upload file to the api workspace:
print(f"uploading file...")
pdf_path = r"knowledge-documents\KNWU-kennis\Nationale_Besluiten_20260918.pdf"
with open(pdf_path, "rb") as f:
    file = client.files.upload(
        file={"file_name": os.path.basename(pdf_path), "content": f},
        purpose="ocr",
    )
print(f"File uploaded: {file.id}")

#  get the number of ocr-files
res = client.files.list(purpose="ocr", include_total=True)
total_filecount = res.total
print(f"er zijn in totaal {total_filecount} files")


# show all attributes of the first file (if exists)
first_file = client.files.list(purpose="ocr").data[0]
print(first_file.model_dump())


# list files in api workspace
print(f"listing files...")
for f in client.files.list().data:
    print(f.id, f.filename, f.purpose, f.size_bytes, f.created_at)


# verwijder alle bestanden - paginated, all pages
print(f"deleting files...")
page = 0
while True:
    res = client.files.list(purpose ="ocr", page=page, page_size=2)
    if not res.data:
        break
    for file in res.data:
        client.files.delete(file_id=file.id)
    page += 1
print("done")