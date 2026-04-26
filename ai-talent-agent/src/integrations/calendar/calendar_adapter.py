from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.database.db import db_cursor, json_dumps, utc_now
from src.services.audit_service import log_audit


class MockCalendarAdapter:
    def get_available_slots(self, recruiter_id: str, duration_minutes: int) -> list[str]:
        start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(days=1, hours=10)
        return [(start + timedelta(days=index, hours=index % 2)).isoformat() for index in range(5)]

    def create_interview_event(self, candidate: dict[str, Any], role: dict[str, Any], slot: str, duration_minutes: int = 30) -> dict[str, Any]:
        with db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO scheduled_interview (candidate_id, role_id, slot_time, duration_minutes, status, event_payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate["id"],
                    role["id"],
                    slot,
                    duration_minutes,
                    "scheduled",
                    json_dumps({"candidate": candidate["name"], "role": role["title"]}),
                    utc_now(),
                ),
            )
            event_id = int(cursor.lastrowid)
        log_audit("scheduled_interview", event_id, "schedule_created", {"candidate_id": candidate["id"], "role_id": role["id"], "slot": slot})
        return {"status": "scheduled", "event_id": event_id, "slot": slot}

    def send_scheduling_link(self, candidate: dict[str, Any]) -> dict[str, str]:
        return {"status": "mocked", "link": f"https://demo.local/schedule/{candidate['id']}"}

