from __future__ import annotations

from typing import Any

from src.agents.ranking_agent import get_match, update_match_stage
from src.integrations.communication.email_adapter import create_draft, send_email_safe
from src.outreach import generate_email_subject_body
from src.llm_client import LLMClient
from src.services.audit_service import log_audit
from src.services.candidate_service import get_candidate
from src.services.compliance_service import get_compliance_record
from src.services.outreach_service import list_messages, save_outreach_message
from src.services.role_service import get_role


def generate_email_draft(candidate_id: str, role_id: int) -> dict[str, Any]:
    candidate = get_candidate(candidate_id)
    role = get_role(role_id)
    if not candidate or not role:
        return {"status": "failed", "error": "Candidate or role not found."}
    assets = generate_email_subject_body(candidate, role, LLMClient())
    draft = create_draft(candidate, role, assets["subject"], assets["body"])
    save_outreach_message(candidate_id, role_id, "email", assets["body"], status="draft", delivery_status="Draft saved", metadata={"subject": assets["subject"], "provider": draft["provider"]})
    return {**draft, "subject": assets["subject"], "body": assets["body"]}


def approve_email(candidate_id: str, role_id: int, approved_by: str) -> dict[str, Any]:
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "email_approved", {"approved_by": approved_by})
    return {"status": "approved"}


def send_test_email(candidate_id: str, role_id: int, approved_by: str) -> dict[str, Any]:
    return _send(candidate_id, role_id, approved_by, mode="test")


def send_production_email(candidate_id: str, role_id: int, approved_by: str) -> dict[str, Any]:
    return _send(candidate_id, role_id, approved_by, mode="production")


def get_email_status(candidate_id: str, role_id: int) -> dict[str, Any]:
    messages = [row for row in list_messages(candidate_id, role_id) if row["channel"] == "email"]
    return messages[0] if messages else {"status": "none"}


def _send(candidate_id: str, role_id: int, approved_by: str, mode: str) -> dict[str, Any]:
    candidate = get_candidate(candidate_id)
    role = get_role(role_id)
    if not candidate or not role:
        return {"status": "failed", "error": "Candidate or role not found."}
    assets = generate_email_subject_body(candidate, role, LLMClient())
    compliance = get_compliance_record(candidate_id)
    match = get_match(candidate_id, role_id)
    result = send_email_safe(
        {
            **candidate,
            "email_valid": bool(candidate.get("email_valid")),
            "email_compliance_passed": bool(match and match.get("compliance_status", {}).get("outreach_allowed", True)),
            "do_not_contact": bool(compliance.get("do_not_contact")),
            "opted_out": bool(compliance.get("opt_out")),
            "recruiter_approved": True,
            "contact_consent_status": candidate.get("contact_consent_status", "unknown"),
        },
        role,
        assets["subject"],
        assets["body"],
        mode,
    )
    logged_body = assets["body"]
    if mode == "test":
        logged_body = (
            f"{assets['body']}\n\n"
            "This is a TalentSignal demo email. "
            f"Intended candidate email: {candidate.get('email') or 'Unavailable'}."
        )
    save_outreach_message(
        candidate_id,
        role_id,
        "email",
        logged_body,
        status=result["status"],
        delivery_status=result["error"] or result["status"],
        metadata={"subject": assets["subject"], "provider": result["provider"], "actual_recipient": result["actual_recipient"], "approved_by": approved_by, "message_id": result.get("message_id")},
    )
    if result["status"] in {"test_sent", "sent", "mock_sent"}:
        update_match_stage(candidate_id, role_id, "Contacted")
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "test_email_sent" if mode == "test" else "production_email_sent", {"approved_by": approved_by, "status": result["status"]})
    return result
