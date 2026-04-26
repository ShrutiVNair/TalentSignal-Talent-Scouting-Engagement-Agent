from __future__ import annotations

from typing import Any

from src.database.db import execute, fetch_all, utc_now
from src.services.audit_service import log_audit


FEEDBACK_IMPACT = {
    "bad_match": -7.0,
    "duplicate_candidate": -8.0,
    "salary_mismatch": -5.0,
    "hiring_manager_rejected": -10.0,
    "candidate_not_interested": -6.0,
    "good_match": 3.0,
    "candidate_responded_positive": 5.0,
    "converted_to_interview": 8.0,
    "offer_accepted": 10.0,
}


def add_feedback(candidate_id: str, role_id: int, feedback_type: str, notes: str = "") -> None:
    execute(
        "INSERT INTO feedback (candidate_id, role_id, feedback_type, notes, created_at) VALUES (?, ?, ?, ?, ?)",
        (candidate_id, role_id, feedback_type, notes, utc_now()),
    )
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "feedback_submitted", {"feedback_type": feedback_type, "notes": notes})


def list_feedback(role_id: int | None = None) -> list[dict[str, Any]]:
    if role_id is None:
        return fetch_all("SELECT * FROM feedback ORDER BY created_at DESC")
    return fetch_all("SELECT * FROM feedback WHERE role_id = ? ORDER BY created_at DESC", (role_id,))


def feedback_adjustment(candidate_id: str, role_id: int) -> float:
    total = 0.0
    for row in list_feedback(role_id):
        if row["candidate_id"] == candidate_id:
            total += FEEDBACK_IMPACT.get(row["feedback_type"], 0.0)
    return total

