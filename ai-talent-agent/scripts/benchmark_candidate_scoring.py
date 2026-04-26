from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import db_cursor, utc_now
from src.database.models import ensure_database
from src.services.batch_scoring_service import get_top_matches, score_candidates_for_role
from src.services.role_service import create_role, list_roles
from src.utils import build_searchable_text, hash_payload, tokenize_skills

import json


def synth_candidate(index: int) -> tuple:
    now = utc_now()
    skills = ["Python", "FastAPI", "PostgreSQL", "AWS"]
    extra = "Kafka" if index % 3 == 0 else "Docker"
    full_skills = skills + [extra]
    searchable = build_searchable_text(
        f"Synthetic Candidate {index}",
        "Backend Engineer",
        f"Company {index % 50}",
        "Remote - US" if index % 2 == 0 else "Bangalore",
        "Synthetic benchmark candidate",
        full_skills,
    )
    resume_hash = hash_payload(index, searchable)
    return (
        f"SYN-{index:06d}",
        f"Synthetic Candidate {index}",
        f"synthetic{index}@example.com",
        f"+1555000{index:06d}"[-12:],
        f"https://www.linkedin.com/in/synthetic{index}",
        "",
        "",
        "Remote - US" if index % 2 == 0 else "Bangalore",
        f"Company {index % 50}",
        "Backend Engineer",
        4 + (index % 6),
        json.dumps(full_skills, sort_keys=True, ensure_ascii=True),
        "Synthetic backend resume text with Python FastAPI PostgreSQL AWS.",
        "Synthetic benchmark candidate",
        "benchmark",
        "$160000",
        "30 days",
        "remote",
        "saas",
        "passive_but_open",
        "",
        json.dumps([], sort_keys=True, ensure_ascii=True),
        json.dumps([], sort_keys=True, ensure_ascii=True),
        "benchmark",
        "demo_assumed",
        now,
        "Ready for email draft",
        "Synthetic benchmark candidate is email-ready.",
        "email",
        json.dumps(tokenize_skills(full_skills), sort_keys=True, ensure_ascii=True),
        searchable,
        resume_hash,
        "parsed",
        None,
        0.98,
        0.8,
        0.9,
        0.82,
        now,
        now,
    )


def reset_candidates() -> None:
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM outreach_message")
        cursor.execute("DELETE FROM candidate_role_match")
        cursor.execute("DELETE FROM compliance_record")
        cursor.execute("DELETE FROM feedback")
        cursor.execute("DELETE FROM audit_log")
        cursor.execute("DELETE FROM candidate")


def bulk_insert_candidates(size: int) -> None:
    rows = [synth_candidate(index) for index in range(1, size + 1)]
    with db_cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO candidate (
                id, full_name, email, phone, linkedin_url, github_url, portfolio_url, location, current_company,
                current_title, years_experience, skills, resume_text, summary, source, compensation_expectation,
                availability, work_mode_preference, domain_experience, engagement_persona, education, certifications,
                work_history, contact_source, contact_consent_status, last_verified_at, contact_readiness_status,
                contact_readiness_reason, preferred_channel, normalized_skills, searchable_text, resume_hash, parse_status,
                last_scored_at, email_confidence, phone_confidence, linkedin_confidence, profile_parse_confidence,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def ensure_role() -> int:
    roles = list_roles()
    if roles:
        return roles[0]["id"]
    return create_role(
        {
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "hiring_manager": "Benchmark Manager",
            "location": "Remote - US",
            "work_mode": "remote",
            "salary_min": 150000,
            "salary_max": 190000,
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "AWS"],
            "nice_to_have_skills": ["Kafka", "Docker"],
            "experience_min": 5,
            "experience_max": 10,
            "jd_text": "Synthetic benchmark role",
            "status": "Open",
            "scoring_weights": {},
            "interview_process": "screen",
        }
    )


def run_benchmark(size: int, role_id: int) -> None:
    print(f"\nBenchmarking {size:,} candidates")
    reset_candidates()

    started = time.perf_counter()
    bulk_insert_candidates(size)
    load_seconds = round(time.perf_counter() - started, 2)

    started = time.perf_counter()
    scoring_summary = score_candidates_for_role(role_id, limit=size, batch_size=500)
    scoring_seconds = round(time.perf_counter() - started, 2)

    started = time.perf_counter()
    top = get_top_matches(role_id, limit=25)
    top_query_seconds = round(time.perf_counter() - started, 4)

    print(f"Load time: {load_seconds}s")
    print(f"Scoring time: {scoring_seconds}s")
    print(f"Top matches query time: {top_query_seconds}s")
    print(f"Processed: {scoring_summary['processed_count']} | Scored: {scoring_summary['scored_count']}")
    print(f"Persisted top matches: {len(top)}")
    if top:
        print(f"Top candidate: {top[0]['full_name']} | Score: {round(float(top[0]['final_score']), 1)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark TalentSignal batch scoring with synthetic candidates.")
    parser.add_argument("--sizes", nargs="*", type=int, default=[1000, 10000], help="Candidate pool sizes to benchmark.")
    parser.add_argument("--include-100k", action="store_true", help="Also benchmark 100000 synthetic candidates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    temp_dir = tempfile.TemporaryDirectory()
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(temp_dir.name) / 'benchmark.db'}"
    ensure_database()
    role_id = ensure_role()
    sizes = list(args.sizes)
    if args.include_100k and 100000 not in sizes:
        sizes.append(100000)
    print("TalentSignal AI batch scoring benchmark")
    print(f"Database: {os.environ['DATABASE_URL']}")
    for size in sizes:
        run_benchmark(size, role_id)
    temp_dir.cleanup()


if __name__ == "__main__":
    main()
