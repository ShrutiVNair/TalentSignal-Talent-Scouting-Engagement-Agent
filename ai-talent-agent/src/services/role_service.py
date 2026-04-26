from __future__ import annotations

import json
from typing import Any

from src.database.db import db_cursor, fetch_all, fetch_one, json_dumps, utc_now
from src.services.audit_service import log_audit
from src.utils import hash_payload, tokenize_skills


DEFAULT_SCORING_WEIGHTS = {
    "required_skills_weight": 0.35,
    "nice_to_have_weight": 0.08,
    "experience_weight": 0.12,
    "domain_weight": 0.08,
    "location_weight": 0.05,
    "compensation_weight": 0.15,
    "availability_weight": 0.10,
    "interest_weight": 0.20,
    "risk_penalty": 0.10,
}


def _decode_role(row: dict[str, Any]) -> dict[str, Any]:
    role = dict(row)
    role["required_skills"] = json.loads(role.get("required_skills") or "[]")
    role["nice_to_have_skills"] = json.loads(role.get("nice_to_have_skills") or "[]")
    role["normalized_required_skills"] = json.loads(role.get("normalized_required_skills") or "[]")
    role["normalized_nice_to_have_skills"] = json.loads(role.get("normalized_nice_to_have_skills") or "[]")
    role["scoring_weights"] = json.loads(role.get("scoring_weights_json") or json_dumps(DEFAULT_SCORING_WEIGHTS))
    role["calibration"] = json.loads(role.get("calibration_json") or "{}")
    return role


def list_roles() -> list[dict[str, Any]]:
    return [_decode_role(row) for row in fetch_all("SELECT * FROM role ORDER BY updated_at DESC")]


def get_role(role_id: int) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM role WHERE id = ?", (role_id,))
    return _decode_role(row) if row else None


def create_role(role_payload: dict[str, Any], calibration: dict[str, Any] | None = None) -> int:
    now = utc_now()
    weights = role_payload.get("scoring_weights") or DEFAULT_SCORING_WEIGHTS
    required_skills = role_payload.get("required_skills", [])
    nice_to_have = role_payload.get("nice_to_have_skills", [])
    normalized_required = tokenize_skills(required_skills)
    normalized_nice = tokenize_skills(nice_to_have)
    role_hash = hash_payload(
        role_payload.get("title"),
        required_skills,
        nice_to_have,
        role_payload.get("location"),
        role_payload.get("work_mode"),
        role_payload.get("experience_min"),
        role_payload.get("experience_max"),
        role_payload.get("salary_min"),
        role_payload.get("salary_max"),
    )
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO role (
                title, department, hiring_manager, location, work_mode, salary_min, salary_max,
                required_skills, nice_to_have_skills, experience_min, experience_max,
                jd_text, status, scoring_weights_json, calibration_json, normalized_required_skills,
                normalized_nice_to_have_skills, role_hash, interview_process, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                role_payload.get("title"),
                role_payload.get("department"),
                role_payload.get("hiring_manager"),
                role_payload.get("location"),
                role_payload.get("work_mode"),
                role_payload.get("salary_min"),
                role_payload.get("salary_max"),
                json_dumps(required_skills),
                json_dumps(nice_to_have),
                role_payload.get("experience_min"),
                role_payload.get("experience_max"),
                role_payload.get("jd_text"),
                role_payload.get("status", "Open"),
                json_dumps(weights),
                json_dumps(calibration or {}),
                json_dumps(normalized_required),
                json_dumps(normalized_nice),
                role_hash,
                role_payload.get("interview_process"),
                now,
                now,
            ),
        )
        role_id = int(cursor.lastrowid)
    log_audit("role", role_id, "role_created", {"title": role_payload.get("title")})
    try:
        from src.services.batch_scoring_service import get_top_matches

        get_top_matches.cache_clear()
    except Exception:
        pass
    return role_id


def update_role_weights(role_id: int, weights: dict[str, float]) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE role SET scoring_weights_json = ?, updated_at = ? WHERE id = ?",
            (json_dumps(weights), utc_now(), role_id),
        )
    log_audit("role", role_id, "scoring_weights_changed", {"weights": weights})
    try:
        from src.services.batch_scoring_service import get_top_matches

        get_top_matches.cache_clear()
    except Exception:
        pass


def role_options() -> list[tuple[int, str]]:
    return [(role["id"], role["title"]) for role in list_roles()]
