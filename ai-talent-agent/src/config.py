from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "talentsignal.db"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}"))
    ats_provider: str = field(default_factory=lambda: os.getenv("ATS_PROVIDER", "mock").strip().lower() or "mock")
    email_provider: str = field(default_factory=lambda: os.getenv("EMAIL_PROVIDER", "mock").strip().lower() or "mock")
    greenhouse_api_key: str = field(default_factory=lambda: os.getenv("GREENHOUSE_API_KEY", "").strip())
    lever_api_key: str = field(default_factory=lambda: os.getenv("LEVER_API_KEY", "").strip())
    metabase_site_url: str = field(default_factory=lambda: os.getenv("METABASE_SITE_URL", "").strip())
    metabase_secret_key: str = field(default_factory=lambda: os.getenv("METABASE_SECRET_KEY", "").strip())
    google_calendar_enabled: bool = field(default_factory=lambda: os.getenv("GOOGLE_CALENDAR_ENABLED", "false").strip().lower() == "true")
    microsoft_calendar_enabled: bool = field(default_factory=lambda: os.getenv("MICROSOFT_CALENDAR_ENABLED", "false").strip().lower() == "true")
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", "").strip())
    teams_webhook_url: str = field(default_factory=lambda: os.getenv("TEAMS_WEBHOOK_URL", "").strip())
    test_email_recipient: str = field(default_factory=lambda: os.getenv("TEST_EMAIL_RECIPIENT", "").strip())
    production_outreach_enabled: bool = field(default_factory=lambda: os.getenv("PRODUCTION_OUTREACH_ENABLED", "false").strip().lower() == "true")
    demo_mode_default: str = field(default_factory=lambda: os.getenv("DEMO_MODE_DEFAULT", "demo").strip().lower() or "demo")


def get_settings() -> Settings:
    return Settings()
