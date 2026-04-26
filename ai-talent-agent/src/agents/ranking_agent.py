from __future__ import annotations

import json
from typing import Any

from src.agent_brain import evaluate_candidate
from src.database.db import db_cursor, fetch_all, fetch_one, json_dumps, utc_now
from src.interest import score_interest
from src.matching import score_candidate
from src.risk import compute_risk
from src.services.audit_service import log_audit
from src.services.feedback_service import feedback_adjustment, list_feedback
from src.utils import compensation_alignment, hash_payload, profile_completeness, round_score


DEFAULT_STAGE = "Sourced"


def compute_scorecard(candidate: dict[str, Any], role: dict[str, Any], parsed_jd: dict[str, Any], conversation: dict[str, Any] | None = None) -> dict[str, Any]:
    controls = {
        "skills_priority": True,
        "remote_first": role.get("work_mode", "") == "remote",
        "required_location": role.get("location", ""),
        "min_years_experience": role.get("experience_min", 0),
    }
    match_result = score_candidate(candidate, parsed_jd, similarity=0.6, controls=controls)
    interest_result = score_interest(candidate, parsed_jd, conversation or _empty_conversation())
    risk_result = compute_risk(candidate, parsed_jd)
    compensation_fit = compensation_alignment(candidate.get("compensation_expectation", ""), parsed_jd)
    availability_fit = interest_result["interest_component_scores"]["availability_timeline"]
    location_fit = match_result["match_component_scores"]["location_work_mode"]
    completeness = round_score(profile_completeness(candidate) * 100)
    decision = evaluate_candidate(parsed_jd, candidate, match_result["match_score"], interest_result["interest_score"])
    weights = role.get("scoring_weights", {})
    match_component = (
        match_result["match_component_scores"]["required_skills"] * weights.get("required_skills_weight", 0.35)
        + match_result["match_component_scores"]["nice_to_have"] * weights.get("nice_to_have_weight", 0.08)
        + match_result["match_component_scores"]["experience_seniority"] * weights.get("experience_weight", 0.12)
        + match_result["match_component_scores"]["domain_relevance"] * weights.get("domain_weight", 0.08)
        + location_fit * weights.get("location_weight", 0.05)
    )
    final_score = round_score(
        match_component
        + interest_result["interest_score"] * weights.get("interest_weight", 0.20)
        + round_score(compensation_fit * 100) * weights.get("compensation_weight", 0.15)
        + availability_fit * weights.get("availability_weight", 0.10)
        + round_score((100 - risk_result["risk_score"])) * weights.get("risk_penalty", 0.10)
    )
    compensation_risk = "high" if compensation_fit < 0.5 else "medium" if compensation_fit < 0.75 else "low"
    return {
        "match_score": match_result["match_score"],
        "interest_score": interest_result["interest_score"],
        "risk_score": risk_result["risk_score"],
        "must_have_skill_score": match_result["match_component_scores"]["required_skills"],
        "nice_to_have_skill_score": match_result["match_component_scores"]["nice_to_have"],
        "experience_score": match_result["match_component_scores"]["experience_seniority"],
        "domain_score": match_result["match_component_scores"]["domain_relevance"],
        "location_score": location_fit,
        "work_mode_score": location_fit,
        "compensation_score": round_score(compensation_fit * 100),
        "availability_score": availability_fit,
        "profile_completeness_score": completeness,
        "final_score": min(100.0, final_score),
        "recommendation": decision["hire_recommendation"],
        "confidence": decision["confidence"],
        "strengths": match_result["strengths"],
        "gaps": match_result["missing_skills"],
        "risk_flags": risk_result["risk_flags"],
        "compensation_fit": round_score(compensation_fit * 100),
        "compensation_risk": compensation_risk,
        "compensation_explanation": _compensation_explanation(candidate, role, compensation_fit),
        "availability_fit": availability_fit,
        "explanation": match_result["explanation"],
        "weights_used": weights,
        "match_component_scores": match_result["match_component_scores"],
        "interest_component_scores": interest_result["interest_component_scores"],
        "decision_reasoning": decision["reasoning"],
        "conversation_summary": interest_result["interest_summary"],
    }


