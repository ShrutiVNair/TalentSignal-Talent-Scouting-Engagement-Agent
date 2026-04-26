from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.database.db import fetch_all


def build_analytics_snapshot() -> dict[str, Any]:
    candidates = fetch_all("SELECT * FROM candidate")
    roles = fetch_all("SELECT * FROM role")
    matches = fetch_all("SELECT * FROM candidate_role_match")
    messages = fetch_all("SELECT * FROM outreach_message")
    feedback = fetch_all("SELECT * FROM feedback")
    compliance = fetch_all("SELECT * FROM compliance_record")

    by_source = Counter(row.get("source") or "unknown" for row in candidates)
    by_stage = Counter(row.get("stage") or "Sourced" for row in matches)
    feedback_reasons = Counter(row.get("feedback_type") or "unknown" for row in feedback)
    response_count = sum(1 for row in messages if row.get("reply_text"))
    positive_responses = sum(1 for row in messages if (row.get("reply_text") or "").lower().find("interested") >= 0)
    interviews = by_stage.get("Interview", 0) + by_stage.get("Recruiter Screen", 0)
    sent = sum(1 for row in messages if row.get("status") == "sent")
    failed = sum(1 for row in messages if row.get("status") == "failed")
    blocked = sum(1 for row in compliance if row.get("opt_out") or row.get("do_not_contact"))
    duplicates = sum(1 for row in matches if "high" in str(row.get("duplicate_status_json", "")).lower())
    parsed_resumes = sum(1 for row in candidates if row.get("source") in {"resume", "app"} or row.get("contact_source") == "resume")
    missing_email = sum(1 for row in candidates if not row.get("email"))
    email_ready = sum(1 for row in candidates if row.get("contact_readiness_status") == "Ready for email draft")
    sms_ready = sum(1 for row in candidates if row.get("contact_readiness_status") == "Ready for SMS test only")
    linkedin_manual = sum(1 for row in messages if row.get("channel") == "linkedin_manual")
    call_manual = sum(1 for row in messages if row.get("channel") == "call_manual")
    test_emails = sum(1 for row in messages if row.get("channel") == "email" and row.get("status") == "test_sent")
    production_emails = sum(1 for row in messages if row.get("channel") == "email" and row.get("status") == "sent")
    blocked_attempts = sum(1 for row in messages if row.get("status") == "blocked")

    role_health = []
    per_role_matches: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in matches:
        per_role_matches[row["role_id"]].append(row)
    for role in roles:
        role_matches = per_role_matches.get(role["id"], [])
        shortlist_count = sum(1 for row in role_matches if float(row.get("final_score", 0)) >= 70)
        response_rate = (sum(1 for row in role_matches if row.get("stage") in {"Responded", "Recruiter Screen", "Interview", "Offer", "Hired"}) / len(role_matches) * 100) if role_matches else 0.0
        compensation_mismatch = sum(1 for row in role_matches if "compensation" in str(row.get("scorecard_json", "")).lower())
        if len(role_matches) < 3 or response_rate < 15 or shortlist_count < 2:
            health = "at risk"
        elif compensation_mismatch >= max(1, len(role_matches) // 2):
            health = "needs attention"
        else:
            health = "healthy"
        role_health.append({"role_id": role["id"], "title": role["title"], "health": health, "candidate_count": len(role_matches), "response_rate": round(response_rate, 1)})

    return {
        "total_candidates": len(candidates),
        "candidates_by_source": dict(by_source),
        "active_roles": sum(1 for row in roles if row.get("status", "Open").lower() == "open"),
        "pipeline_funnel": dict(by_stage),
        "contacted_count": by_stage.get("Contacted", 0),
        "response_rate": round((response_count / sent * 100), 1) if sent else 0.0,
        "positive_response_rate": round((positive_responses / response_count * 100), 1) if response_count else 0.0,
        "interview_conversion_rate": round((interviews / max(len(matches), 1) * 100), 1) if matches else 0.0,
        "offer_conversion_rate": round((by_stage.get("Offer", 0) / max(len(matches), 1) * 100), 1) if matches else 0.0,
        "average_match_score": round(sum(float(row.get("match_score", 0)) for row in matches) / len(matches), 1) if matches else 0.0,
        "average_interest_score": round(sum(float(row.get("interest_score", 0)) for row in matches) / len(matches), 1) if matches else 0.0,
        "outreach_sent": sent,
        "outreach_failed": failed,
        "candidates_blocked_by_compliance": blocked,
        "duplicate_candidates_found": duplicates,
        "resumes_parsed": parsed_resumes,
        "candidates_imported_from_resumes": parsed_resumes,
        "candidates_missing_email": missing_email,
        "candidates_email_ready": email_ready,
        "candidates_sms_test_ready": sms_ready,
        "linkedin_manual_tasks": linkedin_manual,
        "call_manual_tasks": call_manual,
        "test_emails_sent": test_emails,
        "production_emails_sent": production_emails,
        "failed_emails": failed,
        "blocked_outreach_attempts": blocked_attempts,
        "top_rejection_reasons": dict(feedback_reasons.most_common(5)),
        "source_quality": dict(by_source),
        "role_health": role_health,
    }
