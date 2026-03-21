from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv() 
# STAGE - 1 EXTRACTION

reader = PdfReader("GENERAL-STUDIES-PAPER-IV-QP-CSM-25-010925.pdf")
page = reader.pages[0]
text = page.extract_text()

if text and text.strip():
    print("Text found:\n")
    print(text)
else:
    print("No text found, extracting images...")
    for i, image_file_object in enumerate(page.images):
        file_name = f"out-image-{i}-{image_file_object.name}"
        image_file_object.image.save(file_name)
    print("Done")

# STAGE - 2 Setup Github MarketPlace API

token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"
model_name = "openai/gpt-4o"

client = OpenAI(
    base_url=endpoint,
    api_key=token,
)

response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "What is the capital of France?",
        }
    ],
    temperature=1.0,
    top_p=1.0,
    max_tokens=1000,
    model=model_name
)

print(response.choices[0].message.content)