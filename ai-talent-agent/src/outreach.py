from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.llm_client import LLMClient

PERSONA_POSITIONING = {
    "compensation_driven": "Highlight upside, level progression, and why the opportunity compounds their earning power.",
    "mission_driven": "Lead with impact, customer value, and why the team’s mission would feel meaningful.",
    "remote_only": "Lead with remote-by-design collaboration and predictable flexibility.",
    "actively_looking": "Use a direct hook and make the next step feel easy.",
    "passive_but_open": "Make the opportunity feel selective and aligned with career progression.",
    "skeptical": "Be concrete, low-pressure, and credible.",
    "fast_responder": "Keep it short, sharp, and action-oriented.",
    "slow_responder": "Give context in one note and reduce urgency pressure.",
    "not_interested": "Respect their time and keep the door open politely.",
}


def generate_outreach_message(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    match_result: dict[str, Any],
    llm_client: LLMClient,
) -> dict[str, Any]:
    """Generate adaptive outreach and preserve evidence for recruiter review."""

    persona = candidate.get("engagement_persona", "passive_but_open")
    resume_hook = _resume_hook(candidate.get("resume_text", ""), candidate.get("summary", ""))
    trajectory_reason = _trajectory_reason(candidate, jd)
    persona_strategy = PERSONA_POSITIONING.get(
        persona,
        "Make the note feel personal, concise, and relevant to their next step.",
    )
    personalization_inputs = {
        "candidate_name": candidate["name"],
        "candidate_title": candidate["current_title"],
        "target_role": jd["role_title"],
        "resume_hook": resume_hook,
        "trajectory_reason": trajectory_reason,
        "persona_strategy": persona_strategy,
    }

    response = llm_client.complete(
        system_prompt=(
            "You are an experienced recruiter writing human outreach. "
            "Write a concise message under 120 words. "
            "Use one specific experience or project from the candidate background, "
            "explain why this role fits their trajectory, include a short hook, and keep the tone non-corporate. "
            "Avoid generic phrases like 'you match these skills'."
        ),
        user_prompt=(
            f"Candidate: {candidate['name']}, {candidate['current_title']}\n"
            f"Role: {jd['role_title']}\n"
            f"Specific background hook: {resume_hook}\n"
            f"Why this role fits trajectory: {trajectory_reason}\n"
            f"Engagement persona: {persona}\n"
            f"Persona strategy: {persona_strategy}\n"
            "Write the outreach note."
        ),
        temperature=0.45,
    )
    if response:
        message = response.text.strip()
        mode = f"LLM-personalized via {response.provider}"
    else:
        message = _fallback_message(candidate, jd, resume_hook, trajectory_reason, persona)
        mode = "Template fallback"

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    evidence = [
        "Outreach is recruiter-generated inside the app.",
        f"Generated at {generated_at}.",
        f"Personalization mode: {mode}.",
        f"Specific resume hook used: {resume_hook}.",
        f"Trajectory rationale used: {trajectory_reason}.",
        f"Persona strategy applied: {persona_strategy}",
    ]
    communication_log = [
        {
            "step": "message_generated",
            "timestamp": generated_at,
            "channel": "draft",
            "status": "generated",
            "detail": "Outreach draft created for recruiter review.",
        }
    ]
    return {
        "message": message,
        "mode": mode,
        "evidence": evidence,
        "personalization_inputs": personalization_inputs,
        "communication_log": communication_log,
        "delivery_status": "Draft ready",
    }


def build_contact_strategy(candidate: dict[str, Any], predicted_interest: dict[str, Any]) -> dict[str, str]:
    """Create a simple outreach strategy for recruiter review."""

    likelihood = predicted_interest.get("likelihood_to_respond", 0)
    priority = "high" if likelihood >= 75 else "medium"
    timing = "immediate" if candidate.get("engagement_persona") in {"actively_looking", "fast_responder"} else "within 24 hours"
    return {
        "channel": "SMS",
        "timing": timing,
        "follow_up": "48 hours",
        "priority": priority,
    }


