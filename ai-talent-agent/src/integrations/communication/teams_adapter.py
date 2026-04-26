from __future__ import annotations

from src.config import get_settings


def send_teams_alert(message: str) -> dict[str, str]:
    configured = bool(get_settings().teams_webhook_url)
    return {
        "status": "configured" if configured else "mocked",
        "delivery_status": "Teams alert sent" if configured else f"Teams mock alert: {message}",
    }

