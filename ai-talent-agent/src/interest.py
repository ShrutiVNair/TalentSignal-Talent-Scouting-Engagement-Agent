from __future__ import annotations

from typing import Any

from src.llm_client import call_llm
from src.utils import (
    availability_to_days,
    clamp,
    compensation_alignment,
    location_alignment,
    round_score,
    safe_json_loads,
    work_mode_alignment,
)


PERSONA_WEIGHTS = {
    "actively_looking": (0.95, 0.9),
    "passive_but_open": (0.72, 0.68),
    "compensation_driven": (0.7, 0.65),
    "mission_driven": (0.76, 0.75),
    "remote_only": (0.8, 0.72),
    "not_interested": (0.15, 0.12),
    "skeptical": (0.45, 0.4),
    "fast_responder": (0.88, 0.9),
    "slow_responder": (0.62, 0.55),
}


def predict_interest(jd: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Predict response likelihood before simulated outreach runs."""

    fallback_score = _fallback_interest_prediction(jd, candidate)
    prompt = (
        "You are a recruiting engagement prediction assistant. "
        "Return JSON only with keys likelihood_to_respond and reasoning. "
        "likelihood_to_respond must be an integer from 0 to 100.\n\n"
        f"Role: {jd.get('role_title', '')}\n"
        f"Work mode: {jd.get('work_mode', '')}\n"
        f"Candidate title: {candidate.get('current_title', '')}\n"
        f"Candidate persona: {candidate.get('engagement_persona', '')}\n"
        f"Availability: {candidate.get('availability', '')}\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('summary', '')}\n"
    )
    raw_response = call_llm(prompt, temperature=0.2)
    parsed = safe_json_loads(raw_response) if raw_response else None
    if parsed:
        score = int(parsed.get("likelihood_to_respond", fallback_score["likelihood_to_respond"]))
        return {
            "likelihood_to_respond": max(0, min(100, score)),
            "reasoning": parsed.get("reasoning") or fallback_score["reasoning"],
            "prediction_mode": "LLM-assisted",
        }
    return {
        **fallback_score,
        "prediction_mode": "Deterministic fallback",
    }


def score_interest(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    conversation: dict[str, Any],
) -> dict[str, Any]:
    """Compute the auditable Interest Score from conversation and profile signals."""

    persona = candidate.get("engagement_persona", "passive_but_open")
    openness_base, enthusiasm_base = PERSONA_WEIGHTS.get(persona, PERSONA_WEIGHTS["passive_but_open"])

    openness = openness_base
    enthusiasm = _enthusiasm_from_text(conversation["candidate_reply"], enthusiasm_base)
    availability = _availability_score(candidate.get("availability", ""))
    compensation = compensation_alignment(candidate.get("compensation_expectation", ""), jd)
    location_fit = (
        location_alignment(candidate.get("location", ""), str(jd.get("location_preference", "Flexible")), remote_first=False)
        + work_mode_alignment(candidate.get("work_mode_preference", ""), str(jd.get("work_mode", "flexible")))
    ) / 2

    interest_score = round_score(
        (
            openness * 0.35
            + enthusiasm * 0.25
            + availability * 0.20
            + compensation * 0.10
            + location_fit * 0.10
        )
        * 100
    )
    level = "High" if interest_score >= 75 else "Medium" if interest_score >= 50 else "Low"

    evidence = list(conversation.get("conversation_evidence", []))
    evidence.extend(
        [
            f"Availability signal scored {round_score(availability * 100)}.",
            f"Compensation alignment scored {round_score(compensation * 100)}.",
            f"Location/work-mode alignment scored {round_score(location_fit * 100)}.",
        ]
    )
    next_action = recommend_next_action(level, persona)
    summary = (
        f"Interest Score is {interest_score} ({level}). "
        f"The strongest signals came from {interest_driver(openness, enthusiasm, availability)}."
    )

    return {
        "interest_score": interest_score,
        "interest_level": level,
        "interest_summary": summary,
        "conversation_evidence": evidence,
        "recommended_next_action": next_action,
        "interest_component_scores": {
            "openness_to_role": round_score(openness * 100),
            "response_enthusiasm": round_score(enthusiasm * 100),
            "availability_timeline": round_score(availability * 100),
            "compensation_alignment": round_score(compensation * 100),
            "location_work_mode_alignment": round_score(location_fit * 100),
        },
    }


def _fallback_interest_prediction(jd: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    persona = candidate.get("engagement_persona", "passive_but_open")
    base = {
        "actively_looking": 84,
        "passive_but_open": 63,
        "compensation_driven": 58,
        "mission_driven": 66,
        "remote_only": 62,
        "not_interested": 18,
        "skeptical": 41,
        "fast_responder": 78,
        "slow_responder": 49,
    }.get(persona, 55)
    availability_bonus = 10 if candidate.get("availability", "").lower() == "immediate" else 0
    location_bonus = 8 if jd.get("work_mode", "") == "remote" and candidate.get("work_mode_preference", "") == "remote" else 0
    likelihood = max(0, min(100, base + availability_bonus + location_bonus))
    reasoning = (
        f"Predicted response likelihood is {likelihood} based on the {persona.replace('_', ' ')} persona, "
        f"current availability of {candidate.get('availability', 'unknown')}, and role work-mode alignment."
    )
    return {
        "likelihood_to_respond": likelihood,
        "reasoning": reasoning,
    }


def _availability_score(value: str) -> float:
    days = availability_to_days(value)
    if days <= 7:
        return 1.0
    if days <= 21:
        return 0.85
    if days <= 45:
        return 0.65
    return 0.4


def _enthusiasm_from_text(text: str, base: float) -> float:
    lowered = text.lower()
    bonus = 0.0
    if "happy to chat" in lowered or "aligned" in lowered or "interesting" in lowered:
        bonus += 0.08
    if "not looking" in lowered or "won't be a fit" in lowered:
        bonus -= 0.22
    return clamp(base + bonus)


def interest_driver(openness: float, enthusiasm: float, availability: float) -> str:
    scores = {
        "strong openness to the role": openness,
        "positive response energy": enthusiasm,
        "near-term availability": availability,
    }
    return max(scores, key=scores.get)


def recommend_next_action(level: str, persona: str) -> str:
    if level == "High":
        return "Move to recruiter screen within 48 hours"
    if persona == "compensation_driven":
        return "Share level and compensation band before scheduling"
    if persona == "skeptical":
        return "Send a tighter role brief and team context before asking for a call"
    if level == "Low":
        return "Nurture asynchronously and deprioritize for this role"
    return "Send a targeted follow-up with role specifics and timing"
