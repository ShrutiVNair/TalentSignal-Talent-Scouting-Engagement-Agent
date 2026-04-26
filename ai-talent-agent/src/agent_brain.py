from __future__ import annotations

from typing import Any

from src.llm_client import call_llm
from src.utils import clamp, round_score


def evaluate_candidate(
    jd: dict[str, Any],
    candidate: dict[str, Any],
    match_score: float,
    interest_score: float,
) -> dict[str, Any]:
    """Produce a hiring recommendation with rule-based scoring and optional LLM reasoning."""

    gut_fit_score = round_score(match_score * 0.55 + interest_score * 0.45)
    hire_recommendation = _recommend(gut_fit_score, match_score, interest_score)
    confidence = _confidence_score(gut_fit_score, match_score, interest_score, hire_recommendation)
    reasoning = _generate_reasoning(
        jd=jd,
        candidate=candidate,
        match_score=match_score,
        interest_score=interest_score,
        gut_fit_score=gut_fit_score,
        hire_recommendation=hire_recommendation,
    )
    return {
        "hire_recommendation": hire_recommendation,
        "confidence": confidence,
        "gut_fit_score": gut_fit_score,
        "reasoning": reasoning,
    }


def _recommend(gut_fit_score: float, match_score: float, interest_score: float) -> str:
    if match_score >= 78 and interest_score >= 68 and gut_fit_score >= 74:
        return "Strong Yes"
    if match_score >= 62 and interest_score >= 45:
        return "Maybe"
    return "No"


def _confidence_score(
    gut_fit_score: float,
    match_score: float,
    interest_score: float,
    recommendation: str,
) -> float:
    spread_penalty = abs(match_score - interest_score) * 0.25
    if recommendation == "Strong Yes":
        base = 72 + max(gut_fit_score - 74, 0) * 0.6
    elif recommendation == "Maybe":
        base = 58 + max(gut_fit_score - 60, 0) * 0.35
    else:
        base = 64 + max(60 - gut_fit_score, 0) * 0.4
    return round_score(clamp((base - spread_penalty) / 100) * 100)


def _generate_reasoning(
    jd: dict[str, Any],
    candidate: dict[str, Any],
    match_score: float,
    interest_score: float,
    gut_fit_score: float,
    hire_recommendation: str,
) -> str:
    prompt = (
        "You are a senior recruiting decision support agent. "
        "Write 2 concise sentences explaining the recommendation for a recruiter. "
        "Do not invent scores. Keep the reasoning grounded in match, interest, seniority, and likely execution fit.\n\n"
        f"Role: {jd.get('role_title', '')}\n"
        f"Required skills: {', '.join(jd.get('required_skills', []))}\n"
        f"Candidate: {candidate.get('name', '')}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Years experience: {candidate.get('years_experience', 0)}\n"
        f"Candidate skills: {', '.join(candidate.get('skills', []))}\n"
        f"Match score: {match_score}\n"
        f"Interest score: {interest_score}\n"
        f"Gut fit score: {gut_fit_score}\n"
        f"Recommendation: {hire_recommendation}\n"
    )
    reasoning = call_llm(prompt, temperature=0.2).strip()
    if reasoning:
        return reasoning
    return (
        f"{candidate.get('name', 'This candidate')} is a {hire_recommendation.lower()} for the "
        f"{jd.get('role_title', 'target role')} role based on a Match Score of {match_score} and "
        f"Interest Score of {interest_score}. Their combined execution fit lands at {gut_fit_score}, "
        "so the recommendation reflects both capability alignment and likelihood to engage."
    )