def save_match(candidate_id: str, role_id: int, scorecard: dict[str, Any], stage: str = DEFAULT_STAGE, duplicate_status: dict[str, Any] | None = None, compliance_status: dict[str, Any] | None = None, next_best_action: str | None = None) -> None:
    now = utc_now()
    role_hash = scorecard.get("role_hash")
    candidate_hash = scorecard.get("candidate_hash")
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO candidate_role_match (
                candidate_id, role_id, match_score, interest_score, risk_score, final_score,
                recommendation, next_best_action, stage, scorecard_json, duplicate_status_json,
                compliance_status_json, score_version, role_hash, candidate_hash, scored_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id, role_id) DO UPDATE SET
                match_score=excluded.match_score,
                interest_score=excluded.interest_score,
                risk_score=excluded.risk_score,
                final_score=excluded.final_score,
                recommendation=excluded.recommendation,
                next_best_action=excluded.next_best_action,
                stage=excluded.stage,
                scorecard_json=excluded.scorecard_json,
                duplicate_status_json=excluded.duplicate_status_json,
                compliance_status_json=excluded.compliance_status_json,
                score_version=excluded.score_version,
                role_hash=excluded.role_hash,
                candidate_hash=excluded.candidate_hash,
                scored_at=excluded.scored_at,
                updated_at=excluded.updated_at
            """,
            (
                candidate_id,
                role_id,
                scorecard["match_score"],
                scorecard["interest_score"],
                scorecard["risk_score"],
                scorecard["final_score"],
                scorecard["recommendation"],
                next_best_action,
                stage,
                json_dumps(scorecard),
                json_dumps(duplicate_status or {}),
                json_dumps(compliance_status or {}),
                scorecard.get("score_version", "v2"),
                role_hash,
                candidate_hash,
                now,
                now,
                now,
            ),
        )
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "scoring_run", {"stage": stage, "final_score": scorecard["final_score"]})


def list_matches(role_id: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT m.*, c.full_name, c.current_title, c.location, c.compensation_expectation, c.availability
        FROM candidate_role_match m
        JOIN candidate c ON c.id = m.candidate_id
    """
    params: tuple[Any, ...] = ()
    if role_id is not None:
        query += " WHERE role_id = ?"
        params = (role_id,)
    query += " ORDER BY final_score DESC, updated_at DESC"
    rows = fetch_all(query, params)
    for row in rows:
        row["scorecard"] = json.loads(row.get("scorecard_json") or "{}")
        row["duplicate_status"] = json.loads(row.get("duplicate_status_json") or "{}")
        row["compliance_status"] = json.loads(row.get("compliance_status_json") or "{}")
        row["feedback_adjustment"] = feedback_adjustment(row["candidate_id"], row["role_id"])
        row["adjusted_final_score"] = round_score(float(row.get("final_score", 0)) + row["feedback_adjustment"])
    rows.sort(key=lambda item: item["adjusted_final_score"], reverse=True)
    return rows


def get_match(candidate_id: str, role_id: int) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM candidate_role_match WHERE candidate_id = ? AND role_id = ?", (candidate_id, role_id))
    if not row:
        return None
    row["scorecard"] = json.loads(row.get("scorecard_json") or "{}")
    row["duplicate_status"] = json.loads(row.get("duplicate_status_json") or "{}")
    row["compliance_status"] = json.loads(row.get("compliance_status_json") or "{}")
    return row


def update_match_stage(candidate_id: str, role_id: int, stage: str) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE candidate_role_match SET stage = ?, updated_at = ? WHERE candidate_id = ? AND role_id = ?",
            (stage, utc_now(), candidate_id, role_id),
        )
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "stage_changed", {"stage": stage})


def update_hiring_manager_review(candidate_id: str, role_id: int, status: str, notes: str) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE candidate_role_match
            SET hiring_manager_status = ?, hiring_manager_notes = ?, reviewed_at = ?, updated_at = ?
            WHERE candidate_id = ? AND role_id = ?
            """,
            (status, notes, utc_now(), utc_now(), candidate_id, role_id),
        )
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "hiring_manager_review", {"status": status, "notes": notes})


def feedback_types_for_match(candidate_id: str, role_id: int) -> list[str]:
    return [row["feedback_type"] for row in list_feedback(role_id) if row["candidate_id"] == candidate_id]


def _empty_conversation() -> dict[str, Any]:
    return {
        "candidate_reply": "Thanks for the note. I am open to learning more.",
        "conversation_evidence": ["No real reply captured yet; using neutral interest baseline."],
    }


def _compensation_explanation(candidate: dict[str, Any], role: dict[str, Any], fit: float) -> str:
    if not role.get("salary_min") or not role.get("salary_max"):
        return "Salary band is missing, so recruiter should clarify compensation early."
    if fit >= 0.9:
        return "Candidate compensation expectation appears to fit the role band."
    if fit >= 0.6:
        return "Compensation fit is acceptable but should be validated before interview."
    return f"Candidate expectation may sit outside the role band of ${role['salary_min']:,}-${role['salary_max']:,}."
