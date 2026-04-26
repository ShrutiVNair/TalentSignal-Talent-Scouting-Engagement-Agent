from __future__ import annotations

from typing import Any

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover
    TfidfVectorizer = None
    cosine_similarity = None

from src.utils import (
    clamp,
    infer_seniority,
    location_alignment,
    normalize_text,
    profile_completeness,
    round_score,
    scrub_protected_attributes,
    seniority_value,
    slugify_skill,
    top_strength,
    unique_list,
    work_mode_alignment,
)


def score_candidates(
    jd: dict[str, Any],
    candidates: list[dict[str, Any]],
    controls: dict[str, Any],
) -> list[dict[str, Any]]:
    jd_text = build_jd_text(jd)
    candidate_texts = [build_candidate_text(candidate) for candidate in candidates]
    if TfidfVectorizer is not None and cosine_similarity is not None:
        vectorizer = TfidfVectorizer(stop_words="english")
        similarity_scores = cosine_similarity(vectorizer.fit_transform([jd_text, *candidate_texts])[0:1], vectorizer.transform(candidate_texts))[0]
    else:
        similarity_scores = [_keyword_overlap_similarity(jd_text, text) for text in candidate_texts]

    scored = []
    for index, candidate in enumerate(candidates):
        result = score_candidate(candidate, jd, similarity=float(similarity_scores[index]), controls=controls)
        if passes_filters(candidate, jd, controls):
            scored.append(result)
    return sorted(scored, key=lambda item: item["match_score"], reverse=True)


def score_candidate(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    similarity: float,
    controls: dict[str, Any],
) -> dict[str, Any]:
    required_skills = jd.get("required_skills", [])
    nice_skills = jd.get("nice_to_have_skills", [])
    candidate_skills = candidate.get("skills", [])
    candidate_nice = candidate.get("nice_to_have_skills", [])

    matched_required = intersect_skills(required_skills, candidate_skills + candidate_nice)
    missing_required = [skill for skill in required_skills if skill not in matched_required]
    matched_nice = intersect_skills(nice_skills, candidate_skills + candidate_nice)

    required_ratio = len(matched_required) / max(len(required_skills), 1)
    if controls.get("skills_priority"):
        required_ratio = clamp(required_ratio - (0.12 if len(missing_required) >= 2 else 0.0))

    experience_score = _experience_score(candidate, jd)
    seniority_score = _seniority_score(candidate, jd)
    experience_component = (experience_score + seniority_score) / 2

    domain_component = _domain_score(candidate, jd, similarity)
    location_component = _location_score(candidate, jd, controls)
    nice_component = len(matched_nice) / max(len(nice_skills), 1) if nice_skills else 1.0
    completeness_component = profile_completeness(candidate)

    weighted_score = (
        required_ratio * 0.40
        + experience_component * 0.20
        + domain_component * 0.15
        + location_component * 0.10
        + nice_component * 0.10
        + completeness_component * 0.05
    )
    match_score = round_score(weighted_score * 100)

    strengths = unique_list(
        [
            f"Matched {len(matched_required)}/{max(len(required_skills), 1)} required skills",
            "Domain relevance aligns with the target role" if domain_component >= 0.7 else "",
            "Remote/work mode looks aligned" if location_component >= 0.8 else "",
            "Profile is highly complete" if completeness_component >= 0.95 else "",
        ]
    )
    risks = unique_list(
        [
            f"Missing required skills: {', '.join(missing_required[:3])}" if missing_required else "",
            "Years of experience may be below target" if experience_score < 0.6 else "",
            "Location or work-mode mismatch may slow conversion" if location_component < 0.5 else "",
            "Candidate may be overqualified for the role" if candidate.get("years_experience", 0) >= jd.get("years_experience", 0) + 6 else "",
            "Compensation expectations should be validated early" if candidate.get("engagement_persona") == "compensation_driven" else "",
        ]
    )
    explanation = (
        f"{candidate['name']} scores {match_score} on the auditable match rubric. "
        f"They match {len(matched_required)} required skills and {len(matched_nice)} nice-to-have skills, "
        f"with domain relevance assessed from resume text, summary, and JD similarity."
    )

    return {
        "candidate_id": candidate["id"],
        "candidate": candidate,
        "match_score": match_score,
        "matched_skills": matched_required,
        "missing_skills": missing_required,
        "strengths": strengths,
        "risk_flags": risks,
        "top_strength": top_strength(strengths),
        "main_risk": risks[0] if risks else "No major risk flags",
        "match_component_scores": {
            "required_skills": round_score(required_ratio * 100),
            "experience_seniority": round_score(experience_component * 100),
            "domain_relevance": round_score(domain_component * 100),
            "location_work_mode": round_score(location_component * 100),
            "nice_to_have": round_score(nice_component * 100),
            "profile_completeness": round_score(completeness_component * 100),
        },
        "explanation": explanation,
    }


