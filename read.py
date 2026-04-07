from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import os
import base64

load_dotenv() 
# STAGE - 1 EXTRACTION

reader = PdfReader("GENERAL-STUDIES-PAPER-IV-QP-CSM-25-010925.pdf")
page = reader.pages[0]
text = page.extract_text()

if text and text.strip():
    print("Text found:\n")
    #print(text)
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
                "content":  "You are a document classification assistant. Your task is to assign a concise folder path for the given document.Rules: - Keep the path short and meaningful (2–3 levels max)- Do NOT include year, dates, paper numbers, or unnecessary details- Focus only on the main category and subcategory - Avoid over-specific classification Return ONLY the folder path. No explanation.",
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
    print("Using previously extracted image...")

    image_path = None
    for file in os.listdir():
        if file.startswith("out-image-"):
            image_path = file
            break

    if not image_path:
        raise Exception("No extracted image found")

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are a document classification assistant. Your task is to assign a concise folder path for the given document.Rules: - Keep the path short and meaningful (2–3 levels max)- Do NOT include year, dates, paper numbers, or unnecessary details- Focus only on the main category and subcategory - Avoid over-specific classification Return ONLY the folder path. No explanation.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Classify this PDF and return folder path."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.2,
        max_tokens=200
    )
print(response.choices[0].message.content.strip())