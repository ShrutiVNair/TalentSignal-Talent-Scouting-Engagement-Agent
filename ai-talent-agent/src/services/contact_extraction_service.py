from __future__ import annotations

import re
from typing import Any

from src.resume_parser import extract_contact_info
from src.utils import COMMON_SKILLS, normalize_text, parse_years_experience, unique_list


GITHUB_PATTERN = re.compile(r"(https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+)", re.IGNORECASE)
PORTFOLIO_PATTERN = re.compile(r"(https?://(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?)", re.IGNORECASE)


def extract_candidate_profile(resume_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    contact = extract_contact_info(resume_text)
    github = _first_match(GITHUB_PATTERN, resume_text)
    portfolio = _portfolio_url(resume_text, github=github, linkedin=contact.get("linkedin"))
    skills = _extract_skills(resume_text)
    work_history = _extract_work_history(lines)
    certifications = _extract_certifications(lines)
    education = _extract_education(lines)
    full_name = _extract_name(lines, contact.get("email"))
    current_title, current_company = _current_role(work_history, lines)
    years_experience = parse_years_experience(resume_text) or _infer_years_from_history(resume_text)
    availability = _extract_availability(resume_text)
    compensation = _extract_compensation(resume_text)
    summary = _build_summary(current_title, current_company, skills, years_experience)

    confidence_scores = {
        "email_confidence": 0.98 if contact.get("email") else 0.0,
        "phone_confidence": 0.75 if contact.get("phone") else 0.0,
        "linkedin_confidence": 0.9 if contact.get("linkedin") else 0.0,
    }
    profile_parse_confidence = round(
        (
            confidence_scores["email_confidence"]
            + confidence_scores["phone_confidence"]
            + confidence_scores["linkedin_confidence"]
            + (0.8 if full_name else 0.0)
            + (0.75 if skills else 0.0)
        )
        / 5,
        2,
    )

    return {
        "name": full_name or "Needs review",
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "linkedin_url": contact.get("linkedin"),
        "github_url": github,
        "portfolio_url": portfolio,
        "location": _extract_location(lines),
        "current_company": current_company,
        "current_title": current_title,
        "years_experience": years_experience,
        "skills": skills,
        "education": education,
        "certifications": certifications,
        "work_history": work_history,
        "availability": availability,
        "compensation_expectation": compensation,
        "resume_text": resume_text,
        "summary": summary,
        "contact_source": "resume",
        "contact_consent_status": "unknown",
        "email_confidence": confidence_scores["email_confidence"],
        "phone_confidence": confidence_scores["phone_confidence"],
        "linkedin_confidence": confidence_scores["linkedin_confidence"],
        "profile_parse_confidence": profile_parse_confidence,
    }


def _extract_name(lines: list[str], email: str | None) -> str:
    for line in lines[:5]:
        if email and email.lower() in line.lower():
            continue
        if len(line.split()) in {2, 3, 4} and not any(char.isdigit() for char in line):
            return line.strip("|- ")
    return ""


def _extract_skills(text: str) -> list[str]:
    haystack = normalize_text(text)
    return unique_list([skill for skill in COMMON_SKILLS if normalize_text(skill) in haystack])


def _extract_work_history(lines: list[str]) -> list[str]:
    history = []
    for line in lines:
        if re.search(r"\b(19|20)\d{2}\b", line) and len(history) < 6:
            history.append(line)
    return history


def _extract_certifications(lines: list[str]) -> list[str]:
    return [line for line in lines if "cert" in line.lower()][:5]


def _extract_education(lines: list[str]) -> str:
    for line in lines:
        if any(token in line.lower() for token in ["b.tech", "bachelor", "master", "m.tech", "university", "college"]):
            return line
    return ""


def _current_role(work_history: list[str], lines: list[str]) -> tuple[str, str]:
    source = work_history[0] if work_history else next((line for line in lines if "|" in line), "")
    if " at " in source.lower():
        left, right = re.split(r"\bat\b", source, maxsplit=1, flags=re.IGNORECASE)
        return left.strip(" |-"), right.strip(" |-")
    if "|" in source:
        parts = [part.strip() for part in source.split("|") if part.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
    return source[:60], ""


def _extract_location(lines: list[str]) -> str:
    location_tokens = ["remote", "bangalore", "bengaluru", "new york", "seattle", "austin", "london", "pune", "hyderabad"]
    for line in lines[:10]:
        lowered = line.lower()
        if any(token in lowered for token in location_tokens):
            return line
    return ""


def _extract_availability(text: str) -> str:
    match = re.search(r"(immediate|notice period[:\s]+[^\n.]+|\d+\s*(?:days|weeks|months))", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_compensation(text: str) -> str:
    match = re.search(r"(\$[\d,]+(?:\s*-\s*\$?[\d,]+)?|₹[\d,]+(?:\s*-\s*₹?[\d,]+)?|\d+\s*(?:lpa|lakhs|k))", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _infer_years_from_history(text: str) -> int:
    years = re.findall(r"\b(20\d{2}|19\d{2})\b", text)
    if len(years) >= 2:
        span = max(map(int, years)) - min(map(int, years))
        return max(span, 0)
    return 0


def _build_summary(title: str, company: str, skills: list[str], years_experience: int) -> str:
    if not any([title, company, skills, years_experience]):
        return "Resume parsed and awaiting recruiter review."
    skills_text = ", ".join(skills[:5]) or "general engineering skills"
    company_text = f" at {company}" if company else ""
    return f"{title or 'Candidate'}{company_text} with {years_experience or 'unknown'} years of experience and strengths in {skills_text}."


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _portfolio_url(text: str, github: str | None, linkedin: str | None) -> str | None:
    for match in PORTFOLIO_PATTERN.findall(text):
        url = match.strip()
        if github and url == github:
            continue
        if linkedin and url == linkedin:
            continue
        if "linkedin.com" in url.lower() or "github.com" in url.lower():
            continue
        return url
    return None
