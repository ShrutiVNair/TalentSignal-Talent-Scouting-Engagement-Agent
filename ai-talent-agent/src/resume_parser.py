from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?\d{1,3}[\s\-()]*)?(?:\d[\s\-()]*){8,15}\d)"
)
LINKEDIN_PATTERN = re.compile(
    r"(https?://(?:www\.)?linkedin\.com/[A-Za-z0-9\-_/%.]+)",
    re.IGNORECASE,
)


def extract_contact_info(resume_text: str) -> dict[str, str | None]:
    """Extract the first email, phone, and LinkedIn URL from resume text."""

    normalized = " ".join(resume_text.split())
    email_match = EMAIL_PATTERN.search(normalized)
    phone_match = PHONE_PATTERN.search(normalized)
    linkedin_match = LINKEDIN_PATTERN.search(normalized)

    email = email_match.group(0).strip() if email_match else None
    phone = _normalize_phone(phone_match.group(0)) if phone_match else None
    linkedin = linkedin_match.group(1).strip() if linkedin_match else None

    return {
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
    }


def is_valid_email(email: str | None) -> bool:
    """Return whether an email looks syntactically valid."""

    if not email:
        return False
    return bool(EMAIL_PATTERN.fullmatch(email.strip()))


def _normalize_phone(phone: str) -> str | None:
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    return cleaned or None
