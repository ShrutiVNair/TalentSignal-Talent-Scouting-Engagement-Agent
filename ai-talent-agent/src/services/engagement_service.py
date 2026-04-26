from __future__ import annotations

import json
import re
from typing import Any

from src.agents.next_best_action import decide_next_best_action
from src.agents.ranking_agent import get_match
from src.database.db import db_cursor, fetch_all, json_dumps, utc_now
from src.services.audit_service import log_audit
from src.services.compliance_service import get_compliance_record, upsert_compliance
from src.services.outreach_service import list_messages, save_outreach_message
from src.services.role_service import get_role
from src.services.candidate_service import get_candidate
from src.utils import clamp, round_score


POSITIVE_PHRASES = [
    "interested",
    "sounds good",
    "happy to chat",
    "open to discuss",
    "available",
    "let's schedule",
    "lets schedule",
    "free this week",
    "let's talk",
    "lets talk",
    "schedule",
    "call",
    "tomorrow",
    "this week",
]
NEUTRAL_PHRASES = ["send details", "share jd", "share more", "compensation", "remote", "location", "benefits", "details", "salary"]
NEGATIVE_PHRASES = ["not interested", "not looking", "pass", "remove me", "unsubscribe", "do not contact", "stop contacting"]
SCHEDULING_PHRASES = ["available tomorrow", "free this week", "schedule", "chat", "talk", "call", "tomorrow", "this week"]


def analyze_candidate_reply(reply_text: str, previous_interest_score: float | None = None, prior_context: dict[str, Any] | None = None) -> dict[str, Any]:
    text = reply_text.strip()
    lowered = text.lower()
    signals = _matches(lowered, POSITIVE_PHRASES)
    objections = _matches(lowered, NEUTRAL_PHRASES)
    negative = _matches(lowered, NEGATIVE_PHRASES)
    scheduling = _matches(lowered, SCHEDULING_PHRASES)
    previous = 50.0 if previous_interest_score is None else float(previous_interest_score)

    if negative:
        sentiment = "negative"
        interest_level = "low"
        interest_delta = -30
        recommended_next_step = "Do not contact" if _has_opt_out_language(negative) else "Keep warm"
    elif signals and scheduling:
        sentiment = "positive"
        interest_level = "high"
        interest_delta = 25
        recommended_next_step = "Schedule recruiter screen"
    elif signals:
        sentiment = "positive"
        interest_level = "high"
        interest_delta = 18
        recommended_next_step = "Send role details"
    elif objections:
        sentiment = "neutral"
        interest_level = "medium"
        interest_delta = 7
        recommended_next_step = "Answer compensation question" if "compensation" in objections or "salary" in objections else "Send role details"
    else:
        sentiment = "neutral"
        interest_level = "medium"
        interest_delta = 0
        recommended_next_step = "Keep warm"

    if scheduling and sentiment != "negative":
        recommended_next_step = "Schedule recruiter screen"
    new_score = round_score(clamp(previous + interest_delta, 0, 100))

    return {
        "sentiment": sentiment,
        "interest_level": interest_level,
        "interest_delta": interest_delta,
        "previous_interest_score": round_score(previous),
        "new_interest_score": new_score,
        "signals": signals + scheduling,
        "objections": negative + objections,
        "recommended_next_step": recommended_next_step,
        "hr_summary": _reply_summary(text, sentiment, interest_level, interest_delta, new_score, recommended_next_step),
    }


