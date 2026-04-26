from __future__ import annotations

from io import BytesIO
from typing import Any

from src.llm_client import call_llm

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

try:
    from docx import Document
except ImportError:  # pragma: no cover
    Document = None


def extract_text_from_pdf(file: Any) -> str:
    """Extract text from a PDF upload using PyMuPDF."""

    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")
    file.seek(0)
    pdf_bytes = file.read()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        pages = [page.get_text("text") for page in document]
    return "\n".join(pages).strip()


def extract_text_from_docx(file: Any) -> str:
    """Extract text from a DOCX upload using python-docx."""

    if Document is None:
        raise RuntimeError("python-docx is not installed.")
    file.seek(0)
    buffer = BytesIO(file.read())
    document = Document(buffer)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs).strip()


def extract_text(file: Any) -> str:
    """Extract and lightly clean text from PDF, DOCX, or TXT uploads."""

    filename = (getattr(file, "name", "") or "").lower()
    if filename.endswith(".pdf"):
        raw_text = extract_text_from_pdf(file)
    elif filename.endswith(".docx"):
        raw_text = extract_text_from_docx(file)
    else:
        file.seek(0)
        raw_text = file.read().decode("utf-8", errors="ignore")
    return clean_extracted_text(raw_text)


def clean_extracted_text(raw_text: str) -> str:
    """Normalize JD text with LLM cleanup and deterministic fallback."""

    prompt = (
        "Clean and normalize this job description. "
        "Remove formatting noise and keep only hiring-relevant content. "
        "Preserve requirements, responsibilities, location, work mode, and skills.\n\n"
        f"{raw_text}"
    )
    cleaned_text = call_llm(prompt, temperature=0.1).strip()
    if cleaned_text:
        return cleaned_text
    return "\n".join(line.strip() for line in raw_text.splitlines() if line.strip()).strip()
