from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.database.db import db_cursor, fetch_one, utc_now
from src.services.audit_service import log_audit


PROTECTED_TOKENS = [
    "gender",
    "age",
    "race",
    "religion",
    "disability",
    "marital",
    "pregnancy",
    "nationality",
    "health",
    "political",
]


def get_compliance_record(candidate_id: str) -> dict[str, Any]:
    record = fetch_one("SELECT * FROM compliance_record WHERE candidate_id = ?", (candidate_id,))
    return record or {
        "candidate_id": candidate_id,
        "opt_out": 0,
        "do_not_contact": 0,
        "gdpr_delete_requested": 0,
        "last_contacted_at": None,
        "cooldown_until": None,
        "compliance_notes": "",
    }


def upsert_compliance(candidate_id: str, updates: dict[str, Any]) -> None:
    current = get_compliance_record(candidate_id)
    merged = {**current, **updates}
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO compliance_record (
                candidate_id, opt_out, do_not_contact, gdpr_delete_requested,
                last_contacted_at, cooldown_until, compliance_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                opt_out=excluded.opt_out,
                do_not_contact=excluded.do_not_contact,
                gdpr_delete_requested=excluded.gdpr_delete_requested,
                last_contacted_at=excluded.last_contacted_at,
                cooldown_until=excluded.cooldown_until,
                compliance_notes=excluded.compliance_notes
            """,
            (
                candidate_id,
                int(bool(merged.get("opt_out"))),
                int(bool(merged.get("do_not_contact"))),
                int(bool(merged.get("gdpr_delete_requested"))),
                merged.get("last_contacted_at"),
                merged.get("cooldown_until"),
                merged.get("compliance_notes", ""),
            ),
        )
    log_audit("candidate", candidate_id, "compliance_updated", updates)


def detect_protected_attribute_mentions(*texts: str) -> list[str]:
    haystack = " ".join(texts).lower()
    return [token for token in PROTECTED_TOKENS if token in haystack]


def evaluate_compliance(
    candidate: dict[str, Any],
    role: dict[str, Any],
    duplicate_result: dict[str, Any],
    active_other_process: bool = False,
    recent_rejection: bool = False,
) -> dict[str, Any]:
    record = get_compliance_record(candidate["id"])
    protected_hits = detect_protected_attribute_mentions(candidate.get("resume_text", ""), role.get("jd_text", ""))
    now = datetime.now(UTC)
    cooldown_until = record.get("cooldown_until")
    in_cooldown = bool(cooldown_until and datetime.fromisoformat(cooldown_until) > now)
    allowed = not any(
        [
            bool(record.get("opt_out")),
            bool(record.get("do_not_contact")),
            in_cooldown,
            recent_rejection,
            active_other_process,
            duplicate_result.get("duplicate_risk") == "high",
        ]
    )
    reasons = []
    if record.get("opt_out"):
        reasons.append("Candidate opted out")
    if record.get("do_not_contact"):
        reasons.append("Candidate marked do-not-contact")
    if in_cooldown:
        reasons.append("Candidate in cooldown period")
    if recent_rejection:
        reasons.append("Recently rejected for similar role")
    if active_other_process:
        reasons.append("Candidate active in another process")
    if duplicate_result.get("duplicate_risk") == "high":
        reasons.append("High duplicate risk")
    if protected_hits:
        reasons.append("Protected attributes detected and excluded from scoring")
    result = {
        "outreach_allowed": allowed,
        "opt_out": bool(record.get("opt_out")),
        "do_not_contact": bool(record.get("do_not_contact")),
        "last_contacted_at": record.get("last_contacted_at"),
        "cooldown_until": record.get("cooldown_until"),
        "duplicate_status": duplicate_result,
        "protected_attribute_warning": protected_hits,
        "reasons": reasons or ["No compliance blockers found"],
        "audit_log_available": True,
    }
    log_audit("candidate", candidate["id"], "compliance_check", result)
    return result


def mark_contacted(candidate_id: str) -> None:
    upsert_compliance(candidate_id, {"last_contacted_at": utc_now()})