def simulate_candidate_conversation(candidate: dict[str, Any], role: dict[str, Any], outreach_message: str) -> dict[str, Any]:
    persona = (candidate.get("engagement_persona") or "passive_but_open").lower()
    match = get_match(candidate["id"], role["id"]) or {}
    match_score = float(match.get("match_score", 50))
    skills = candidate.get("skills", [])[:3]
    role_title = role.get("title", "the role")

    if persona in {"actively_looking", "fast_responder"} or (match_score >= 82 and candidate.get("availability")):
        reply = (
            f"Thanks, this sounds interesting. My background in {', '.join(skills) or 'the space'} feels aligned, "
            "and I am available this week to talk."
        )
        sentiment = "positive"
        interest_score = 90 if "available" in reply.lower() else 84
        signals = ["aligned background", "available this week", "scheduling intent"]
        objections: list[str] = []
        recommended = "Schedule recruiter screen"
    elif persona == "compensation_driven":
        reply = "Potentially interested. Can you share compensation, level, and whether the role is remote?"
        sentiment = "positive"
        interest_score = 72
        signals = ["open to details"]
        objections = ["compensation", "level", "remote"]
        recommended = "Answer compensation question"
    elif persona == "remote_only":
        reply = "I am open to learning more if the role is fully remote and the collaboration model is clear."
        sentiment = "neutral"
        interest_score = 66
        signals = ["open to details"]
        objections = ["remote"]
        recommended = "Send role details"
    elif persona == "not_interested":
        reply = "Thanks for reaching out, but I am not looking right now. Please keep me in mind for the future."
        sentiment = "negative"
        interest_score = 24
        signals = []
        objections = ["not looking"]
        recommended = "Keep warm"
    elif match_score >= 70:
        reply = f"Thanks for the note. {role_title} sounds relevant. Could you send more about the team and expectations?"
        sentiment = "neutral"
        interest_score = 62
        signals = ["asked for details"]
        objections = ["team context"]
        recommended = "Send role details"
    else:
        reply = "Thanks for reaching out. I would need more detail before knowing whether this is relevant."
        sentiment = "neutral"
        interest_score = 45
        signals = ["low commitment"]
        objections = ["needs more detail"]
        recommended = "Recruiter review"

    return {
        "outreach_message": outreach_message,
        "candidate_reply": reply,
        "sentiment": sentiment,
        "interest_score": round_score(interest_score),
        "signals": signals,
        "objections": objections,
        "recommended_next_step": recommended,
        "hr_summary": (
            f"{candidate['name']} gave a {sentiment} simulated reply. "
            f"Interest is {round_score(interest_score)}%. Recommended next step: {recommended}."
        ),
    }


def simulate_outreach_for_role(role_id: int, limit: int = 5) -> dict[str, Any]:
    role = get_role(role_id)
    if not role:
        return {"status": "failed", "error": "Role not found.", "engaged_count": 0, "average_interest_score": 0, "results": []}
    matches = fetch_all(
        """
        SELECT m.*, c.full_name, c.current_title, c.current_company
        FROM candidate_role_match m
        JOIN candidate c ON c.id = m.candidate_id
        WHERE m.role_id = ?
        ORDER BY m.match_score DESC, m.final_score DESC
        LIMIT ?
        """,
        (role_id, limit),
    )
    results = []
    for match in matches:
        candidate = get_candidate(match["candidate_id"])
        if not candidate:
            continue
        outreach = _simulation_outreach_message(candidate, role, match)
        simulation = simulate_candidate_conversation(candidate, role, outreach)
        _persist_simulated_conversation(candidate, role, simulation)
        _apply_simulated_interest(candidate["id"], role_id, simulation)
        results.append({"candidate_id": candidate["id"], **simulation})
    average = round_score(sum(item["interest_score"] for item in results) / len(results)) if results else 0
    log_audit("role", role_id, "outreach_simulated", {"engaged_count": len(results), "average_interest_score": average})
    return {"status": "complete", "engaged_count": len(results), "average_interest_score": average, "results": results}


def capture_candidate_reply(candidate_id: str, role_id: int, reply_text: str) -> dict[str, Any]:
    reply_text = reply_text.strip()
    if not reply_text:
        return {"status": "failed", "error": "Reply text is empty."}

    match = get_match(candidate_id, role_id)
    previous_interest = float(match["interest_score"]) if match else 50.0
    analysis = analyze_candidate_reply(reply_text, previous_interest, {"timeline": list_reply_timeline(candidate_id, role_id)})
    message_id = save_outreach_message(
        candidate_id,
        role_id,
        "email_reply",
        reply_text,
        status="received",
        delivery_status="Manual reply captured",
        metadata={"analysis": analysis},
    )
    updated = update_interest_from_reply(candidate_id, role_id, analysis)
    if analysis["recommended_next_step"] == "Do not contact":
        upsert_compliance(candidate_id, {"do_not_contact": 1, "opt_out": 1, "compliance_notes": "Candidate requested no further contact."})
    log_audit("candidate_role_match", f"{candidate_id}:{role_id}", "reply_analyzed", {"message_id": message_id, **analysis})
    return {"status": "saved", "message_id": message_id, "analysis": analysis, "match": updated}


def latest_simulation_for_candidate(candidate_id: str, role_id: int) -> dict[str, Any] | None:
    messages = [
        item
        for item in list_messages(candidate_id, role_id)
        if item["channel"] == "simulated_reply"
    ]
    if not messages:
        return None
    metadata = messages[0].get("metadata", {})
    return metadata.get("simulation")


