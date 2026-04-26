from __future__ import annotations

import json
import hashlib
import math
import re
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

COMMON_SKILLS = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "PostgreSQL",
    "AWS",
    "Distributed Systems",
    "Kafka",
    "Terraform",
    "Kubernetes",
    "Docker",
    "Redis",
    "CI/CD",
    "Microservices",
    "System Design",
    "GraphQL",
    "Airflow",
    "Observability",
    "REST APIs",
    "SRE",
]

DOMAIN_KEYWORDS = [
    "saas",
    "fintech",
    "healthtech",
    "payments",
    "cloud",
    "infrastructure",
    "developer tools",
    "e-commerce",
    "marketplace",
    "logistics",
    "travel",
    "adtech",
    "edtech",
    "data",
    "ai",
    "cybersecurity",
    "media",
    "insurance",
    "manufacturing",
    "retail",
]

PROTECTED_ATTRIBUTE_TOKENS = [
    "gender",
    "male",
    "female",
    "age",
    "race",
    "religion",
    "disability",
    "marital",
    "pregnancy",
    "nationality",
    "health",
    "political",
]

SENIORITY_ORDER = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
    "principal": 5,
    "lead": 4,
    "manager": 4,
}


def load_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def scrub_protected_attributes(text: str) -> str:
    cleaned = text or ""
    for token in PROTECTED_ATTRIBUTE_TOKENS:
        cleaned = re.sub(rf"\b{re.escape(token)}\b", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def slugify_skill(skill: str) -> str:
    normalized = normalize_text(skill)
    return normalized.replace(" and ", " ").replace("/", " ").replace("-", " ")


def tokenize_skills(values: Iterable[str]) -> list[str]:
    return unique_list([slugify_skill(value) for value in values if value])


def build_searchable_text(*parts: Any) -> str:
    flattened: list[str] = []
    for part in parts:
        if isinstance(part, list):
            flattened.extend(str(item or "") for item in part)
        else:
            flattened.append(str(part or ""))
    return normalize_text(" ".join(flattened))


def hash_payload(*parts: Any) -> str:
    text = build_searchable_text(*parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def unique_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = normalize_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def extract_known_skills(text: str) -> list[str]:
    haystack = normalize_text(text)
    found = [skill for skill in COMMON_SKILLS if normalize_text(skill) in haystack]
    return unique_list(found)


def infer_seniority(text: str) -> str:
    haystack = normalize_text(text)
    for label in ["principal", "staff", "lead", "senior", "mid", "junior"]:
        if label in haystack:
            return label
    return "mid"


def seniority_value(value: str) -> int:
    return SENIORITY_ORDER.get(normalize_text(value), 2)


def infer_role_title(jd_text: str) -> str:
    first_line = jd_text.strip().splitlines()[0].strip()
    if first_line:
        return first_line.replace("—", "-").split("-")[0].strip()
    return "Target Role"


def parse_years_experience(text: str) -> int:
    match = re.search(r"(\d+)\s*\+?\s*years", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def parse_money(value: str) -> int:
    match = re.search(r"(\d[\d,]*)", value or "")
    return int(match.group(1).replace(",", "")) if match else 0


def availability_to_days(value: str) -> int:
    normalized = normalize_text(value)
    numeric_match = re.search(r"(\d+)", normalized)
    amount = int(numeric_match.group(1)) if numeric_match else 3
    if "immediate" in normalized:
        return 0
    if "week" in normalized:
        return amount * 7
    if "month" in normalized:
        return amount * 30
    return 21


def infer_work_mode(text: str) -> str:
    haystack = normalize_text(text)
    if "remote" in haystack:
        return "remote"
    if "hybrid" in haystack:
        return "hybrid"
    if "onsite" in haystack or "on-site" in haystack:
        return "onsite"
    return "flexible"


def infer_location(text: str) -> str:
    location_match = re.search(
        r"(\bunited states\b|\bu\.s\.\b|\bus\b|\bcanada\b|new york|remote - us|remote - canada|austin, tx|seattle, wa)",
        text,
        flags=re.IGNORECASE,
    )
    if location_match:
        return location_match.group(1)
    return "Flexible"


def extract_domain_keywords(text: str) -> list[str]:
    haystack = normalize_text(text)
    return [keyword for keyword in DOMAIN_KEYWORDS if keyword in haystack]


def profile_completeness(candidate: dict[str, Any]) -> float:
    required_fields = [
        "name",
        "current_title",
        "years_experience",
        "location",
        "work_mode_preference",
        "skills",
        "summary",
        "domain_experience",
        "availability",
        "compensation_expectation",
        "engagement_persona",
        "resume_text",
        "linkedin_url",
        "github_url",
    ]
    completed = 0
    for field in required_fields:
        value = candidate.get(field)
        if isinstance(value, list):
            completed += int(bool(value))
        else:
            completed += int(value not in (None, "", []))
    return completed / len(required_fields)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def location_alignment(candidate_location: str, target_location: str, remote_first: bool = False) -> float:
    candidate_norm = normalize_text(candidate_location)
    target_norm = normalize_text(target_location)
    if target_norm in {"flexible", "", "remote"}:
        return 1.0 if remote_first or "remote" in candidate_norm else 0.8
    if target_norm in candidate_norm:
        return 1.0
    if remote_first and "remote" in candidate_norm:
        return 0.9
    if "united states" in target_norm and ("remote - us" in candidate_norm or ", " in candidate_location):
        return 0.9
    if "canada" in target_norm and "canada" in candidate_norm:
        return 1.0
    return 0.35 if "remote" in candidate_norm else 0.1


def work_mode_alignment(candidate_mode: str, jd_mode: str, remote_first: bool = False) -> float:
    candidate_norm = normalize_text(candidate_mode)
    jd_norm = normalize_text(jd_mode)
    if remote_first and candidate_norm == "remote":
        return 1.0
    if jd_norm in {"flexible", ""}:
        return 1.0
    if jd_norm == candidate_norm:
        return 1.0
    if jd_norm == "remote" and candidate_norm == "hybrid":
        return 0.6
    if jd_norm == "hybrid" and candidate_norm == "remote":
        return 0.75
    return 0.2


def compensation_band_for_jd(jd: dict[str, Any]) -> tuple[int, int]:
    seniority = infer_seniority(f"{jd.get('seniority', '')} {jd.get('role_title', '')}")
    base_by_seniority = {
        "junior": (90000, 120000),
        "mid": (120000, 150000),
        "senior": (150000, 185000),
        "staff": (180000, 230000),
        "principal": (210000, 280000),
        "lead": (180000, 225000),
    }
    return base_by_seniority.get(seniority, (120000, 160000))


def compensation_alignment(candidate_comp: str, jd: dict[str, Any]) -> float:
    low, high = compensation_band_for_jd(jd)
    expected = parse_money(candidate_comp)
    if expected == 0:
        return 0.6
    if low <= expected <= high:
        return 1.0
    distance = min(abs(expected - low), abs(expected - high))
    return clamp(1.0 - distance / 120000)


def top_strength(strengths: list[str]) -> str:
    return strengths[0] if strengths else "Balanced profile"


def main_risk(risks: list[str]) -> str:
    return risks[0] if risks else "No major risk flags"


def round_score(value: float) -> float:
    return round(value, 1)


def safe_json_loads(raw_text: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def cosine_to_percentage(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return round_score(clamp(value) * 100)
