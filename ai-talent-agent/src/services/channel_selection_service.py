from __future__ import annotations

import os
from typing import Any

from src.services.contact_validation_service import contact_readiness


def select_outreach_channel(
    candidate: dict[str, Any],
    role: dict[str, Any],
    validation_result: dict[str, Any] | None,
    compliance_result: dict[str, Any],
    duplicate_result: dict[str, Any],
    integration_status: dict[str, Any],
    outreach_mode: str,
    scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validation_result or contact_readiness(candidate, compliance_result)
    scorecard = scorecard or {}
    if not compliance_result.get("outreach_allowed"):
        return {
            "recommended_channel": "blocked",
            "allowed_channels": [],
            "blocked_channels": [{"channel": "all", "reason": "; ".join(compliance_result.get("reasons", ["Compliance review required"]))}],
            "manual_tasks": [],
            "reasoning": "Outreach is blocked until compliance issues are cleared.",
            "required_approval": True,
        }

    allowed: list[str] = []
    blocked: list[dict[str, str]] = []
    manual_tasks: list[str] = []

    if validation.get("email_valid"):
        allowed.append("email")
    else:
        blocked.append({"channel": "email", "reason": "Valid email not available."})

    sms_test_ready = bool(candidate.get("phone")) and bool(os.getenv("TEST_PHONE_NUMBER", "").strip()) and integration_status.get("twilio_ready")
    if sms_test_ready:
        allowed.append("sms_test")
    elif candidate.get("phone"):
        blocked.append({"channel": "sms_test", "reason": "Twilio test mode is not fully configured."})

    if validation.get("linkedin_valid"):
        allowed.append("linkedin_manual")
        manual_tasks.append("linkedin_manual")
    else:
        blocked.append({"channel": "linkedin_manual", "reason": "LinkedIn URL missing or invalid."})

    if validation.get("phone_valid"):
        allowed.append("call_manual")
        manual_tasks.append("call_manual")
    else:
        blocked.append({"channel": "call_manual", "reason": "Phone number missing or invalid."})

    if duplicate_result.get("duplicate_risk") == "high":
        blocked.append({"channel": "email", "reason": "High duplicate risk requires recruiter review first."})

    if scorecard.get("compensation_risk") == "high" and "email" in allowed:
        recommended = "email"
        reasoning = "Start with a compensation clarification email before moving to scheduling."
    elif scorecard.get("interest_score", 0) >= 75 and "email" in allowed:
        recommended = "email"
        reasoning = "Email is the cleanest first channel for a high-interest, compliant candidate."
    elif "sms_test" in allowed:
        recommended = "sms_test"
        reasoning = "SMS test mode is available, but only to the configured test number."
    elif "linkedin_manual" in allowed:
        recommended = "linkedin_manual"
        reasoning = "LinkedIn is available and remains a recruiter-run manual task."
    elif "call_manual" in allowed:
        recommended = "call_manual"
        reasoning = "A manual recruiter call task is safer than automated outreach here."
    else:
        recommended = "enrichment_needed"
        reasoning = "The candidate needs contact enrichment or compliance review before outreach can proceed."

    if outreach_mode.lower().startswith("test") and recommended == "email" and validation.get("contact_consent_status") == "unknown":
        reasoning = f"{reasoning} Production outreach remains blocked because consent is not explicit."

    return {
        "recommended_channel": recommended,
        "allowed_channels": allowed,
        "blocked_channels": blocked,
        "manual_tasks": manual_tasks,
        "reasoning": reasoning,
        "required_approval": True,
    }
