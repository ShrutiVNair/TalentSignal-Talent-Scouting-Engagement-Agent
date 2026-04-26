from __future__ import annotations

import os
from typing import Any

try:
    import phonenumbers
except ImportError:  # pragma: no cover
    phonenumbers = None

try:
    from twilio.rest import Client
except ImportError:  # pragma: no cover
    Client = None

from src.config import get_settings
from src.integrations.ats.greenhouse import GreenhouseAdapter
from src.integrations.ats.lever import LeverAdapter
from src.integrations.ats.mock_ats import MockATSAdapter
from src.integrations.base import IntegrationStatus
from src.integrations.communication.email_adapter import get_status as get_email_status


def validate_phone_number(phone_number: str) -> tuple[bool, str | None]:
    if not phone_number or phonenumbers is None:
        return False, None
    try:
        parsed = phonenumbers.parse(phone_number, None)
    except phonenumbers.NumberParseException:
        return False, None
    if not phonenumbers.is_valid_number(parsed):
        return False, None
    normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return True, normalized


def send_sms(message: str, phone_number: str) -> dict[str, Any]:
    sid = os.getenv("TWILIO_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_PHONE", "").strip()
    test_phone = os.getenv("TEST_PHONE_NUMBER", "").strip()

    if phonenumbers is None:
        return {"status": "failed", "sid": None, "error": "phonenumbers is not installed."}
    if not sid or not auth_token or not twilio_phone or not test_phone:
        return {"status": "failed", "sid": None, "error": "Twilio credentials are not configured."}
    is_valid, normalized_phone = validate_phone_number(test_phone)
    if not is_valid or not normalized_phone:
        return {"status": "failed", "sid": None, "error": "Invalid TEST_PHONE_NUMBER."}
    if Client is None:
        return {"status": "failed", "sid": None, "error": "Twilio SDK is not installed."}
    try:
        client = Client(sid, auth_token)
        safe_message = f"{message}\n\nTalentSignal AI test SMS. Candidate phone would have been: {phone_number or 'Unavailable'}"
        response = client.messages.create(body=safe_message, from_=twilio_phone, to=normalized_phone)
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "sid": None, "error": f"Twilio send failed: {exc}"}
    return {"status": "sent", "sid": getattr(response, "sid", None), "error": None}


def get_ats_adapter() -> Any:
    provider = get_settings().ats_provider
    if provider == "greenhouse":
        return GreenhouseAdapter()
    if provider == "lever":
        return LeverAdapter()
    return MockATSAdapter()


def integration_statuses() -> list[IntegrationStatus]:
    settings = get_settings()
    email_status = get_email_status()
    return [
        IntegrationStatus("ATS", True, True, settings.ats_provider, f"Provider: {settings.ats_provider}"),
        IntegrationStatus("Twilio SMS", bool(os.getenv("TWILIO_SID", "").strip()), bool(os.getenv("TWILIO_SID", "").strip()), "real" if os.getenv("TWILIO_SID", "").strip() else "optional", "Real SMS test mode is enabled only when Twilio env vars are set."),
        IntegrationStatus(
            "Email",
            True,
            email_status.configured,
            email_status.provider,
            email_status.detail,
        ),
        IntegrationStatus("Slack", bool(settings.slack_webhook_url), bool(settings.slack_webhook_url), "optional", "Internal alerts are mocked unless webhook is configured."),
        IntegrationStatus("Teams", bool(settings.teams_webhook_url), bool(settings.teams_webhook_url), "optional", "Internal alerts are mocked unless webhook is configured."),
        IntegrationStatus("Google Calendar", settings.google_calendar_enabled, settings.google_calendar_enabled, "optional", "Mock calendar works even when disabled."),
        IntegrationStatus("Microsoft Calendar", settings.microsoft_calendar_enabled, settings.microsoft_calendar_enabled, "optional", "Mock calendar works even when disabled."),
    ]
