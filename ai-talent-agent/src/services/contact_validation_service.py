from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

from src.resume_parser import is_valid_email

try:
    import phonenumbers
except ImportError:  # pragma: no cover
    phonenumbers = None


SUSPICIOUS_EMAIL_DOMAINS = {"example.com", "test.com", "mailinator.com"}


def normalize_email(email: str | None) -> str | None:
    cleaned = (email or "").strip().lower()
    return cleaned or None


def validate_email(email: str | None) -> dict[str, Any]:
    normalized = normalize_email(email)
    valid = is_valid_email(normalized)
    domain = normalized.split("@", 1)[1] if valid and normalized and "@" in normalized else ""
    warning = "Suspicious email domain." if domain in SUSPICIOUS_EMAIL_DOMAINS else ""
    return {
        "value": normalized,
        "valid": valid,
        "warning": warning,
        "confidence": 0.98 if valid else 0.0,
    }


def normalize_phone(phone: str | None) -> str | None:
    cleaned = re.sub(r"[^\d+]", "", (phone or "").strip())
    return cleaned or None


def validate_phone(phone: str | None) -> dict[str, Any]:
    normalized = normalize_phone(phone)
    if not normalized:
        return {"value": None, "valid": False, "warning": "Phone number missing.", "confidence": 0.0}
    if phonenumbers is None:
        digits = re.sub(r"\D", "", normalized)
        valid = 10 <= len(digits) <= 15
        return {
            "value": normalized,
            "valid": valid,
            "warning": "" if valid else "Phone number format could not be verified.",
            "confidence": 0.7 if valid else 0.2,
        }
    try:
        parsed = phonenumbers.parse(normalized, None)
        valid = phonenumbers.is_valid_number(parsed)
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164) if valid else normalized
        return {
            "value": formatted,
            "valid": valid,
            "warning": "" if valid else "Phone number is not valid.",
            "confidence": 0.95 if valid else 0.1,
        }
    except Exception:
        return {"value": normalized, "valid": False, "warning": "Phone number could not be parsed.", "confidence": 0.1}


def mask_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 4:
        return "Unavailable"
    return f"{'*' * max(0, len(digits) - 4)}{digits[-4:]}"


def _normalize_url(url: str | None) -> str | None:
    cleaned = (url or "").strip()
    if not cleaned:
        return None
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned


def validate_linkedin(url: str | None) -> dict[str, Any]:
    normalized = _normalize_url(url)
    if not normalized:
        return {"value": None, "valid": False, "warning": "LinkedIn URL missing.", "confidence": 0.0}
    parsed = urlparse(normalized)
    valid = parsed.netloc.endswith("linkedin.com") and ("/in/" in parsed.path or "/pub/" in parsed.path)
    return {
        "value": normalized,
        "valid": valid,
        "warning": "" if valid else "LinkedIn URL should look like linkedin.com/in/... or linkedin.com/pub/...",
        "confidence": 0.9 if valid else 0.2,
    }


def validate_url(url: str | None) -> dict[str, Any]:
    normalized = _normalize_url(url)
    if not normalized:
        return {"value": None, "valid": False, "warning": "URL missing.", "confidence": 0.0}
    parsed = urlparse(normalized)
    valid = bool(parsed.scheme and parsed.netloc)
    return {"value": normalized, "valid": valid, "warning": "" if valid else "URL is malformed.", "confidence": 0.85 if valid else 0.2}


def contact_readiness(candidate: dict[str, Any], compliance: dict[str, Any] | None = None) -> dict[str, Any]:
    compliance = compliance or {}
    email_result = validate_email(candidate.get("email"))
    phone_result = validate_phone(candidate.get("phone"))
    linkedin_result = validate_linkedin(candidate.get("linkedin_url"))
    consent_status = candidate.get("contact_consent_status") or ("opted_out" if compliance.get("opt_out") else "unknown")
    twilio_ready = bool(os.getenv("TWILIO_SID", "").strip()) and bool(os.getenv("TEST_PHONE_NUMBER", "").strip())
    if not compliance.get("outreach_allowed", True):
        status = "Blocked by compliance"
        preferred = "blocked"
        reason = "; ".join(compliance.get("reasons", ["Compliance review required"]))
    elif email_result["valid"]:
        status = "Ready for email draft"
        preferred = "email"
        reason = "Valid email is available and can be used for draft or test mode."
    elif phone_result["valid"] and candidate.get("phone"):
        status = "Ready for SMS test only" if twilio_ready else "Needs recruiter review"
        preferred = "sms_test" if twilio_ready else "call_manual"
        reason = "Phone is available, but recruiter review is still required before any live outreach."
    elif linkedin_result["valid"]:
        status = "LinkedIn manual task"
        preferred = "linkedin_manual"
        reason = "LinkedIn is available, but outreach remains manual."
    else:
        status = "Missing contact info"
        preferred = "enrichment_needed"
        reason = "No verified recruiter-safe contact channel is available yet."
    if consent_status == "unknown" and preferred == "email":
        reason = f"{reason} Consent is not explicit, so production send remains blocked."
    return {
        "contact_readiness_status": status,
        "contact_readiness_reason": reason,
        "preferred_channel": preferred,
        "email_valid": email_result["valid"],
        "phone_valid": phone_result["valid"],
        "linkedin_valid": linkedin_result["valid"],
        "email_confidence": email_result["confidence"],
        "phone_confidence": phone_result["confidence"],
        "linkedin_confidence": linkedin_result["confidence"],
        "masked_phone": mask_phone(phone_result["value"]),
        "contact_consent_status": consent_status,
        "validations": {
            "email": email_result,
            "phone": phone_result,
            "linkedin": linkedin_result,
            "github": validate_url(candidate.get("github_url")),
            "portfolio": validate_url(candidate.get("portfolio_url")),
        },
    }
