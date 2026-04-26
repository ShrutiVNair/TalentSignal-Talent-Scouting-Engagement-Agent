from __future__ import annotations

import json
from pathlib import Path

from src.database.db import db_cursor, json_dumps, utc_now
from src.database.models import ensure_database
from src.resume_parser import extract_contact_info
from src.utils import DATA_DIR


DEFAULT_INTEGRATIONS = [
    ("ats_mock", 1, {"provider": "mock"}),
    ("hris_mock", 1, {"provider": "mock"}),
    ("calendar_mock", 1, {"provider": "mock"}),
    ("metabase", 0, {}),
    ("twilio_sms", 0, {}),
    ("email", 1, {"mode": "draft"}),
    ("slack", 0, {}),
    ("teams", 0, {}),
]


def seed_all() -> None:
    ensure_database()
    _seed_candidates(DATA_DIR / "candidates.json")
    _seed_integrations()


def _seed_candidates(path: Path) -> None:
    candidates = json.loads(path.read_text(encoding="utf-8"))
    now = utc_now()
    with db_cursor() as cursor:
        for raw_candidate in candidates:
            contact = extract_contact_info(raw_candidate.get("resume_text", ""))
            cursor.execute(
                """
                INSERT INTO candidate (
                    id, full_name, email, phone, linkedin_url, github_url, location, current_company,
                    current_title, years_experience, skills, resume_text, summary, source,
                    compensation_expectation, availability, work_mode_preference, domain_experience,
                    engagement_persona, portfolio_url, education, certifications, work_history,
                    contact_source, contact_consent_status, last_verified_at, contact_readiness_status,
                    contact_readiness_reason, preferred_channel, email_confidence, phone_confidence,
                    linkedin_confidence, profile_parse_confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    full_name=excluded.full_name,
                    email=COALESCE(candidate.email, excluded.email),
                    phone=COALESCE(candidate.phone, excluded.phone),
                    linkedin_url=excluded.linkedin_url,
                    github_url=excluded.github_url,
                    portfolio_url=excluded.portfolio_url,
                    location=excluded.location,
                    current_title=excluded.current_title,
                    years_experience=excluded.years_experience,
                    skills=excluded.skills,
                    resume_text=excluded.resume_text,
                    summary=excluded.summary,
                    source=excluded.source,
                    compensation_expectation=excluded.compensation_expectation,
                    availability=excluded.availability,
                    work_mode_preference=excluded.work_mode_preference,
                    domain_experience=excluded.domain_experience,
                    engagement_persona=excluded.engagement_persona,
                    education=excluded.education,
                    certifications=excluded.certifications,
                    work_history=excluded.work_history,
                    contact_source=excluded.contact_source,
                    contact_consent_status=excluded.contact_consent_status,
                    last_verified_at=excluded.last_verified_at,
                    contact_readiness_status=excluded.contact_readiness_status,
                    contact_readiness_reason=excluded.contact_readiness_reason,
                    preferred_channel=excluded.preferred_channel,
                    email_confidence=excluded.email_confidence,
                    phone_confidence=excluded.phone_confidence,
                    linkedin_confidence=excluded.linkedin_confidence,
                    profile_parse_confidence=excluded.profile_parse_confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    raw_candidate["id"],
                    raw_candidate.get("name", ""),
                    contact.get("email"),
                    contact.get("phone"),
                    raw_candidate.get("linkedin_url"),
                    raw_candidate.get("github_url"),
                    raw_candidate.get("location"),
                    raw_candidate.get("current_company"),
                    raw_candidate.get("current_title"),
                    raw_candidate.get("years_experience", 0),
                    json_dumps(raw_candidate.get("skills", [])),
                    raw_candidate.get("resume_text"),
                    raw_candidate.get("summary"),
                    "seed_dataset",
                    raw_candidate.get("compensation_expectation"),
                    raw_candidate.get("availability"),
                    raw_candidate.get("work_mode_preference"),
                    raw_candidate.get("domain_experience"),
                    raw_candidate.get("engagement_persona"),
                    raw_candidate.get("portfolio_url"),
                    raw_candidate.get("education"),
                    json_dumps(raw_candidate.get("certifications", [])),
                    json_dumps(raw_candidate.get("work_history", [])),
                    "demo",
                    "demo_assumed",
                    now,
                    "Ready for email draft" if contact.get("email") else "Needs recruiter review",
                    "Seeded demo candidate data" if contact.get("email") else "Missing recruiter-verifiable email",
                    "email" if contact.get("email") else "linkedin_manual" if raw_candidate.get("linkedin_url") else "enrichment_needed",
                    0.95 if contact.get("email") else 0.0,
                    0.75 if contact.get("phone") else 0.0,
                    0.9 if raw_candidate.get("linkedin_url") else 0.0,
                    0.75,
                    now,
                    now,
                ),
            )
            cursor.execute(
                """
                INSERT INTO compliance_record (candidate_id, opt_out, do_not_contact, gdpr_delete_requested, compliance_notes)
                VALUES (?, 0, 0, 0, ?)
                ON CONFLICT(candidate_id) DO NOTHING
                """,
                (raw_candidate["id"], "Seeded default compliance state"),
            )


def _seed_integrations() -> None:
    now = utc_now()
    with db_cursor() as cursor:
        for name, enabled, config in DEFAULT_INTEGRATIONS:
            cursor.execute(
                """
                INSERT INTO integration_config (integration_name, enabled, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(integration_name) DO UPDATE SET
                    enabled=excluded.enabled,
                    config_json=excluded.config_json,
                    updated_at=excluded.updated_at
                """,
                (name, enabled, json_dumps(config), now, now),
            )
