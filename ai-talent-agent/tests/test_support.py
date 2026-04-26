from __future__ import annotations

import os
import tempfile
import unittest


class TalentSignalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/test.db"
        from src.database.models import ensure_database
        from src.database.seed import seed_all
        from src.jd_parser import parse_jd
        from src.llm_client import LLMClient
        from src.agents.role_calibration import calibrate_role
        from src.services.role_service import create_role

        ensure_database()
        seed_all()
        parsed = parse_jd("Senior Backend Engineer remote Python FastAPI PostgreSQL AWS 5+ years", LLMClient())
        calibration = calibrate_role(parsed, {"location": "Remote - US", "work_mode": "remote", "salary_min": 150000, "salary_max": 190000, "interview_process": "screen"})
        create_role(
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

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()
