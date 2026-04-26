from __future__ import annotations

from typing import Any

from src.matching import intersect_skills
from src.utils import (
    availability_to_days,
    compensation_alignment,
    infer_seniority,
    location_alignment,
    normalize_text,
    round_score,
    seniority_value,
    unique_list,
    work_mode_alignment,
)


def compute_risk(candidate: dict[str, Any], jd: dict[str, Any]) -> dict[str, Any]:
    """Compute rule-based candidate risk signals without using an LLM."""

    flags: list[str] = []
    risk_points = 0

    compensation_fit = compensation_alignment(candidate.get("compensation_expectation", ""), jd)
    if compensation_fit < 0.65:
        flags.append("Compensation mismatch risk")
        risk_points += 28

    matched_skills = intersect_skills(
        jd.get("required_skills", []),
        candidate.get("skills", []) + candidate.get("nice_to_have_skills", []),
    )
    missing_count = max(len(jd.get("required_skills", [])) - len(matched_skills), 0)
    if missing_count >= 2:
        flags.append(f"Skill gap risk: missing {missing_count} required skills")
        risk_points += min(34, missing_count * 12)
    elif missing_count == 1:
        flags.append("Minor skill gap risk")
        risk_points += 10

    location_fit = location_alignment(
        candidate.get("location", ""),
        str(jd.get("location_preference", "Flexible")),
        remote_first=False,
    )
    mode_fit = work_mode_alignment(
        candidate.get("work_mode_preference", ""),
        str(jd.get("work_mode", "flexible")),
        remote_first=False,
    )
    if (location_fit + mode_fit) / 2 < 0.55:
        flags.append("Location/work-mode mismatch risk")
        risk_points += 18

    availability_days = availability_to_days(candidate.get("availability", ""))
    if availability_days > 45:
        flags.append("Low availability risk")
        risk_points += 22
    elif availability_days > 21:
        flags.append("Delayed availability risk")
        risk_points += 12

    if _is_flight_risk(candidate, jd):
        flags.append("Possible job hopping / flight risk")
        risk_points += 16

    risk_score = min(100, round_score(risk_points))
    flags = unique_list(flags)
    summary = _summarize_risk(flags, risk_score)
    return {
        "risk_score": risk_score,
        "risk_flags": flags,
        "risk_summary": summary,
    }


def derive_rejection_reasons(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    match_score: float,
) -> list[str]:
    """Return recruiter-facing rejection reasons for non-selected candidates."""

    reasons: list[str] = []
    risk = compute_risk(candidate, jd)
    matched_skills = intersect_skills(
        jd.get("required_skills", []),
        candidate.get("skills", []) + candidate.get("nice_to_have_skills", []),
    )
    if len(matched_skills) < max(1, len(jd.get("required_skills", [])) // 2):
        reasons.append("Missing required skills")
    if candidate.get("engagement_persona") in {"not_interested", "skeptical", "slow_responder"}:
        reasons.append("Low interest likelihood")
    if "compensation mismatch" in risk["risk_summary"].lower() or "Compensation mismatch risk" in risk["risk_flags"]:
        reasons.append("High compensation mismatch")
    if risk["risk_score"] >= 60:
        reasons.append("Overall risk too high for current shortlist")
    if match_score < 60:
        reasons.append("Below shortlist threshold on match quality")
    return reasons[:3] or ["Not prioritized against stronger shortlisted candidates"]


def _is_flight_risk(candidate: dict[str, Any], jd: dict[str, Any]) -> bool:
    candidate_seniority = seniority_value(infer_seniority(candidate.get("current_title", "")))
    jd_seniority = seniority_value(str(jd.get("seniority", "mid")))
    overleveled = candidate_seniority - jd_seniority >= 2
    compensation_persona = normalize_text(candidate.get("engagement_persona", "")) == "compensation_driven"
    years_gap = candidate.get("years_experience", 0) >= jd.get("years_experience", 0) + 6
    return overleveled or (compensation_persona and years_gap)


def _summarize_risk(flags: list[str], risk_score: float) -> str:
    if not flags:
        return "Low risk profile with no major blockers detected by the rule-based risk engine."
    if risk_score >= 60:
        return f"High risk profile driven by {', '.join(flags[:2]).lower()}."
    if risk_score >= 30:
        return f"Moderate risk profile driven by {', '.join(flags[:2]).lower()}."
    return f"Limited risk profile, with watchouts around {', '.join(flags[:2]).lower()}."
