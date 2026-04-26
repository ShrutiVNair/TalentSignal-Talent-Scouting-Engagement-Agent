from __future__ import annotations

import time
from typing import Any

from src.agents.compliance_agent import run_compliance
from src.agents.next_best_action import decide_next_best_action
from src.agents.ranking_agent import get_match, save_match
from src.integrations import get_ats_adapter
from src.llm_client import LLMClient
from src.outreach import generate_email_subject_body
from src.services.batch_scoring_service import get_top_matches, score_candidates_for_role
from src.services.candidate_service import get_candidate, list_candidates_page
from src.services.outreach_service import save_outreach_message
from src.services.role_service import get_role


def run_talent_scan(role_id: int, options: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    role = get_role(role_id)
    if not role:
        return {
            "processed_count": 0,
            "scored_count": 0,
            "qualified_count": 0,
            "blocked_count": 0,
            "duplicate_risk_count": 0,
            "drafts_created": 0,
            "top_candidates": [],
            "duration_seconds": 0.0,
            "warnings": ["Role not found."],
        }

    max_candidates = int(options.get("max_candidates") or 100)
    batch_size = int(options.get("batch_size") or 25)
    score_threshold = float(options.get("score_threshold") or 0)
    top_n = int(options.get("generate_outreach_for_top_n") or 0)
    skip_duplicates = bool(options.get("skip_duplicates"))
    skip_blocked = bool(options.get("skip_compliance_blocked"))

    page = list_candidates_page(page=1, page_size=max_candidates)
    candidate_ids = [candidate["id"] for candidate in page["items"]]
    scoring_summary = score_candidates_for_role(role_id, candidate_ids=candidate_ids, batch_size=batch_size, progress_callback=options.get("progress_callback"))

    ats_adapter = get_ats_adapter()
    blocked_count = 0
    duplicate_risk_count = 0
    drafts_created = 0
    qualified_rows: list[dict[str, Any]] = []
    for row in get_top_matches(role_id, limit=max_candidates):
        candidate = get_candidate(row["candidate_id"])
        if not candidate:
            continue
        duplicate = ats_adapter.check_duplicate(candidate)
        compliance = run_compliance(candidate, role, duplicate)
        scorecard = row.get("scorecard") or (get_match(candidate["id"], role_id) or {}).get("scorecard", {})
        next_action = decide_next_best_action(scorecard, compliance, duplicate, row.get("stage", "Shortlisted"))
        save_match(candidate["id"], role_id, scorecard, stage=row.get("stage", "Shortlisted"), duplicate_status=duplicate, compliance_status=compliance, next_best_action=next_action["action"])

        is_duplicate = duplicate.get("duplicate_risk") in {"medium", "high"}
        is_blocked = not compliance.get("outreach_allowed")
        if is_duplicate:
            duplicate_risk_count += 1
        if is_blocked:
            blocked_count += 1
        if row.get("final_score", 0) < score_threshold:
            continue
        if skip_duplicates and is_duplicate:
            continue
        if skip_blocked and is_blocked:
            continue
        qualified_rows.append({**row, "duplicate_status": duplicate, "compliance_status": compliance, "next_best_action": next_action["action"]})

    qualified_rows.sort(key=lambda item: float(item.get("final_score", 0)), reverse=True)
    if top_n > 0:
        llm_client = LLMClient()
        for row in qualified_rows[:top_n]:
            candidate = get_candidate(row["candidate_id"])
            if not candidate:
                continue
            email_assets = generate_email_subject_body(candidate, role, llm_client)
            save_outreach_message(candidate["id"], role_id, "email", email_assets["body"], status="draft", delivery_status="Draft created by talent scan", metadata={"subject": email_assets["subject"], "automation_mode": options.get("automation_mode", "review_first")})
            drafts_created += 1

    duration = round(time.perf_counter() - started, 2)
    return {
        "processed_count": len(candidate_ids),
        "scored_count": scoring_summary["scored_count"],
        "qualified_count": len(qualified_rows),
        "blocked_count": blocked_count,
        "duplicate_risk_count": duplicate_risk_count,
        "drafts_created": drafts_created,
        "top_candidates": qualified_rows[:10],
        "duration_seconds": duration,
        "warnings": scoring_summary.get("warnings", []),
    }
