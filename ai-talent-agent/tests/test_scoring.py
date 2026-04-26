from __future__ import annotations

from src.agents.next_best_action import decide_next_best_action
from src.agents.ranking_agent import compute_scorecard, list_matches, save_match
from src.agents.role_calibration import calibrate_role
from src.jd_parser import parse_jd
from src.llm_client import LLMClient
from src.services.candidate_service import list_candidates
from src.services.role_service import create_role, get_role
from tests.test_support import TalentSignalTestCase


class ScoringTests(TalentSignalTestCase):
    def test_scoring_returns_expected_range_and_persists(self) -> None:
        parsed = parse_jd("Senior Backend Engineer remote Python FastAPI PostgreSQL AWS 5+ years", LLMClient())
        calibration = calibrate_role(parsed, {"location": "Remote - US", "work_mode": "remote", "salary_min": 150000, "salary_max": 190000, "interview_process": "screen"})
        role_id = create_role(
            {
                "title": parsed["role_title"],
                "department": "Engineering",
                "hiring_manager": "Manager",
                "location": "Remote - US",
                "work_mode": "remote",
                "salary_min": 150000,
                "salary_max": 190000,
                "required_skills": calibration["must_have_skills"],
                "nice_to_have_skills": calibration["nice_to_have_skills"],
                "experience_min": 5,
                "experience_max": 10,
                "jd_text": "sample",
                "scoring_weights": {},
            },
            calibration=calibration,
        )
        role = get_role(role_id)
        candidate = list_candidates()[0]
        scorecard = compute_scorecard(candidate, role, {
            "role_title": role["title"],
            "required_skills": role["required_skills"],
            "nice_to_have_skills": role["nice_to_have_skills"],
            "years_experience": role["experience_min"],
            "seniority": "senior",
            "location_preference": role["location"],
            "work_mode": role["work_mode"],
            "responsibilities": [],
            "must_have_constraints": [],
            "search_keywords": role["required_skills"],
        })
        self.assertGreaterEqual(scorecard["final_score"], 0)
        self.assertLessEqual(scorecard["final_score"], 100)
        next_action = decide_next_best_action(scorecard, {"outreach_allowed": True, "reasons": []}, {"duplicate_risk": "none"}, "Shortlisted")
        save_match(candidate["id"], role_id, scorecard, stage="Shortlisted", duplicate_status={"duplicate_risk": "none"}, compliance_status={"outreach_allowed": True}, next_best_action=next_action["action"])
        rows = list_matches(role_id)
        self.assertTrue(any(row["candidate_id"] == candidate["id"] for row in rows))

