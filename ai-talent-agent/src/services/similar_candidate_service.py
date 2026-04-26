from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from src.services.candidate_service import list_candidates
from src.utils import round_score


def find_similar_candidates(candidate: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    results = []
    for other in list_candidates():
        if other["id"] == candidate["id"]:
            continue
        overlap = len(set(candidate.get("skills", [])) & set(other.get("skills", [])))
        exp_gap = abs(float(candidate.get("years_experience", 0)) - float(other.get("years_experience", 0)))
        title_similarity = SequenceMatcher(None, candidate.get("current_title", ""), other.get("current_title", "")).ratio()
        location_bonus = 0.1 if candidate.get("location") == other.get("location") else 0.0
        score = round_score(min(100.0, overlap * 12 + max(0, 20 - exp_gap * 3) + title_similarity * 35 + location_bonus * 100))
        results.append(
            {
                "candidate_id": other["id"],
                "name": other["name"],
                "current_title": other.get("current_title"),
                "similarity_score": score,
                "explanation": f"{overlap} shared skills, {title_similarity:.0%} title similarity, {exp_gap:.1f} years experience gap.",
            }
        )
    return sorted(results, key=lambda item: item["similarity_score"], reverse=True)[:limit]

