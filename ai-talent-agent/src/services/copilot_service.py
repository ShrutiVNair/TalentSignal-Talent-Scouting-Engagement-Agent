from __future__ import annotations

import re
from typing import Any

from src.agents.ranking_agent import list_matches
from src.services.analytics_service import build_analytics_snapshot
from src.services.candidate_service import get_candidate, list_candidates, search_candidates
from src.services.similar_candidate_service import find_similar_candidates


def run_copilot(command: str, role_id: int | None = None) -> str:
    text = command.strip()
    lowered = text.lower()
    matches = list_matches(role_id) if role_id else []

    if lowered.startswith("find ") or lowered.startswith("show ") and "candidates" in lowered:
        results = search_candidates(text.replace("find", "").replace("show", "").strip())
        if results:
            names = ", ".join(candidate["name"] for candidate in results[:5])
            return f"Found {len(results)} candidate matches. Top results: {names}."
        return "I could not find a direct candidate match. Try role, skill, location, risk, or compensation phrasing."
    if "high risk" in lowered:
        high_risk = [row for row in matches if float(row.get("risk_score", 0)) >= 60]
        return f"High-risk candidates: {', '.join(row['full_name'] for row in high_risk[:5]) or 'none'}."
    if lowered.startswith("why is ") and " ranked above " in lowered:
        parts = re.split(r" ranked above ", text, flags=re.IGNORECASE)
        if len(parts) == 2:
            left_name = parts[0].replace("Why is", "").strip()
            right_name = parts[1].strip(" ?")
            left = next((row for row in matches if row["full_name"].lower() == left_name.lower()), None)
            right = next((row for row in matches if row["full_name"].lower() == right_name.lower()), None)
            if left and right:
                return f"{left['full_name']} is above {right['full_name']} because the adjusted final score is {left['adjusted_final_score']} vs {right['adjusted_final_score']}, with stronger {left['scorecard'].get('strengths', ['fit'])[0].lower()}."
    if "warmer outreach" in lowered:
        return "Try leading with one concrete project hook, keep the tone low-pressure, and ask for a short exploratory chat instead of a formal interview."
    if "compensation risk" in lowered:
        risky = [row for row in matches if row["scorecard"].get("compensation_risk") in {"high", "medium"}]
        return f"Candidates with compensation risk: {', '.join(row['full_name'] for row in risky[:5]) or 'none'}."
    if "ready for interview" in lowered:
        ready = [row for row in matches if row.get("stage") in {"Responded", "Recruiter Screen"} or row.get("next_best_action") == "Schedule recruiter screen"]
        return f"Candidates ready for interview: {', '.join(row['full_name'] for row in ready[:5]) or 'none'}."
    if "roles are at risk" in lowered or "which roles are at risk" in lowered:
        health = [row for row in build_analytics_snapshot()["role_health"] if row["health"] == "at risk"]
        return f"Roles at risk: {', '.join(role['title'] for role in health) or 'none'}."
    if "find more candidates like this" in lowered:
        all_candidates = list_candidates()
        if all_candidates:
            similar = find_similar_candidates(all_candidates[0], limit=3)
            return f"Similar candidates to {all_candidates[0]['name']}: {', '.join(row['name'] for row in similar)}."
    return (
        "I didn't recognize that command yet. Try one of these: "
        "'Find backend engineers in Bangalore with Kafka', 'Show high risk candidates', "
        "'Show candidates with compensation risk', 'Show candidates ready for interview', "
        "'Which roles are at risk?', or 'Why is Candidate A ranked above Candidate B?'."
    )