def update_interest_from_reply(candidate_id: str, role_id: int, analysis: dict[str, Any]) -> dict[str, Any]:
    match = get_match(candidate_id, role_id)
    current = float(match["interest_score"]) if match else 50.0
    new_score = round_score(clamp(float(analysis.get("new_interest_score", current + analysis["interest_delta"])), 0, 100))
    scorecard = dict((match or {}).get("scorecard") or {})
    scorecard["interest_score"] = new_score
    scorecard["conversation_summary"] = analysis["hr_summary"]
    next_action = decide_next_best_action(
        {**scorecard, "final_score": float((match or {}).get("final_score", scorecard.get("final_score", 0)))},
        (match or {}).get("compliance_status") or {"outreach_allowed": True, "reasons": []},
        (match or {}).get("duplicate_status") or {"duplicate_risk": "none"},
        (match or {}).get("stage") or "Contacted",
    )
    action = analysis.get("recommended_next_step") or next_action["action"]
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE candidate_role_match
            SET interest_score = ?, next_best_action = ?, scorecard_json = ?, updated_at = ?
            WHERE candidate_id = ? AND role_id = ?
            """,
            (new_score, action, json_dumps(scorecard), utc_now(), candidate_id, role_id),
        )
    return get_match(candidate_id, role_id) or {"candidate_id": candidate_id, "role_id": role_id, "interest_score": new_score, "next_best_action": action}


def list_reply_timeline(candidate_id: str, role_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT * FROM outreach_message
        WHERE candidate_id = ? AND role_id = ? AND channel IN ('email_reply', 'simulated_reply')
        ORDER BY created_at ASC
        """,
        (candidate_id, role_id),
    )
    timeline = []
    for row in rows:
        metadata = json.loads(row.get("metadata_json") or "{}")
        analysis = metadata.get("analysis", {})
        timeline.append(
            {
                "id": row["id"],
                "reply_text": row["message_body"],
                "channel": row["channel"],
                "created_at": row["created_at"],
                "analysis": analysis,
            }
        )
    return timeline


def build_hr_decision_summary(candidate_id: str, role_id: int) -> dict[str, Any]:
    candidate = get_candidate(candidate_id)
    role = get_role(role_id)
    match = get_match(candidate_id, role_id)
    timeline = list_reply_timeline(candidate_id, role_id)
    if not candidate or not role:
        return {"status": "missing", "summary": "Select a role and candidate to generate an HR summary."}

    match_score = float((match or {}).get("match_score", 0))
    interest_score = float((match or {}).get("interest_score", 50))
    latest = timeline[-1]["analysis"] if timeline else {}
    simulation = latest_simulation_for_candidate(candidate_id, role_id)
    if simulation and not latest:
        latest = simulation
    compliance = get_compliance_record(candidate_id)
    scorecard = (match or {}).get("scorecard") or {}
    objections = []
    for item in timeline:
        objections.extend(item["analysis"].get("objections", []))
    key_reasons = scorecard.get("strengths") or candidate.get("skills", [])[:3] or ["Candidate profile is ready for recruiter review."]

    if compliance.get("do_not_contact") or compliance.get("opt_out") or latest.get("recommended_next_step") == "Do not contact":
        action = "Do not contact"
    elif match_score >= 80 and interest_score >= 70:
        action = "Schedule recruiter screen"
    elif match_score >= 70 and 40 <= interest_score < 70 and any(term in objections for term in ["compensation", "salary"]):
        action = "Answer compensation question"
    elif match_score >= 70 and 40 <= interest_score < 70:
        action = "Send role details"
    elif interest_score < 40:
        action = "Keep warm"
    else:
        action = "Keep warm"

    engagement_status = "No replies yet"
    if timeline:
        interest_level = latest.get("interest_level") or ("high" if interest_score >= 70 else "medium" if interest_score >= 40 else "low")
        engagement_status = f"{interest_level.title()} interest, {latest.get('sentiment', 'neutral')} sentiment"

    return {
        "status": "ready",
        "candidate_name": candidate["name"],
        "role": role["title"],
        "match_score": round_score(match_score),
        "interest_score": round_score(interest_score),
        "engagement_status": engagement_status,
        "key_fit_reasons": key_reasons[:4],
        "candidate_concerns": sorted(set(objections)) or ["No explicit objections captured."],
        "recommended_next_step": action,
        "suggested_recruiter_action": action,
        "summary": _hr_summary_text(candidate, role, match_score, interest_score, key_reasons, objections, latest, action),
        "latest_reply_summary": latest.get("hr_summary", "Outreach simulation has not run yet."),
        "reply_count": len(timeline),
    }


