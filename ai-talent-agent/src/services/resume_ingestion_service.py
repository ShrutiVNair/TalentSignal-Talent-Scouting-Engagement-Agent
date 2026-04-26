from __future__ import annotations

import uuid
from typing import Any

from src.jd_extractor import extract_text
from src.services.audit_service import log_audit
from src.services.candidate_service import upsert_candidate
from src.services.contact_extraction_service import extract_candidate_profile
from src.services.contact_validation_service import contact_readiness, normalize_email, normalize_phone


def parse_resume_input(resume_text: str | None = None, uploaded_file: Any | None = None) -> dict[str, Any]:
    raw_text = (resume_text or "").strip()
    if uploaded_file is not None:
        raw_text = extract_text(uploaded_file)
    if not raw_text:
        return {"status": "needs_review", "error": "Resume text is empty.", "candidate_preview": None}
    profile = extract_candidate_profile(raw_text)
    readiness = contact_readiness(profile)
    preview = {
        **profile,
        "id": profile.get("id") or f"RESUME-{uuid.uuid4().hex[:8].upper()}",
        "email": normalize_email(profile.get("email")),
        "phone": normalize_phone(profile.get("phone")),
        **{key: readiness[key] for key in [
            "contact_readiness_status",
            "contact_readiness_reason",
            "preferred_channel",
            "email_valid",
            "phone_valid",
            "linkedin_valid",
            "email_confidence",
            "phone_confidence",
            "linkedin_confidence",
            "masked_phone",
            "contact_consent_status",
        ]},
    }
    preview["profile_parse_confidence"] = profile.get("profile_parse_confidence", 0)
    log_audit("resume", preview["id"], "resume_parsed", {"status": "preview_ready", "email": preview.get("email"), "linkedin_url": preview.get("linkedin_url")})
    return {"status": "preview_ready", "error": None, "candidate_preview": preview}


def save_parsed_candidate(candidate_payload: dict[str, Any]) -> str:
    candidate_id = upsert_candidate(candidate_payload, source=candidate_payload.get("contact_source", "resume"))
    log_audit("candidate", candidate_id, "resume_candidate_saved", {"contact_source": candidate_payload.get("contact_source", "resume")})
    return candidate_id
