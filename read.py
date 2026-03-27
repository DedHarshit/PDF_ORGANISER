from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv() 
# STAGE - 1 EXTRACTION

reader = PdfReader("1773859921123.pdf")
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


if text and text.strip():
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a help full assistant whos job is to find the correct sorted path/folder for the pdf based on the given text in format of a\b\c",
            },
            {
                "role": "user",
                "content": f"{text}",
            }
        ],
        temperature=1.0,
        top_p=1.0,
        max_tokens=1000,
        model=model_name
)
    
else:
    response = client.chat.completions.create(
       input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": "You are a help full assistant whos job is to find the correct sorted path/folder for the pdf based on the given text in format of a\b\c"},
            {
                "type": "input_image",
                "image_url": "https://api.nga.gov/iiif/a2e6da57-3cd1-4235-b20e-95dcaefed6c8/full/!800,800/0/default.jpg",
            },
        ],
    }],
)

print(response.choices[0].message.content)