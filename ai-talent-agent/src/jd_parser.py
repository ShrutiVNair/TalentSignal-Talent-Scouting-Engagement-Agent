from __future__ import annotations

import re
from typing import Any

from src.llm_client import LLMClient
from src.utils import (
    extract_domain_keywords,
    extract_known_skills,
    infer_location,
    infer_role_title,
    infer_seniority,
    infer_work_mode,
    parse_years_experience,
    safe_json_loads,
    unique_list,
)


PARSER_SYSTEM_PROMPT = """You are a recruiting intelligence agent.
Extract the job description into strict JSON with these keys:
role_title, required_skills, nice_to_have_skills, years_experience, seniority,
location_preference, work_mode, responsibilities, must_have_constraints, search_keywords.
Return JSON only. Lists must contain strings. years_experience must be an integer."""


def parse_jd(jd_text: str, llm_client: LLMClient) -> dict[str, Any]:
    llm_result = _parse_jd_with_llm(jd_text, llm_client)
    if llm_result:
        llm_result["parser_mode"] = f"LLM-assisted via {llm_result.pop('_provider', 'LLM')}"
        return llm_result
    fallback = _parse_jd_fallback(jd_text)
    fallback["parser_mode"] = "Deterministic fallback"
    return fallback


def _parse_jd_with_llm(jd_text: str, llm_client: LLMClient) -> dict[str, Any] | None:
    response = llm_client.complete(
        PARSER_SYSTEM_PROMPT,
        f"Job description:\n{jd_text}",
        temperature=0.1,
    )
    if not response:
        return None
    parsed = safe_json_loads(response.text)
    if not parsed:
        return None
    normalized = _normalize_parsed_jd(parsed, jd_text)
    normalized["_provider"] = f"{response.provider} / {response.model}"
    return normalized


def _parse_jd_fallback(jd_text: str) -> dict[str, Any]:
    required_section = _section_after_heading(jd_text, ["requirements", "must have"])
    nice_section = _section_after_heading(jd_text, ["nice to have", "preferred", "bonus"])
    responsibilities_section = _section_after_heading(jd_text, ["responsibilities", "what you'll do"])

    required_skills = extract_known_skills(required_section or jd_text)
    nice_skills = [skill for skill in extract_known_skills(nice_section or jd_text) if skill not in required_skills]
    responsibilities = _extract_bullets(responsibilities_section) or _extract_sentences(jd_text, limit=4)
    must_have_constraints = []

    years = parse_years_experience(jd_text)
    if years:
        must_have_constraints.append(f"{years}+ years experience")
    work_mode = infer_work_mode(jd_text)
    if work_mode != "flexible":
        must_have_constraints.append(f"{work_mode.title()} work mode")

    location = infer_location(jd_text)
    if location != "Flexible":
        must_have_constraints.append(f"Location preference: {location}")

    search_keywords = unique_list(
        [
            infer_role_title(jd_text),
            *required_skills,
            *nice_skills,
            *extract_domain_keywords(jd_text),
        ]
    )

    return {
        "role_title": infer_role_title(jd_text),
        "required_skills": required_skills,
        "nice_to_have_skills": nice_skills,
        "years_experience": years or 5,
        "seniority": infer_seniority(jd_text),
        "location_preference": location,
        "work_mode": work_mode,
        "responsibilities": responsibilities,
        "must_have_constraints": must_have_constraints,
        "search_keywords": search_keywords,
    }


def _normalize_parsed_jd(parsed: dict[str, Any], jd_text: str) -> dict[str, Any]:
    fallback = _parse_jd_fallback(jd_text)
    return {
        "role_title": parsed.get("role_title") or fallback["role_title"],
        "required_skills": unique_list(parsed.get("required_skills") or fallback["required_skills"]),
        "nice_to_have_skills": unique_list(parsed.get("nice_to_have_skills") or fallback["nice_to_have_skills"]),
        "years_experience": int(parsed.get("years_experience") or fallback["years_experience"]),
        "seniority": str(parsed.get("seniority") or fallback["seniority"]).lower(),
        "location_preference": parsed.get("location_preference") or fallback["location_preference"],
        "work_mode": str(parsed.get("work_mode") or fallback["work_mode"]).lower(),
        "responsibilities": unique_list(parsed.get("responsibilities") or fallback["responsibilities"]),
        "must_have_constraints": unique_list(parsed.get("must_have_constraints") or fallback["must_have_constraints"]),
        "search_keywords": unique_list(parsed.get("search_keywords") or fallback["search_keywords"]),
    }


def _section_after_heading(text: str, headings: list[str]) -> str:
    lines = text.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        normalized = line.strip().lower().rstrip(":")
        if any(heading in normalized for heading in headings):
            capture = True
            continue
        if capture and line.strip() and not line.startswith("-") and re.match(r"^[A-Za-z ].+:$", line.strip()):
            break
        if capture:
            collected.append(line)
    return "\n".join(collected).strip()


def _extract_bullets(section_text: str) -> list[str]:
    bullets = []
    for line in section_text.splitlines():
        clean = line.strip().lstrip("-").strip()
        if clean:
            bullets.append(clean)
    return bullets


def _extract_sentences(text: str, limit: int = 4) -> list[str]:
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in raw_sentences[:limit] if sentence.strip()]
