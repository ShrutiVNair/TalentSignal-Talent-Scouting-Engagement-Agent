from __future__ import annotations

from typing import Any


def decide_next_best_action(scorecard: dict[str, Any], compliance: dict[str, Any], duplicate_result: dict[str, Any], stage: str, feedback_types: list[str] | None = None) -> dict[str, str]:
    feedback = set(feedback_types or [])
    if not compliance.get("outreach_allowed"):
        return {"action": "Do not contact", "reason": "; ".join(compliance.get("reasons", []))}
    if duplicate_result.get("duplicate_risk") == "high":
        return {"action": "Ask hiring manager to review", "reason": duplicate_result.get("explanation", "")}
    if "candidate_responded_positive" in feedback or stage == "Responded":
        return {"action": "Schedule recruiter screen", "reason": "Candidate is engaged and compliant."}
    if scorecard.get("compensation_risk") == "high":
        return {"action": "Send compensation clarification", "reason": scorecard.get("compensation_explanation", "")}
    if stage == "Contacted":
        return {"action": "Wait and follow up", "reason": "Outreach already started; follow-up cadence is active."}
    if scorecard.get("final_score", 0) >= 80:
        return {"action": "Contact now", "reason": "High score, low risk, and compliant profile."}
    if scorecard.get("final_score", 0) >= 65:
        return {"action": "Ask hiring manager to review", "reason": "Promising profile with some tradeoffs."}
    if scorecard.get("match_score", 0) < 50:
        return {"action": "Archive", "reason": "Low role fit based on explainable scoring."}
    return {"action": "Add to nurture campaign", "reason": "Not urgent for this role, but still potentially useful later."}

