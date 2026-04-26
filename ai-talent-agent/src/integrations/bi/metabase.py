from __future__ import annotations

from src.config import get_settings
from src.integrations.base import IntegrationStatus


def metabase_status() -> IntegrationStatus:
    settings = get_settings()
    configured = bool(settings.metabase_site_url)
    return IntegrationStatus(
        name="Metabase",
        enabled=configured,
        configured=configured,
        mode="external" if configured else "native",
        detail=settings.metabase_site_url or "Using native Streamlit analytics because Metabase is not configured.",
    )

