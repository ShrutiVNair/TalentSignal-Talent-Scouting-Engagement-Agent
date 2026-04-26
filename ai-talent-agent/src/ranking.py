from __future__ import annotations

from typing import Any

from src.llm_client import call_llm
from src.utils import main_risk, round_score, top_strength


def build_ranked_shortlist(
    candidate_runs: list[dict[str, Any]],
    match_weight: float,
    interest_weight: float,
) -> list[dict[str, Any]]:
    """Build the recruiter-facing shortlist while keeping final score formula unchanged."""

    total = match_weight + interest_weight
    normalized_match = match_weight / total if total else 0.65
    normalized_interest = interest_weight / total if total else 0.35

    ranked_rows: list[dict[str, Any]] = []
    for run in candidate_runs:
        final_score = round_score(
            run["match_score"] * normalized_match + run["interest_score"] * normalized_interest
        )
        next_action = _next_action(run)
        row = {
            **run,
            "final_score": final_score,
            "next_action": next_action,
            "top_strength": run.get("top_strength") or top_strength(run.get("strengths", [])),
            "main_risk": run.get("risk_summary") or run.get("main_risk") or main_risk(run.get("risk_flags", [])),
        }
        ranked_rows.append(row)

    ranked_rows.sort(
        key=lambda item: (item["final_score"], item.get("confidence", 0), -item.get("risk_score", 0)),
        reverse=True,
    )
    for index, row in enumerate(ranked_rows, start=1):
        row["rank"] = index
    return ranked_rows


def build_shortlist_summary(ranked_rows: list[dict[str, Any]]) -> str:
    """Create a recruiter-friendly top-level summary of the shortlist."""

    if not ranked_rows:
        return "No shortlisted candidates yet. Run outreach and interest analysis to produce a ranked summary."

    top_rows = ranked_rows[:3]
    interview_ready = sum(
        1
        for row in top_rows
        if row.get("hire_recommendation") == "Strong Yes" and row.get("risk_score", 0) < 40
    )
    compensation_watch = sum(
        1 for row in top_rows if "compensation" in row.get("risk_summary", "").lower()
    )
    high_risk = sum(1 for row in top_rows if row.get("risk_score", 0) >= 60)

    summary_parts = [f"Top {len(top_rows)} candidates identified."]
    if interview_ready:
        summary_parts.append(f"{interview_ready} ready to interview immediately.")
    if compensation_watch:
        summary_parts.append(f"{compensation_watch} requires compensation alignment.")
    if high_risk:
        summary_parts.append(f"{high_risk} is high-risk despite strong upside.")
    if len(summary_parts) == 1:
        summary_parts.append("The current shortlist is balanced and ready for recruiter review.")
    return " ".join(summary_parts)


def generate_shortlist_summary(ranked_rows: list[dict[str, Any]]) -> str:
    """Generate a recruiter-friendly shortlist summary with LLM fallback."""

    fallback_summary = build_shortlist_summary(ranked_rows)
    if not ranked_rows:
        return fallback_summary
    top_rows = ranked_rows[:3]
    prompt = (
        "Write one short recruiter-friendly summary sentence for this shortlist. "
        "Mention interview-ready candidates, compensation watchouts, or risk if relevant.\n\n"
        + "\n".join(
            f"{row['candidate']['name']}: recommendation={row.get('hire_recommendation')}, "
            f"risk={row.get('risk_score')}, next_action={row.get('next_action')}"
            for row in top_rows
        )
    )
    response = call_llm(prompt, temperature=0.2).strip()
    return response or fallback_summary


def apply_feedback_adjustments(
    ranked_rows: list[dict[str, Any]],
    feedback_map: dict[str, int],
) -> list[dict[str, Any]]:
    """Adjust ranking slightly based on recruiter feedback for similar profiles."""

    adjusted_rows: list[dict[str, Any]] = []
    negative_rows = [row for row in ranked_rows if feedback_map.get(row["candidate_id"]) == -1]
    positive_rows = [row for row in ranked_rows if feedback_map.get(row["candidate_id"]) == 1]

    for row in ranked_rows:
        adjustment = float(feedback_map.get(row["candidate_id"], 0)) * 2.5
        for negative in negative_rows:
            if negative["candidate_id"] != row["candidate_id"] and _is_similar_profile(row, negative):
                adjustment -= 1.5
        for positive in positive_rows:
            if positive["candidate_id"] != row["candidate_id"] and _is_similar_profile(row, positive):
                adjustment += 1.0

        updated = {
            **row,
            "feedback_adjustment": round_score(adjustment),
            "adjusted_final_score": round_score(row["final_score"] + adjustment),
        }
        adjusted_rows.append(updated)

    adjusted_rows.sort(
        key=lambda item: (
            item["adjusted_final_score"],
            item.get("confidence", 0),
            -item.get("risk_score", 0),
        ),
        reverse=True,
    )
    for index, row in enumerate(adjusted_rows, start=1):
        row["rank"] = index
    return adjusted_rows


def _next_action(run: dict[str, Any]) -> str:
    if run.get("hire_recommendation") == "Strong Yes" and run.get("risk_score", 0) < 40:
        return "Schedule interview"
    if "compensation" in " ".join(run.get("risk_flags", [])).lower():
        return "Clarify compensation"
    if run.get("hire_recommendation") == "No" or run.get("risk_score", 0) >= 70:
        return "Reject"
    return run.get("recommended_next_action", "Review with recruiter")


def _is_similar_profile(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_candidate = left["candidate"]
    right_candidate = right["candidate"]
    left_skills = set(left_candidate.get("skills", []))
    right_skills = set(right_candidate.get("skills", []))
    skill_overlap = len(left_skills & right_skills)
    same_persona = left_candidate.get("engagement_persona") == right_candidate.get("engagement_persona")
    same_title_family = left_candidate.get("current_title", "").split()[:2] == right_candidate.get("current_title", "").split()[:2]
    return skill_overlap >= 2 or same_persona or same_title_family