def generate_email_subject_body(
    candidate: dict[str, Any],
    role: dict[str, Any],
    llm_client: LLMClient,
) -> dict[str, str]:
    """Generate a human-quality subject and email body for recruiter review."""

    resume_hook = _resume_hook(candidate.get("resume_text", ""), candidate.get("summary", ""))
    trajectory_reason = _trajectory_reason(candidate, {"role_title": role.get("title", "")})
    response = llm_client.complete(
        system_prompt=(
            "You are an experienced recruiter writing a concise outreach email. "
            "Return JSON with keys subject and body. "
            "The subject should be short and human. "
            "The body should reference one concrete experience, explain why the role fits the candidate's path, "
            "and stay under 140 words."
        ),
        user_prompt=(
            f"Candidate: {candidate.get('name')}, {candidate.get('current_title')}\n"
            f"Role: {role.get('title')}\n"
            f"Resume hook: {resume_hook}\n"
            f"Trajectory reason: {trajectory_reason}\n"
        ),
        temperature=0.35,
    )
    if response:
        raw = response.text.strip()
        if '"subject"' in raw and '"body"' in raw:
            import json
            from src.utils import safe_json_loads

            parsed = safe_json_loads(raw)
            if parsed:
                return {
                    "subject": str(parsed.get("subject") or f"{role.get('title')} opportunity").strip(),
                    "body": str(parsed.get("body") or "").strip() or _fallback_email_body(candidate, role, resume_hook, trajectory_reason),
                }
    return {
        "subject": f"{role.get('title')} opportunity",
        "body": _fallback_email_body(candidate, role, resume_hook, trajectory_reason),
    }


def _resume_hook(resume_text: str, summary: str) -> str:
    text = resume_text or summary
    sentences = [sentence.strip() for sentence in text.split(".") if sentence.strip()]
    for sentence in sentences:
        lowered = sentence.lower()
        if any(token in lowered for token in ["built", "led", "designed", "delivered", "scaled", "modernized"]):
            return sentence
    return summary or "Relevant backend ownership and delivery experience"


def _trajectory_reason(candidate: dict[str, Any], jd: dict[str, Any]) -> str:
    role = jd.get("role_title", "this role")
    summary = candidate.get("summary", "")
    if "platform" in summary.lower() or "distributed" in summary.lower():
        return f"{role} builds on their path into larger-scale backend ownership"
    if "mentor" in summary.lower() or "lead" in candidate.get("current_title", "").lower():
        return f"{role} fits their trajectory toward higher-impact technical leadership"
    return f"{role} is a natural next step from their current backend scope"


def _fallback_message(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    resume_hook: str,
    trajectory_reason: str,
    persona: str,
) -> str:
    persona_line = {
        "compensation_driven": "If useful, I can share level and comp range up front.",
        "mission_driven": "The team has real product and customer impact, not just maintenance work.",
        "remote_only": "The role is set up to work well in a distributed environment.",
        "skeptical": "Happy to send specifics on the team and what they need this person to own.",
    }.get(persona, "If it sounds relevant, I can send a quick overview.")
    return (
        f"Hi {candidate['name']},\n\n"
        f"Quick note because your background stood out, especially: {resume_hook}. "
        f"We're hiring a {jd['role_title']}, and it feels aligned because {trajectory_reason}. "
        f"{persona_line}\n\n"
        "Worth a brief chat?"
    )


def _fallback_email_body(candidate: dict[str, Any], role: dict[str, Any], resume_hook: str, trajectory_reason: str) -> str:
    return (
        f"Hi {candidate['name']},\n\n"
        f"I reached out because {resume_hook}. We're hiring for a {role.get('title')} role, "
        f"and it looks like a strong fit because {trajectory_reason}. "
        "If it feels relevant, I’d be happy to share a short overview and answer any questions.\n\n"
        "Best,\nTalentSignal AI Recruiting"
    )
