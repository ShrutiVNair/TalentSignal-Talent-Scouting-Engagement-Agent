from __future__ import annotations

import json
import uuid
from typing import Any

from src.database.db import db_cursor, fetch_all, fetch_one, json_dumps, utc_now
from src.integrations.communication.email_adapter import send_email_draft
from src.integrations.communication.slack_adapter import send_slack_alert
from src.integrations.communication.teams_adapter import send_teams_alert
from src.integrations.communication.whatsapp_adapter import send_whatsapp_mock
from src.integrations import send_sms
from src.services.audit_service import log_audit
from src.services.compliance_service import mark_contacted


DEFAULT_SEQUENCE_STEPS = [
    {"step_number": 1, "day_offset": 0, "channel": "email", "label": "Initial outreach"},
    {"step_number": 2, "day_offset": 2, "channel": "linkedin_task", "label": "LinkedIn follow-up"},
    {"step_number": 3, "day_offset": 4, "channel": "sms", "label": "SMS nudge"},
    {"step_number": 4, "day_offset": 7, "channel": "email", "label": "Soft follow-up"},
    {"step_number": 5, "day_offset": 14, "channel": "system", "label": "Mark cold if no response"},
]


def save_outreach_message(
    candidate_id: str,
    role_id: int,
    channel: str,
    message_body: str,
    status: str = "draft",
    delivery_status: str = "Draft only",
    sequence_id: str | None = None,
    step_number: int = 0,
    metadata: dict[str, Any] | None = None,
) -> int:
    now = utc_now()
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO outreach_message (
                candidate_id, role_id, channel, message_body, status, sent_at, delivery_status,
                reply_text, reply_received_at, sequence_id, step_number, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                role_id,
                channel,
                message_body,
                status,
                now if status == "sent" else None,
                delivery_status,
                None,
                None,
                sequence_id,
                step_number,
                json_dumps(metadata or {}),
                now,
                now,
            ),
        )
        message_id = int(cursor.lastrowid)
    log_audit("outreach_message", message_id, "outreach_generated", {"candidate_id": candidate_id, "role_id": role_id, "channel": channel})
    return message_id


def list_messages(candidate_id: str | None = None, role_id: int | None = None) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    query = "SELECT * FROM outreach_message"
    if candidate_id:
        clauses.append("candidate_id = ?")
        params.append(candidate_id)
    if role_id is not None:
        clauses.append("role_id = ?")
        params.append(role_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    rows = fetch_all(query, tuple(params))
    for row in rows:
        row["metadata"] = json.loads(row.get("metadata_json") or "{}")
    return rows


def create_sequence(candidate_id: str, role_id: int, base_message: str) -> dict[str, Any]:
    sequence_id = f"SEQ-{uuid.uuid4().hex[:10]}"
    now = utc_now()
    steps = []
    for template_step in DEFAULT_SEQUENCE_STEPS:
        step = {
            **template_step,
            "status": "scheduled" if template_step["channel"] != "system" else "pending",
            "message_template": base_message if template_step["step_number"] == 1 else "",
        }
        steps.append(step)
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT OR REPLACE INTO outreach_sequence (id, candidate_id, role_id, status, steps_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sequence_id, candidate_id, role_id, "active", json_dumps(steps), now, now),
        )
    log_audit("outreach_sequence", sequence_id, "sequence_created", {"candidate_id": candidate_id, "role_id": role_id})
    return {"sequence_id": sequence_id, "steps": steps}


def get_sequence(sequence_id: str) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM outreach_sequence WHERE id = ?", (sequence_id,))
    if not row:
        return None
    row["steps"] = json.loads(row.get("steps_json") or "[]")
    return row


def trigger_sequence_step(
    candidate: dict[str, Any],
    role: dict[str, Any],
    sequence_id: str,
    step_number: int,
    mode: str,
    message_body: str,
) -> dict[str, Any]:
    sequence = get_sequence(sequence_id)
    if not sequence:
        return {"status": "failed", "error": "Sequence not found"}
    step = next((item for item in sequence["steps"] if item["step_number"] == step_number), None)
    if not step:
        return {"status": "failed", "error": "Step not found"}
    channel = step["channel"]
    if mode == "demo":
        status = {"status": "draft", "delivery_status": f"{channel} queued in demo mode"}
    elif channel == "sms":
        status = send_sms(message_body, candidate.get("phone", ""))
        status["delivery_status"] = "SMS sent" if status["status"] == "sent" else status.get("error", "SMS failed")
    elif channel == "email":
        status = send_email_draft(candidate, role, message_body, draft_only=True)
    elif channel == "whatsapp":
        status = send_whatsapp_mock(candidate, message_body)
    elif channel == "slack_alert":
        status = send_slack_alert(f"Candidate {candidate['name']} ready for recruiter action")
    elif channel == "teams_alert":
        status = send_teams_alert(f"Candidate {candidate['name']} ready for recruiter action")
    else:
        status = {"status": "task_created", "delivery_status": f"Manual task created for {channel}"}
    save_outreach_message(
        candidate["id"],
        role["id"],
        channel,
        message_body,
        status=status["status"],
        delivery_status=status.get("delivery_status", status["status"]),
        sequence_id=sequence_id,
        step_number=step_number,
        metadata={"mode": mode},
    )
    if status["status"] in {"sent", "draft", "task_created"}:
        mark_contacted(candidate["id"])
    log_audit("outreach_sequence", sequence_id, "outreach_sent", {"channel": channel, "status": status["status"]})
    return status


def save_reply(message_id: int, reply_text: str) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE outreach_message SET reply_text = ?, reply_received_at = ?, updated_at = ? WHERE id = ?",
            (reply_text, utc_now(), utc_now(), message_id),
        )
    log_audit("outreach_message", message_id, "reply_received", {"reply_text": reply_text[:200]})

