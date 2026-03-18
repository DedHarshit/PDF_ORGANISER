from pypdf import PdfReader

# STAGE - 1 EXTRACTION

reader = PdfReader("PDF_ORGANISER/GENERAL-STUDIES-PAPER-IV-QP-CSM-25-010925.pdf")
page = reader.pages[0]
text = page.extract_text()

if text and text.strip():
    print("Text found:\n")
    print(text)
else:
    print("No text found, extracting images...")
    for i, image_file_object in enumerate(page.images):
        file_name = f"PDF_ORGANISER/out-image-{i}-{image_file_object.name}"
        image_file_object.image.save(file_name)
    print("Done")