def _simulation_outreach_message(candidate: dict[str, Any], role: dict[str, Any], match: dict[str, Any]) -> str:
    scorecard = json.loads(match.get("scorecard_json") or "{}") if "scorecard_json" in match else match.get("scorecard", {})
    strength = (scorecard.get("strengths") or candidate.get("skills", [])[:1] or ["your background"])[0]
    return (
        f"Hi {candidate['name']}, I came across your background and noticed {strength}. "
        f"We are hiring for {role.get('title')}, and your experience looks relevant. "
        "Would you be open to learning more?"
    )


def _persist_simulated_conversation(candidate: dict[str, Any], role: dict[str, Any], simulation: dict[str, Any]) -> None:
    existing = [
        item
        for item in list_messages(candidate["id"], role["id"])
        if item["channel"] in {"simulated_outreach", "simulated_reply"}
    ]
    if existing:
        return
    save_outreach_message(
        candidate["id"],
        role["id"],
        "simulated_outreach",
        simulation["outreach_message"],
        status="simulated",
        delivery_status="Outreach simulation generated",
        metadata={"simulation": simulation},
    )
    save_outreach_message(
        candidate["id"],
        role["id"],
        "simulated_reply",
        simulation["candidate_reply"],
        status="simulated_reply",
        delivery_status="Candidate reply simulated",
        metadata={"analysis": {
            "sentiment": simulation["sentiment"],
            "interest_level": "high" if simulation["interest_score"] >= 70 else "medium" if simulation["interest_score"] >= 40 else "low",
            "interest_delta": 0,
            "new_interest_score": simulation["interest_score"],
            "signals": simulation["signals"],
            "objections": simulation["objections"],
            "recommended_next_step": simulation["recommended_next_step"],
            "hr_summary": simulation["hr_summary"],
        }, "simulation": simulation},
    )


def _apply_simulated_interest(candidate_id: str, role_id: int, simulation: dict[str, Any]) -> None:
    match = get_match(candidate_id, role_id)
    if not match:
        return
    scorecard = dict(match.get("scorecard") or {})
    scorecard["interest_score"] = simulation["interest_score"]
    scorecard["conversation_summary"] = simulation["hr_summary"]
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE candidate_role_match
            SET interest_score = ?, next_best_action = ?, scorecard_json = ?, updated_at = ?
            WHERE candidate_id = ? AND role_id = ?
            """,
            (
                simulation["interest_score"],
                simulation["recommended_next_step"],
                json_dumps(scorecard),
                utc_now(),
                candidate_id,
                role_id,
            ),
        )


def _matches(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if re.search(rf"\b{re.escape(phrase)}\b", text)]


def _has_opt_out_language(phrases: list[str]) -> bool:
    return any(phrase in {"remove me", "unsubscribe", "do not contact", "stop contacting"} for phrase in phrases)


def _reply_summary(reply_text: str, sentiment: str, interest_level: str, interest_delta: float, new_score: float, next_step: str) -> str:
    preview = reply_text[:140] + ("..." if len(reply_text) > 140 else "")
    sign = "+" if interest_delta > 0 else ""
    return f"Latest reply is {sentiment} with {interest_level} interest. Interest {sign}{interest_delta} to {new_score}%. Suggested action: {next_step}. Reply: {preview}"


def _hr_summary_text(
    candidate: dict[str, Any],
    role: dict[str, Any],
    match_score: float,
    interest_score: float,
    key_reasons: list[str],
    objections: list[str],
    latest: dict[str, Any],
    action: str,
) -> str:
    fit = ", ".join(key_reasons[:2]) if key_reasons else "relevant background"
    concern_text = ""
    clean_objections = [item for item in objections if item not in NEGATIVE_PHRASES]
    if clean_objections:
        concern_text = f" The candidate raised {', '.join(sorted(set(clean_objections))[:2])}, so HR should address that clearly."
    reply_text = "No reply has been captured yet."
    if latest:
        reply_text = latest.get("hr_summary", "The latest reply was analyzed.")
    return (
        f"{candidate['name']} is a {round_score(match_score)}% match for the {role['title']} role with "
        f"{round_score(interest_score)}% current interest. Key fit evidence: {fit}."
        f"{concern_text} {reply_text} Recommended: {action}."
    )
