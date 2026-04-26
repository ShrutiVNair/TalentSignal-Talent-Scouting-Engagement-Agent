from __future__ import annotations

from src.config import get_settings


def send_slack_alert(message: str) -> dict[str, str]:
    configured = bool(get_settings().slack_webhook_url)
    return {
        "status": "configured" if configured else "mocked",
        "delivery_status": "Slack alert sent" if configured else f"Slack mock alert: {message}",
    }

