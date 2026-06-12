"""
classifier.py
-------------
Handles all PDF content extraction and LLM-based folder classification.
Supports both text-based and image-based (scanned) PDFs.
"""

import os
import re
import base64
import logging
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

ENDPOINT     = "https://models.github.ai/inference"
MODEL_NAME   = "openai/gpt-4o"
MAX_PAGES    = 3        # Pages to scan for text before giving up
TEXT_LIMIT   = 4000     # Max characters sent to API (avoid token overflow)
API_RETRIES  = 3
API_BACKOFF  = 2.0      # seconds (doubles each retry)

SYSTEM_PROMPT = (
    "You are a document classification assistant. "
    "Assign a concise folder path for the given document. "
    "Rules:\n"
    "- 2–3 levels max, e.g. 'Exams/Civil_Services' or 'Finance/Tax_Returns'\n"
    "- Use only letters, numbers, underscores, and forward slashes\n"
    "- NO dates, years, paper numbers, or version info\n"
    "- Focus on subject matter and document type only\n"
    "Return ONLY the folder path. No explanation, no punctuation."
)

def _get_client() -> OpenAI:
    """Create OpenAI client with the current token (read fresh each time so .env changes are picked up)."""
    load_dotenv(override=True)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set. Add it in the Settings tab or .env file.")
    return OpenAI(base_url=ENDPOINT, api_key=token)


# ── Text & Image Extraction ───────────────────────────────────────────────────

class PDFExtractionError(Exception):
    """Raised when a PDF cannot be read at all (corrupted, encrypted, empty)."""

class PDFNoContentError(Exception):
    """Raised when a PDF is valid but yields no extractable text or images."""


def extract_content(pdf_path: str) -> tuple[str | None, list[str]]:
    """
    Extract text and/or images from a PDF.

    Strategy:
        1. Try text extraction from the first MAX_PAGES pages.
        2. If no text found, extract the first embedded image from page 1.

    Returns:
        (text_or_None, list_of_temp_image_file_paths)

    Raises:
        PDFExtractionError  — corrupted, encrypted, or unreadable PDF
        PDFNoContentError   — valid PDF but nothing extractable
    """
    pdf_path = str(pdf_path)
    temp_images: list[str] = []

    try:
        reader = PdfReader(pdf_path)
    except PdfReadError as exc:
        raise PDFExtractionError(f"Corrupted or invalid PDF: {pdf_path}") from exc
    except Exception as exc:
        raise PDFExtractionError(f"Cannot open PDF: {exc}") from exc

    if reader.is_encrypted:
        raise PDFExtractionError(f"PDF is password-protected: {pdf_path}")

    if len(reader.pages) == 0:
        raise PDFExtractionError(f"PDF has no pages: {pdf_path}")

    # ── Pass 1: text extraction ───────────────────────────────────────────────
    text_parts: list[str] = []
    for page in reader.pages[:MAX_PAGES]:
        try:
            raw = page.extract_text()
            if raw and raw.strip():
                text_parts.append(raw.strip())
        except Exception as exc:
            logger.warning("Text extraction failed on a page: %s", exc)

    if text_parts:
        combined = "\n\n".join(text_parts)
        logger.debug("Extracted %d chars of text from '%s'", len(combined), pdf_path)
        return combined, temp_images

    # ── Pass 2: image extraction fallback ────────────────────────────────────
    logger.info("No text found in '%s', falling back to image extraction.", pdf_path)
    first_page = reader.pages[0]

    if not first_page.images:
        raise PDFNoContentError(
            f"No extractable text or images found in '{pdf_path}'. "
            "It may be a scanned PDF with no embedded images — "
            "consider adding an OCR pre-processing step."
        )

    img_obj = first_page.images[0]
    suffix  = Path(img_obj.name).suffix or ".jpg"
    tmp     = tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, prefix="pdf_organiser_img_"
    )
    img_obj.image.save(tmp.name)
    tmp.close()
    temp_images.append(tmp.name)
    logger.debug("Saved temp image '%s' for '%s'", tmp.name, pdf_path)

    return None, temp_images


# ── API Calls ─────────────────────────────────────────────────────────────────

def _call_api(messages: list[dict], retries: int = API_RETRIES) -> str:
    """
    Call the LLM API with exponential-backoff retry on transient errors.

    Raises:
        RuntimeError — after all retries exhausted, or on non-retryable API error
    """
    client = _get_client()
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,   # Low temp = consistent, deterministic paths
                top_p=1.0,
                max_tokens=100,
            )
            return response.choices[0].message.content.strip()

        except RateLimitError:
            wait = API_BACKOFF * (2 ** attempt)
            logger.warning("Rate limit hit. Retrying in %.1fs… (%d/%d)", wait, attempt + 1, retries)
            time.sleep(wait)

        except APITimeoutError:
            wait = API_BACKOFF * (2 ** attempt)
            logger.warning("API timeout. Retrying in %.1fs… (%d/%d)", wait, attempt + 1, retries)
            time.sleep(wait)

        except APIError as exc:
            raise RuntimeError(f"Non-retryable API error: {exc}") from exc

    raise RuntimeError(f"API call failed after {retries} retries.")


def _build_text_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": text[:TEXT_LIMIT]},
    ]


def _build_image_messages(image_path: str) -> list[dict]:
    with open(image_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("utf-8")

    ext      = Path(image_path).suffix.lstrip(".")
    mime     = f"image/{ext}" if ext else "image/jpeg"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Classify this document and return only the folder path."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        },
    ]


# ── Path Sanitization ─────────────────────────────────────────────────────────

def _sanitize_path(raw: str) -> str:
    """
    Clean up the LLM-returned path to be safe for all operating systems.

    - Strips leading/trailing slashes and whitespace
    - Removes any character that isn't alphanumeric, underscore, hyphen, or separator
    - Collapses empty segments
    - Falls back to 'Uncategorized' if nothing valid remains
    """
    path = raw.strip().strip("/\\")
    segments = re.split(r"[/\\]", path)
    clean = []
    for seg in segments:
        seg = re.sub(r"[^\w\s-]", "", seg).strip().replace(" ", "_")
        if seg:
            clean.append(seg)
    return os.path.join(*clean) if clean else "Uncategorized"


# ── Public API ────────────────────────────────────────────────────────────────

def classify_pdf(pdf_path: str) -> str:
    """
    Full pipeline: extract content from PDF → classify via LLM → return folder path.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A sanitized relative folder path string, e.g. 'Exams/Civil_Services'.

    Raises:
        PDFExtractionError  — unreadable PDF (caller should move to _errors)
        PDFNoContentError   — valid but empty PDF
        RuntimeError        — API failure after all retries
    """
    text, temp_images = extract_content(pdf_path)

    try:
        if text:
            messages = _build_text_messages(text)
        else:
            messages = _build_image_messages(temp_images[0])

        raw_path   = _call_api(messages)
        clean_path = _sanitize_path(raw_path)
        logger.info("'%s'  →  classified as  '%s'", Path(pdf_path).name, clean_path)
        return clean_path

    finally:
        for img in temp_images:
            try:
                os.remove(img)
                logger.debug("Cleaned up temp image '%s'", img)
            except OSError:
                pass  # Not critical if cleanup fails
