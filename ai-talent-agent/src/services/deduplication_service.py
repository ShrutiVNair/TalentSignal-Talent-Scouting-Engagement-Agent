from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from src.services.audit_service import log_audit
from src.services.candidate_service import list_candidates
from src.utils import normalize_text


def check_duplicate(candidate: dict[str, Any], candidate_pool: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    pool = candidate_pool or list_candidates()
    matched_ids: list[str] = []
    reasons: list[str] = []
    risk = "none"
    candidate_id = candidate.get("id")

    for existing in pool:
        if existing.get("id") == candidate_id:
            continue
        if candidate.get("email") and existing.get("email") and candidate["email"] == existing["email"]:
            matched_ids.append(existing["id"])
            reasons.append("same email exists")
            risk = "high"
        elif candidate.get("phone") and existing.get("phone") and candidate["phone"] == existing["phone"]:
            matched_ids.append(existing["id"])
            reasons.append("same phone exists")
            risk = "high"
        elif candidate.get("linkedin_url") and existing.get("linkedin_url") and candidate["linkedin_url"] == existing["linkedin_url"]:
            matched_ids.append(existing["id"])
            reasons.append("same LinkedIn URL")
            risk = "high"
        elif candidate.get("github_url") and existing.get("github_url") and candidate["github_url"] == existing["github_url"]:
            matched_ids.append(existing["id"])
            reasons.append("same GitHub URL")
            risk = max_risk(risk, "medium")
        else:
            name_score = SequenceMatcher(None, normalize_text(candidate.get("name", "")), normalize_text(existing.get("name", ""))).ratio()
            same_company = normalize_text(candidate.get("current_company", "")) and normalize_text(candidate.get("current_company", "")) == normalize_text(existing.get("current_company", ""))
            same_location = normalize_text(candidate.get("location", "")) == normalize_text(existing.get("location", ""))
            if name_score >= 0.90 and same_company:
                matched_ids.append(existing["id"])
                reasons.append("similar name and same company")
                risk = max_risk(risk, "medium")
            elif name_score >= 0.92 and same_location:
                matched_ids.append(existing["id"])
                reasons.append("similar name and same location")
                risk = max_risk(risk, "low")

    explanation = "No duplicate signals detected."
    action = "Proceed"
    if reasons:
        explanation = f"Possible duplicate found: {', '.join(sorted(set(reasons)))}."
    if risk == "high":
        action = "Block outreach pending recruiter review"
    elif risk == "medium":
        action = "Review before outreach"

    result = {
        "duplicate_risk": risk,
        "matched_candidate_ids": sorted(set(matched_ids)),
        "explanation": explanation,
        "recommended_action": action,
    }
    log_audit("candidate", candidate_id or "unknown", "duplicate_check", result)
    return result


def max_risk(current: str, new: str) -> str:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    return new if order[new] > order[current] else current

