from __future__ import annotations

from src.database.db import db_cursor


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS candidate (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        linkedin_url TEXT,
        github_url TEXT,
        portfolio_url TEXT,
        location TEXT,
        current_company TEXT,
        current_title TEXT,
        years_experience REAL DEFAULT 0,
        skills TEXT,
        resume_text TEXT,
        summary TEXT,
        source TEXT,
        compensation_expectation TEXT,
        availability TEXT,
        work_mode_preference TEXT,
        domain_experience TEXT,
        engagement_persona TEXT,
        education TEXT,
        certifications TEXT,
        work_history TEXT,
        contact_source TEXT,
        contact_consent_status TEXT,
        last_verified_at TEXT,
        contact_readiness_status TEXT,
        contact_readiness_reason TEXT,
        preferred_channel TEXT,
        normalized_skills TEXT,
        searchable_text TEXT,
        resume_hash TEXT,
        parse_status TEXT,
        last_scored_at TEXT,
        email_confidence REAL DEFAULT 0,
        phone_confidence REAL DEFAULT 0,
        linkedin_confidence REAL DEFAULT 0,
        profile_parse_confidence REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS role (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        department TEXT,
        hiring_manager TEXT,
        location TEXT,
        work_mode TEXT,
        salary_min INTEGER,
        salary_max INTEGER,
        required_skills TEXT,
        nice_to_have_skills TEXT,
        experience_min INTEGER,
        experience_max INTEGER,
        jd_text TEXT,
        status TEXT DEFAULT 'Open',
        scoring_weights_json TEXT,
        calibration_json TEXT,
        normalized_required_skills TEXT,
        normalized_nice_to_have_skills TEXT,
        role_hash TEXT,
        interview_process TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_role_match (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        match_score REAL DEFAULT 0,
        interest_score REAL DEFAULT 0,
        risk_score REAL DEFAULT 0,
        final_score REAL DEFAULT 0,
        recommendation TEXT,
        next_best_action TEXT,
        stage TEXT DEFAULT 'Sourced',
        scorecard_json TEXT,
        duplicate_status_json TEXT,
        compliance_status_json TEXT,
        hiring_manager_status TEXT DEFAULT 'pending',
        hiring_manager_notes TEXT,
        reviewed_at TEXT,
        last_contacted_at TEXT,
        score_version TEXT,
        role_hash TEXT,
        candidate_hash TEXT,
        scored_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(candidate_id, role_id),
        FOREIGN KEY(candidate_id) REFERENCES candidate(id),
        FOREIGN KEY(role_id) REFERENCES role(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outreach_message (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        channel TEXT NOT NULL,
        message_body TEXT NOT NULL,
        status TEXT,
        sent_at TEXT,
        delivery_status TEXT,
        reply_text TEXT,
        reply_received_at TEXT,
        sequence_id TEXT,
        step_number INTEGER DEFAULT 0,
        metadata_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(candidate_id) REFERENCES candidate(id),
        FOREIGN KEY(role_id) REFERENCES role(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        feedback_type TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(candidate_id) REFERENCES candidate(id),
        FOREIGN KEY(role_id) REFERENCES role(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        details_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS compliance_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL UNIQUE,
        opt_out INTEGER DEFAULT 0,
        do_not_contact INTEGER DEFAULT 0,
        gdpr_delete_requested INTEGER DEFAULT 0,
        last_contacted_at TEXT,
        cooldown_until TEXT,
        compliance_notes TEXT,
        FOREIGN KEY(candidate_id) REFERENCES candidate(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS integration_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        integration_name TEXT NOT NULL UNIQUE,
        enabled INTEGER DEFAULT 0,
        config_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outreach_sequence (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        steps_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(candidate_id) REFERENCES candidate(id),
        FOREIGN KEY(role_id) REFERENCES role(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduled_interview (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        slot_time TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        status TEXT NOT NULL,
        event_payload_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(candidate_id) REFERENCES candidate(id),
        FOREIGN KEY(role_id) REFERENCES role(id)
    )
    """,
]


def ensure_database() -> None:
    with db_cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        _ensure_candidate_columns(cursor)
        _ensure_role_columns(cursor)
        _ensure_match_columns(cursor)
        _ensure_indexes(cursor)


def _ensure_candidate_columns(cursor: object) -> None:
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(candidate)").fetchall()}
    candidate_columns = {
        "portfolio_url": "TEXT",
        "education": "TEXT",
        "certifications": "TEXT",
        "work_history": "TEXT",
        "contact_source": "TEXT",
        "contact_consent_status": "TEXT",
        "last_verified_at": "TEXT",
        "contact_readiness_status": "TEXT",
        "contact_readiness_reason": "TEXT",
        "preferred_channel": "TEXT",
        "normalized_skills": "TEXT",
        "searchable_text": "TEXT",
        "resume_hash": "TEXT",
        "parse_status": "TEXT",
        "last_scored_at": "TEXT",
        "email_confidence": "REAL DEFAULT 0",
        "phone_confidence": "REAL DEFAULT 0",
        "linkedin_confidence": "REAL DEFAULT 0",
        "profile_parse_confidence": "REAL DEFAULT 0",
    }
    for name, definition in candidate_columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE candidate ADD COLUMN {name} {definition}")


def _ensure_role_columns(cursor: object) -> None:
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(role)").fetchall()}
    columns = {
        "normalized_required_skills": "TEXT",
        "normalized_nice_to_have_skills": "TEXT",
        "role_hash": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE role ADD COLUMN {name} {definition}")


def _ensure_match_columns(cursor: object) -> None:
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(candidate_role_match)").fetchall()}
    columns = {
        "score_version": "TEXT",
        "role_hash": "TEXT",
        "candidate_hash": "TEXT",
        "scored_at": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE candidate_role_match ADD COLUMN {name} {definition}")


def _ensure_indexes(cursor: object) -> None:
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_candidate_email ON candidate(email)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_linkedin ON candidate(linkedin_url)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_phone ON candidate(phone)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_location ON candidate(location)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_company ON candidate(current_company)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_searchable ON candidate(searchable_text)",
        "CREATE INDEX IF NOT EXISTS idx_match_role_id ON candidate_role_match(role_id)",
        "CREATE INDEX IF NOT EXISTS idx_match_final_score ON candidate_role_match(final_score)",
        "CREATE INDEX IF NOT EXISTS idx_match_stage ON candidate_role_match(stage)",
        "CREATE INDEX IF NOT EXISTS idx_compliance_candidate_id ON compliance_record(candidate_id)",
        "CREATE INDEX IF NOT EXISTS idx_outreach_candidate_id ON outreach_message(candidate_id)",
        "CREATE INDEX IF NOT EXISTS idx_outreach_role_id ON outreach_message(role_id)",
    ]
    for statement in indexes:
        cursor.execute(statement)
