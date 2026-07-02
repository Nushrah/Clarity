"""Resume text extraction utilities for Clarity."""

import re
from typing import Dict, Any

from pypdf import PdfReader
from docx import Document


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_resume_text(file_path: str, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(file_path)
    if file_type == "docx":
        return extract_text_from_docx(file_path)
    if file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    raise ValueError("Unsupported resume file type")


def anonymize_resume_text(raw_text: str) -> str:
    """Remove name, email, phone, and address patterns for blind screening."""
    text = raw_text
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL REDACTED]", text)
    text = re.sub(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE REDACTED]", text)
    text = re.sub(r"\b\d{1,5}\s+\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b[^,\n]*", "[ADDRESS REDACTED]", text, flags=re.IGNORECASE)
    lines = text.split("\n")
    if lines:
        lines[0] = "[NAME REDACTED]"
    return "\n".join(lines)


def build_anonymized_profile(raw_text: str, candidate_id: str) -> Dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "anonymized_text": anonymize_resume_text(raw_text),
        "skills": [],
        "experience": [],
        "education_redacted": True,
    }
