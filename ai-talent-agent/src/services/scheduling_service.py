from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3
from typing import Any

from src.database.db import db_cursor, json_dumps, utc_now
from src.services.audit_service import log_audit


def suggested_recruiter_screen_slots(count: int = 3) -> list[str]:
    tomorrow = datetime.now(UTC).replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
    slots = [
        tomorrow,
        tomorrow.replace(hour=15),
        tomorrow.replace(hour=10, minute=30) + timedelta(days=1),
    ]
    return [slot.isoformat() for slot in slots[:count]]


def create_mock_meeting_recommendation(candidate_id: str, role_id: int, slot_time: str | None = None) -> dict[str, Any]:
    slots = suggested_recruiter_screen_slots()
    selected = slot_time or slots[0]
    payload = {
        "type": "mock_recruiter_screen",
        "suggested_slots": slots,
        "note": "Calendar integrations are disabled in this demo build.",
    }
    try:
        with db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO scheduled_interview (
                    candidate_id, role_id, slot_time, duration_minutes, status,
                    event_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (candidate_id, role_id, selected, 30, "recommended", json_dumps(payload), utc_now()),
            )
            interview_id = int(cursor.lastrowid)
    except sqlite3.DatabaseError:
        interview_id = 0
    log_audit("scheduled_interview", interview_id or f"{candidate_id}:{role_id}", "mock_meeting_recommended", {"candidate_id": candidate_id, "role_id": role_id, "slot_time": selected})
    return {"status": "recommended", "interview_id": interview_id, "slot_time": selected, "suggested_slots": slots}