def passes_filters(candidate: dict[str, Any], jd: dict[str, Any], controls: dict[str, Any]) -> bool:
    min_years = int(controls.get("min_years_experience", 0) or 0)
    if candidate.get("years_experience", 0) < min_years:
        return False
    required_location = normalize_text(str(controls.get("required_location", "")).strip())
    if required_location:
        location = normalize_text(candidate.get("location", ""))
        if required_location not in location:
            if required_location == "united states" and ("remote - us" in location or "," in candidate.get("location", "")):
                return True
            return False
    return True


def intersect_skills(left: list[str], right: list[str]) -> list[str]:
    right_lookup = {slugify_skill(skill): skill for skill in right}
    matches = []
    for skill in left:
        if slugify_skill(skill) in right_lookup:
            matches.append(skill)
    return matches


def _experience_score(candidate: dict[str, Any], jd: dict[str, Any]) -> float:
    target = jd.get("years_experience", 0)
    actual = candidate.get("years_experience", 0)
    if target <= 0:
        return 1.0
    if actual >= target:
        if actual <= target + 4:
            return 1.0
        return 0.8
    return clamp(actual / target)


def _seniority_score(candidate: dict[str, Any], jd: dict[str, Any]) -> float:
    candidate_value = seniority_value(infer_seniority(candidate.get("current_title", "")))
    jd_value = seniority_value(str(jd.get("seniority", "mid")))
    distance = abs(candidate_value - jd_value)
    return clamp(1.0 - distance * 0.2)


def _domain_score(candidate: dict[str, Any], jd: dict[str, Any], similarity: float) -> float:
    jd_keywords = {normalize_text(keyword) for keyword in jd.get("search_keywords", [])}
    candidate_text = normalize_text(
        scrub_protected_attributes(
            " ".join(
                str(value or "")
                for value in [
                    candidate.get("summary"),
                    candidate.get("domain_experience"),
                    candidate.get("resume_text"),
                ]
            )
        )
    )
    overlap = sum(1 for keyword in jd_keywords if keyword and keyword in candidate_text)
    overlap_ratio = overlap / max(len(jd_keywords), 1)
    return clamp(overlap_ratio * 0.55 + similarity * 0.45)


def _location_score(candidate: dict[str, Any], jd: dict[str, Any], controls: dict[str, Any]) -> float:
    remote_first = bool(controls.get("remote_first"))
    location_fit = location_alignment(
        candidate.get("location", ""),
        str(jd.get("location_preference", "Flexible")),
        remote_first=remote_first,
    )
    mode_fit = work_mode_alignment(
        candidate.get("work_mode_preference", ""),
        str(jd.get("work_mode", "flexible")),
        remote_first=remote_first,
    )
    return (location_fit + mode_fit) / 2


def build_jd_text(jd: dict[str, Any]) -> str:
    return scrub_protected_attributes(
        " ".join(
            [
                str(jd.get("role_title", "") or ""),
                " ".join(str(item or "") for item in jd.get("required_skills", [])),
                " ".join(str(item or "") for item in jd.get("nice_to_have_skills", [])),
                " ".join(str(item or "") for item in jd.get("responsibilities", [])),
                " ".join(str(item or "") for item in jd.get("search_keywords", [])),
            ]
        )
    )


def build_candidate_text(candidate: dict[str, Any]) -> str:
    return scrub_protected_attributes(
        " ".join(
            [
                str(candidate.get("current_title", "") or ""),
                " ".join(str(item or "") for item in candidate.get("skills", [])),
                " ".join(str(item or "") for item in candidate.get("nice_to_have_skills", [])),
                str(candidate.get("summary", "") or ""),
                str(candidate.get("domain_experience", "") or ""),
                str(candidate.get("resume_text", "") or ""),
            ]
        )
    )


def _keyword_overlap_similarity(left: str, right: str) -> float:
    left_tokens = {token for token in normalize_text(left).split() if token}
    right_tokens = {token for token in normalize_text(right).split() if token}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
