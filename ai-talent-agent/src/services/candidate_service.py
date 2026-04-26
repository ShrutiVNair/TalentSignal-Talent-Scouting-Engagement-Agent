from __future__ import annotations

import json
from math import ceil
from typing import Any

from src.database.db import db_cursor, fetch_all, fetch_one, json_dumps, utc_now
from src.resume_parser import extract_contact_info, is_valid_email
from src.services.audit_service import log_audit
from src.utils import build_searchable_text, hash_payload, tokenize_skills


def _decode_candidate(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return row
    row = dict(row)
    row["name"] = row.pop("full_name")
    row["skills"] = json.loads(row.get("skills") or "[]")
    row["normalized_skills"] = json.loads(row.get("normalized_skills") or "[]")
    row["certifications"] = json.loads(row.get("certifications") or "[]")
    row["work_history"] = json.loads(row.get("work_history") or "[]")
    row["email_valid"] = is_valid_email(row.get("email"))
    row["contact_incomplete"] = not all([row.get("email"), row.get("phone"), row.get("linkedin_url")])
    return row


def list_candidates() -> list[dict[str, Any]]:
    rows = fetch_all("SELECT * FROM candidate ORDER BY updated_at DESC, full_name ASC")
    return [_decode_candidate(row) for row in rows]


def get_candidate(candidate_id: str) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM candidate WHERE id = ?", (candidate_id,))
    return _decode_candidate(row) if row else None


def upsert_candidate(candidate: dict[str, Any], source: str = "app") -> str:
    now = utc_now()
    candidate_id = str(candidate["id"])
    contact = extract_contact_info(candidate.get("resume_text", ""))
    normalized_skills = tokenize_skills(candidate.get("skills", []))
    searchable_text = build_searchable_text(
        candidate.get("name"),
        candidate.get("current_title"),
        candidate.get("current_company"),
        candidate.get("location"),
        candidate.get("summary"),
        candidate.get("skills", []),
    )
    resume_hash = hash_payload(candidate.get("resume_text"), candidate.get("email"), candidate.get("phone"))
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO candidate (
                id, full_name, email, phone, linkedin_url, github_url, location, current_company,
                current_title, years_experience, skills, resume_text, summary, source,
                compensation_expectation, availability, work_mode_preference, domain_experience,
                engagement_persona, portfolio_url, education, certifications, work_history,
                contact_source, contact_consent_status, last_verified_at, contact_readiness_status,
                contact_readiness_reason, preferred_channel, normalized_skills, searchable_text,
                resume_hash, parse_status, last_scored_at, email_confidence, phone_confidence,
                linkedin_confidence, profile_parse_confidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                full_name=excluded.full_name,
                email=excluded.email,
                phone=excluded.phone,
                linkedin_url=excluded.linkedin_url,
                github_url=excluded.github_url,
                portfolio_url=excluded.portfolio_url,
                location=excluded.location,
                current_company=excluded.current_company,
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
                normalized_skills=excluded.normalized_skills,
                searchable_text=excluded.searchable_text,
                resume_hash=excluded.resume_hash,
                parse_status=excluded.parse_status,
                last_scored_at=excluded.last_scored_at,
                email_confidence=excluded.email_confidence,
                phone_confidence=excluded.phone_confidence,
                linkedin_confidence=excluded.linkedin_confidence,
                profile_parse_confidence=excluded.profile_parse_confidence,
                updated_at=excluded.updated_at
            """,
            (
                candidate_id,
                candidate.get("name", ""),
                candidate.get("email") or contact.get("email"),
                candidate.get("phone") or contact.get("phone"),
                candidate.get("linkedin_url") or contact.get("linkedin"),
                candidate.get("github_url"),
                candidate.get("location"),
                candidate.get("current_company"),
                candidate.get("current_title"),
                candidate.get("years_experience", 0),
                json_dumps(candidate.get("skills", [])),
                candidate.get("resume_text"),
                candidate.get("summary"),
                source,
                candidate.get("compensation_expectation"),
                candidate.get("availability"),
                candidate.get("work_mode_preference"),
                candidate.get("domain_experience"),
                candidate.get("engagement_persona"),
                candidate.get("portfolio_url"),
                candidate.get("education"),
                json_dumps(candidate.get("certifications", [])),
                json_dumps(candidate.get("work_history", [])),
                candidate.get("contact_source") or source,
                candidate.get("contact_consent_status", "unknown"),
                candidate.get("last_verified_at"),
                candidate.get("contact_readiness_status"),
                candidate.get("contact_readiness_reason"),
                candidate.get("preferred_channel"),
                json_dumps(normalized_skills),
                searchable_text,
                resume_hash,
                candidate.get("parse_status", "parsed"),
                candidate.get("last_scored_at"),
                candidate.get("email_confidence", 0),
                candidate.get("phone_confidence", 0),
                candidate.get("linkedin_confidence", 0),
                candidate.get("profile_parse_confidence", 0),
                now,
                now,
            ),
        )
    log_audit("candidate", candidate_id, "candidate_upserted", {"source": source})
    try:
        from src.services.batch_scoring_service import get_top_matches

        get_top_matches.cache_clear()
    except Exception:
        pass
    return candidate_id


def search_candidates(query: str) -> list[dict[str, Any]]:
    like = f"%{query.strip().lower()}%"
    rows = fetch_all(
        """
        SELECT * FROM candidate
        WHERE lower(full_name) LIKE ?
           OR lower(current_title) LIKE ?
           OR lower(location) LIKE ?
           OR lower(summary) LIKE ?
           OR lower(skills) LIKE ?
        ORDER BY updated_at DESC
        """,
        (like, like, like, like, like),
    )
    return [_decode_candidate(row) for row in rows]


def list_candidates_page(
    page: int = 1,
    page_size: int = 25,
    query: str = "",
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    clauses: list[str] = []
    params: list[Any] = []
    if query.strip():
        clauses.append("searchable_text LIKE ?")
        params.append(f"%{query.strip().lower()}%")
    if filters.get("contact_readiness_status"):
        clauses.append("contact_readiness_status = ?")
        params.append(filters["contact_readiness_status"])
    if filters.get("location"):
        clauses.append("location LIKE ?")
        params.append(f"%{filters['location']}%")
    if filters.get("source"):
        clauses.append("source = ?")
        params.append(filters["source"])
    if filters.get("preferred_channel"):
        clauses.append("preferred_channel = ?")
        params.append(filters["preferred_channel"])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total_row = fetch_one(f"SELECT COUNT(*) as total FROM candidate{where}", tuple(params)) or {"total": 0}
    total = int(total_row["total"])
    offset = max(page - 1, 0) * page_size
    rows = fetch_all(
        f"SELECT * FROM candidate{where} ORDER BY updated_at DESC, full_name ASC LIMIT ? OFFSET ?",
        tuple([*params, page_size, offset]),
    )
    items = [_decode_candidate(row) for row in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)) if page_size else 1,
    }
