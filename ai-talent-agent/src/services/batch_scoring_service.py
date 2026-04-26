from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from src.agents.next_best_action import decide_next_best_action
from src.database.db import db_cursor, fetch_all, fetch_one, json_dumps, utc_now
from src.interest import score_interest
from src.matching import score_candidate
from src.risk import compute_risk
from src.services.audit_service import log_audit
from src.services.candidate_service import get_candidate, list_candidates_page
from src.services.feedback_service import feedback_adjustment
from src.services.role_service import get_role
from src.utils import compensation_alignment, hash_payload, profile_completeness, round_score


SCORE_VERSION = "fast_v1"


@lru_cache(maxsize=64)
def get_top_matches(role_id: int, limit: int = 50) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT m.*, c.full_name, c.current_title, c.location, c.current_company, c.contact_readiness_status, c.preferred_channel
        FROM candidate_role_match m
        JOIN candidate c ON c.id = m.candidate_id
        WHERE m.role_id = ?
        ORDER BY m.final_score DESC, m.updated_at DESC
        LIMIT ?
        """,
        (role_id, limit),
    )
    return [_decode_match_row(row) for row in rows]


def get_cached_scores(role_id: int) -> list[dict[str, Any]]:
    rows = fetch_all("SELECT * FROM candidate_role_match WHERE role_id = ? ORDER BY final_score DESC, updated_at DESC", (role_id,))
    return [_decode_match_row(row) for row in rows]


def invalidate_scores_for_role(role_id: int) -> None:
    get_top_matches.cache_clear()


def _decode_match_row(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row["scorecard"] = json.loads(row.get("scorecard_json") or "{}")
    row["duplicate_status"] = json.loads(row.get("duplicate_status_json") or "{}")
    row["compliance_status"] = json.loads(row.get("compliance_status_json") or "{}")
    return row


def score_candidates_for_role(
    role_id: int,
    candidate_ids: list[str] | None = None,
    limit: int | None = None,
    batch_size: int = 500,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    role = get_role(role_id)
    if not role:
        return {"processed_count": 0, "scored_count": 0, "warnings": ["Role not found."]}
    if candidate_ids is None:
        page_size = min(limit or 1000, 1000)
        page = 1
        candidate_rows: list[dict[str, Any]] = []
        while True:
            page_result = list_candidates_page(page=page, page_size=page_size)
            if not page_result["items"]:
                break
            candidate_rows.extend(page_result["items"])
            if limit and len(candidate_rows) >= limit:
                candidate_rows = candidate_rows[:limit]
                break
            if page >= page_result["pages"]:
                break
            page += 1
    else:
        candidate_rows = [candidate for candidate_id in candidate_ids if (candidate := get_candidate(candidate_id))]

    total = len(candidate_rows)
    scored_count = 0
    for start in range(0, total, batch_size):
        chunk = candidate_rows[start : start + batch_size]
        score_candidate_batch(role, chunk)
        scored_count += len(chunk)
        if progress_callback:
            progress_callback(min(scored_count / max(total, 1), 1.0), scored_count, total)

    invalidate_scores_for_role(role_id)
    return {"processed_count": total, "scored_count": scored_count, "warnings": []}


def score_candidate_batch(role: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed_jd = {
        "role_title": role.get("title", ""),
        "required_skills": role.get("required_skills", []),
        "nice_to_have_skills": role.get("nice_to_have_skills", []),
        "years_experience": role.get("experience_min", 0),
        "seniority": "senior" if (role.get("experience_min") or 0) >= 5 else "mid",
        "location_preference": role.get("location", "Flexible"),
        "work_mode": role.get("work_mode", "flexible"),
        "responsibilities": [],
        "must_have_constraints": [],
        "search_keywords": [role.get("title", ""), *role.get("required_skills", [])],
    }
    controls = {
        "skills_priority": True,
        "remote_first": role.get("work_mode", "") == "remote",
        "required_location": role.get("location", ""),
        "min_years_experience": role.get("experience_min", 0),
    }
    rows = []
    persisted_rows = []
    for candidate in candidates:
        match_result = score_candidate(candidate, parsed_jd, similarity=0.6, controls=controls)
        interest_result = score_interest(candidate, parsed_jd, _empty_conversation())
        risk_result = compute_risk(candidate, parsed_jd)
        scorecard = _build_fast_scorecard(candidate, role, parsed_jd, match_result, interest_result, risk_result)
        next_action = decide_next_best_action(
            scorecard,
            {"outreach_allowed": True, "reasons": []},
            {"duplicate_risk": "none"},
            "Shortlisted",
        )
        rows.append(scorecard)
        persisted_rows.append(
            (
                candidate["id"],
                role["id"],
                scorecard["match_score"],
                scorecard["interest_score"],
                scorecard["risk_score"],
                scorecard["final_score"],
                scorecard["recommendation"],
                next_action["action"],
                "Shortlisted",
                json_dumps(scorecard),
                json_dumps({"duplicate_risk": "none"}),
                json_dumps({"outreach_allowed": True}),
                scorecard.get("score_version", SCORE_VERSION),
                scorecard.get("role_hash"),
                scorecard.get("candidate_hash"),
                utc_now(),
                utc_now(),
                utc_now(),
            )
        )
    _persist_scorecards_batch(persisted_rows)
    if persisted_rows:
        log_audit(
            "role",
            role["id"],
            "batch_scoring_run",
            {"candidate_count": len(persisted_rows), "score_version": SCORE_VERSION},
        )
    return rows


def _persist_scorecards_batch(rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    with db_cursor() as cursor:
        cursor.executemany(
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
            rows,
        )


def _build_fast_scorecard(
    candidate: dict[str, Any],
    role: dict[str, Any],
    parsed_jd: dict[str, Any],
    match_result: dict[str, Any],
    interest_result: dict[str, Any],
    risk_result: dict[str, Any],
) -> dict[str, Any]:
    weights = role.get("scoring_weights", {})
    compensation_fit = compensation_alignment(candidate.get("compensation_expectation", ""), parsed_jd)
    availability_fit = interest_result["interest_component_scores"]["availability_timeline"]
    location_fit = match_result["match_component_scores"]["location_work_mode"]
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
    recommendation = _fast_recommendation(match_result["match_score"], interest_result["interest_score"])
    candidate_hash = hash_payload(candidate.get("id"), candidate.get("updated_at"), candidate.get("resume_hash"), candidate.get("searchable_text"))
    role_hash = role.get("role_hash") or hash_payload(role.get("id"), role.get("updated_at"), role.get("title"))
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
        "profile_completeness_score": round_score(profile_completeness(candidate) * 100),
        "final_score": min(100.0, final_score + feedback_adjustment(candidate["id"], role["id"])),
        "recommendation": recommendation,
        "confidence": _fast_confidence(match_result["match_score"], interest_result["interest_score"]),
        "strengths": match_result["strengths"],
        "gaps": match_result["missing_skills"],
        "risk_flags": risk_result["risk_flags"],
        "compensation_fit": round_score(compensation_fit * 100),
        "compensation_risk": "high" if compensation_fit < 0.5 else "medium" if compensation_fit < 0.75 else "low",
        "compensation_explanation": "Compensation fit is derived from the role band and stated candidate expectation.",
        "availability_fit": availability_fit,
        "explanation": match_result["explanation"],
        "weights_used": weights,
        "match_component_scores": match_result["match_component_scores"],
        "interest_component_scores": interest_result["interest_component_scores"],
        "decision_reasoning": "Deterministic fast scoring path used for recruiter workflow and large candidate pools.",
        "conversation_summary": interest_result["interest_summary"],
        "score_version": SCORE_VERSION,
        "role_hash": role_hash,
        "candidate_hash": candidate_hash,
        "scored_at": utc_now(),
    }


def _empty_conversation() -> dict[str, Any]:
    return {
        "candidate_reply": "Thanks for the note. I am open to learning more.",
        "conversation_evidence": ["Fast scoring path using neutral conversation baseline."],
    }


def _fast_recommendation(match_score: float, interest_score: float) -> str:
    if match_score >= 78 and interest_score >= 68:
        return "Strong Yes"
    if match_score >= 62 and interest_score >= 45:
        return "Maybe"
    return "No"


def _fast_confidence(match_score: float, interest_score: float) -> float:
    combined = round_score(match_score * 0.6 + interest_score * 0.4)
    if combined >= 80:
        return 82.0
    if combined >= 65:
        return 71.0
    return 58.0
