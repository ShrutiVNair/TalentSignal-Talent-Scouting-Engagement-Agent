from __future__ import annotations

from typing import Any


def send_whatsapp_mock(candidate: dict[str, Any], message: str) -> dict[str, str]:
    return {"status": "mocked", "delivery_status": f"WhatsApp mock prepared for {candidate['name']}: {message[:60]}"}

