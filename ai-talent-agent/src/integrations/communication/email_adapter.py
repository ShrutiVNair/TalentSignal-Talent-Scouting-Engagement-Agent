from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any

from src.config import get_settings
from src.resume_parser import is_valid_email
from src.services.audit_service import log_audit


@dataclass(frozen=True)
class EmailStatus:
    provider: str
    configured: bool
    mode: str
    detail: str
    smtp_host: str
    from_address: str
    test_recipient_configured: bool
    production_enabled: bool


def is_configured() -> bool:
    settings = get_settings()
    if settings.email_provider != "smtp":
        return False
    required = [
        os.getenv("SMTP_HOST", "").strip(),
        os.getenv("SMTP_PORT", "").strip(),
        os.getenv("SMTP_USERNAME", "").strip(),
        os.getenv("SMTP_PASSWORD", "").strip(),
        os.getenv("SMTP_FROM", "").strip(),
    ]
    return all(required)


def get_status() -> EmailStatus:
    settings = get_settings()
    configured = is_configured()
    if settings.email_provider == "mock":
        detail = "Mock mode is active. No real email will be sent."
        mode = "mock"
    elif configured:
        detail = "SMTP is configured. Real test email is available from the Outreach page."
        mode = "connected"
    else:
        detail = "SMTP is incomplete. Email actions fall back to mock mode safely."
        mode = "missing_credentials"
    return EmailStatus(
        provider=settings.email_provider,
        configured=configured,
        mode=mode,
        detail=detail,
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        from_address=os.getenv("SMTP_FROM", "").strip(),
        test_recipient_configured=bool(settings.test_email_recipient),
        production_enabled=settings.production_outreach_enabled,
    )


def create_draft(candidate: dict[str, Any], role: dict[str, Any] | str, subject: str, body: str) -> dict[str, Any]:
    role_name = role["title"] if isinstance(role, dict) else str(role)
    result = {
        "status": "draft",
        "recipient": candidate.get("email"),
        "actual_recipient": candidate.get("email"),
        "provider": get_status().provider,
        "error": None,
        "message_id": None,
        "subject": subject,
        "body": body,
    }
    log_audit("candidate", candidate["id"], "email_draft_generated", {"role": role_name, "subject": subject})
    return result


def send_test_email(subject: str, body: str, candidate_email: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    test_recipient = settings.test_email_recipient
    if not test_recipient:
        return _result("mock_sent", candidate_email, "TEST_EMAIL_RECIPIENT is not configured; saved as mock send.", "No external recipient (mock mode)", provider_label())
    test_subject = subject if subject.startswith("[TEST]") else f"[TEST] {subject}"
    candidate_line = (
        "\n\nThis is a TalentSignal demo email. "
        f"Intended candidate email: {candidate_email or 'Unavailable'}."
    )
    return _send_email(test_subject, f"{body}{candidate_line}", test_recipient, "test_sent", candidate_email)


def send_candidate_email(candidate: dict[str, Any], role: dict[str, Any] | str, subject: str, body: str) -> dict[str, Any]:
    settings = get_settings()
    candidate_email = (candidate.get("email") or "").strip()
    if not settings.production_outreach_enabled:
        return _result("blocked", candidate_email, "Production outreach is disabled.", candidate_email, provider_label())
    if not is_valid_email(candidate_email):
        return _result("blocked", candidate_email, "Candidate email is invalid or missing.", candidate_email, provider_label())
    if not candidate.get("email_compliance_passed"):
        return _result("blocked", candidate_email, "Compliance check did not pass.", candidate_email, provider_label())
    if candidate.get("opted_out") or candidate.get("do_not_contact"):
        return _result("blocked", candidate_email, "Candidate is opted out or marked do-not-contact.", candidate_email, provider_label())
    if candidate.get("contact_consent_status") not in {"explicit", "demo_assumed"}:
        return _result("blocked", candidate_email, "Consent status does not allow production outreach.", candidate_email, provider_label())
    if not candidate.get("recruiter_approved"):
        return _result("blocked", candidate_email, "Recruiter approval is required.", candidate_email, provider_label())
    return _send_email(subject, body, candidate_email, "sent", candidate_email)


def send_email_safe(candidate: dict[str, Any], role: dict[str, Any] | str, subject: str, body: str, mode: str) -> dict[str, Any]:
    provider = provider_label()
    candidate_email = (candidate.get("email") or "").strip() or None
    if mode == "test":
        result = send_test_email(subject, body, candidate_email=candidate_email)
    elif mode == "mock" or get_settings().email_provider == "mock":
        result = _result("mock_sent", candidate_email, None, "No external recipient (mock mode)", provider)
    elif mode == "production":
        result = send_candidate_email(candidate, role, subject, body)
    else:
        result = _result("failed", candidate_email, "Unsupported email mode.", candidate_email, provider)

    action = (
        "test_email_sent" if result["status"] == "test_sent"
        else "production_email_sent" if result["status"] == "sent"
        else "email_blocked" if result["status"] == "blocked"
        else "email_failed" if result["status"] == "failed"
        else "email_approved"
    )
    log_audit(
        "candidate",
        candidate["id"],
        action,
        {
            "mode": mode,
            "provider": result["provider"],
            "recipient": result["recipient"],
            "actual_recipient": result["actual_recipient"],
            "error": result["error"],
        },
    )
    return result


def send_email_draft(candidate: dict[str, Any], role: dict[str, Any], message: str, draft_only: bool = True) -> dict[str, Any]:
    subject = f"{role['title']} opportunity"
    if draft_only:
        draft = create_draft(candidate, role, subject, message)
        return {"status": draft["status"], "delivery_status": "Email draft saved", "error": draft["error"]}
    result = send_test_email(subject, message, candidate.get("email"))
    return {"status": result["status"], "delivery_status": result["status"], "error": result["error"]}


def provider_label() -> str:
    return "smtp" if get_settings().email_provider == "smtp" else "mock"


def _send_email(subject: str, body: str, recipient: str, success_status: str, candidate_email: str | None) -> dict[str, Any]:
    if not is_configured():
        return _result("mock_sent", candidate_email or recipient, None, recipient, provider_label())

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Message-ID"] = make_msgid()
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError:
        return _result("failed", recipient, "SMTP authentication failed.", recipient, provider_label())
    except smtplib.SMTPException as exc:
        return _result("failed", recipient, f"SMTP failure: {exc}", recipient, provider_label())
    except OSError as exc:
        return _result("failed", recipient, f"SMTP connection failed: {exc}", recipient, provider_label())

    actual_recipient = recipient if success_status == "sent" else recipient
    return _result(success_status, candidate_email or recipient, None, actual_recipient, provider_label(), message["Message-ID"])


def _result(
    status: str,
    recipient: str | None,
    error: str | None,
    actual_recipient: str | None,
    provider: str,
    message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "recipient": recipient,
        "actual_recipient": actual_recipient,
        "provider": provider,
        "error": error,
        "message_id": message_id,
    }
