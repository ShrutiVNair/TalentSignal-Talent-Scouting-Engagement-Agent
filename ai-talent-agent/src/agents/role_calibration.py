from __future__ import annotations

from typing import Any

from src.utils import parse_money, unique_list


def calibrate_role(parsed_jd: dict[str, Any], role_fields: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    suggestions: list[str] = []
    required = unique_list(parsed_jd.get("required_skills", []))
    nice = [skill for skill in unique_list(parsed_jd.get("nice_to_have_skills", [])) if skill not in required]
    salary_min = int(role_fields.get("salary_min") or 0)
    salary_max = int(role_fields.get("salary_max") or 0)

    if parsed_jd.get("seniority") in {"mid", ""} and "senior" not in (parsed_jd.get("role_title") or "").lower():
        issues.append("Seniority is not explicit.")
        suggestions.append("Clarify level such as Senior, Staff, or Principal.")
    if len(required) > 8:
        issues.append("Too many must-have skills listed.")
        suggestions.append("Move some technologies into nice-to-have skills.")
    if not salary_min or not salary_max:
        issues.append("Salary range is missing.")
        suggestions.append("Add a salary band for better calibration and compensation risk detection.")
    if not role_fields.get("location") or not role_fields.get("work_mode"):
        issues.append("Location or work mode is missing.")
        suggestions.append("Specify location and remote/hybrid expectations.")
    if int(parsed_jd.get("years_experience", 0)) >= 12 and parsed_jd.get("seniority") in {"junior", "mid"}:
        issues.append("Experience requirement appears unrealistic for the stated level.")
    if salary_max and parsed_jd.get("seniority") == "principal" and salary_max < 180000:
        issues.append("Salary may contradict the seniority level.")
    if not role_fields.get("interview_process"):
        issues.append("Interview process information is missing.")
    if required and nice and set(required) & set(nice):
        issues.append("Required skills and nice-to-have skills overlap.")
        nice = [skill for skill in nice if skill not in required]

    jd_quality_score = max(20, 100 - len(issues) * 10)
    cleaned = {
        "must_have_skills": required,
        "nice_to_have_skills": nice,
        "cleaned_role_requirements": {
            "required_skills": required,
            "nice_to_have_skills": nice,
            "experience_min": parsed_jd.get("years_experience", 0),
            "work_mode": role_fields.get("work_mode") or parsed_jd.get("work_mode"),
            "location": role_fields.get("location") or parsed_jd.get("location_preference"),
            "salary_min": salary_min,
            "salary_max": salary_max,
        },
    }
    return {
        "jd_quality_score": jd_quality_score,
        "detected_issues": issues,
        "suggested_improvements": suggestions,
        **cleaned,
    }

