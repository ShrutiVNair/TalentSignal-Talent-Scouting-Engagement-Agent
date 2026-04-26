from __future__ import annotations

import os

from src.agents.next_best_action import decide_next_best_action
from src.agents.ranking_agent import compute_scorecard, list_matches, save_match
from src.agents.role_calibration import calibrate_role
from src.jd_parser import parse_jd
from src.llm_client import LLMClient
from src.integrations.communication.email_adapter import send_email_safe
from src.services.candidate_service import get_candidate
from src.services.channel_selection_service import select_outreach_channel
from src.services.contact_validation_service import contact_readiness, validate_email
from src.services.role_service import create_role, get_role
from src.services.resume_ingestion_service import parse_resume_input, save_parsed_candidate
from tests.test_support import TalentSignalTestCase


RESUME_TEXT = """Priya Sharma
Senior Backend Engineer
Bangalore, India
priya.sharma@example.com
+91 98765 43210
https://www.linkedin.com/in/priyasharma
https://github.com/priyasharma

Experience
Senior Backend Engineer | Razorpay | 2021 - Present
Backend Engineer | Flipkart | 2018 - 2021

Skills
Python, FastAPI, Kafka, PostgreSQL, AWS
Notice period: 30 days
Expected compensation: ₹35 LPA
"""


class ResumeEmailWorkflowTests(TalentSignalTestCase):
    def test_resume_parsing_extracts_contact_fields(self) -> None:
        parsed = parse_resume_input(resume_text=RESUME_TEXT)
        preview = parsed["candidate_preview"]
        self.assertEqual(parsed["status"], "preview_ready")
        self.assertEqual(preview["email"], "priya.sharma@example.com")
        self.assertTrue(preview["phone"].endswith("43210"))
        self.assertIn("linkedin.com/in/priyasharma", preview["linkedin_url"])
        self.assertIn("Python", preview["skills"])

    def test_contact_validation_marks_valid_and_invalid_email(self) -> None:
        self.assertTrue(validate_email("valid@example.com")["valid"])
        self.assertFalse(validate_email("not-an-email")["valid"])

    def test_contact_readiness_prefers_email_when_valid(self) -> None:
        candidate = parse_resume_input(resume_text=RESUME_TEXT)["candidate_preview"]
        readiness = contact_readiness(candidate, {"outreach_allowed": True})
        self.assertEqual(readiness["preferred_channel"], "email")

    def test_channel_selection_blocks_when_compliance_blocked(self) -> None:
        candidate = parse_resume_input(resume_text=RESUME_TEXT)["candidate_preview"]
        readiness = contact_readiness(candidate, {"outreach_allowed": False, "reasons": ["Candidate opted out"]})
        result = select_outreach_channel(
            candidate,
            {"title": "Backend Engineer"},
            readiness,
            {"outreach_allowed": False, "reasons": ["Candidate opted out"]},
            {"duplicate_risk": "none"},
            {"twilio_ready": False},
            "Demo Simulation",
        )
        self.assertEqual(result["recommended_channel"], "blocked")

    def test_email_adapter_mock_send(self) -> None:
        os.environ["EMAIL_PROVIDER"] = "mock"
        result = send_email_safe({"id": "C001", "email": "candidate@example.com"}, {"title": "Role"}, "Hello", "Body", "mock")
        self.assertEqual(result["status"], "mock_sent")

    def test_email_adapter_blocks_production_when_disabled(self) -> None:
        os.environ["EMAIL_PROVIDER"] = "smtp"
        os.environ["PRODUCTION_OUTREACH_ENABLED"] = "false"
        result = send_email_safe(
            {
                "id": "C001",
                "email": "candidate@example.com",
                "email_valid": True,
                "email_compliance_passed": True,
                "recruiter_approved": True,
                "contact_consent_status": "explicit",
            },
            {"title": "Role"},
            "Hello",
            "Body",
            "production",
        )
        self.assertEqual(result["status"], "blocked")

    def test_resume_import_saves_candidate(self) -> None:
        preview = parse_resume_input(resume_text=RESUME_TEXT)["candidate_preview"]
        candidate_id = save_parsed_candidate(preview)
        saved = get_candidate(candidate_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["email"], "priya.sharma@example.com")

    def test_parsed_resume_candidate_can_be_scored(self) -> None:
        preview = parse_resume_input(resume_text=RESUME_TEXT)["candidate_preview"]
        candidate_id = save_parsed_candidate(preview)
        candidate = get_candidate(candidate_id)
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
        scorecard = compute_scorecard(
            candidate,
            role,
            {
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
            },
        )
        action = decide_next_best_action(scorecard, {"outreach_allowed": True, "reasons": []}, {"duplicate_risk": "none"}, "Shortlisted")
        save_match(candidate_id, role_id, scorecard, stage="Shortlisted", duplicate_status={"duplicate_risk": "none"}, compliance_status={"outreach_allowed": True}, next_best_action=action["action"])
        self.assertTrue(any(row["candidate_id"] == candidate_id for row in list_matches(role_id)))

    def test_approval_required_before_send(self) -> None:
        os.environ["EMAIL_PROVIDER"] = "smtp"
        os.environ["PRODUCTION_OUTREACH_ENABLED"] = "true"
        result = send_email_safe(
            {
                "id": "C001",
                "email": "candidate@example.com",
                "email_valid": True,
                "email_compliance_passed": True,
                "recruiter_approved": False,
                "contact_consent_status": "explicit",
            },
            {"title": "Role"},
            "Hello",
            "Body",
            "production",
        )
        self.assertEqual(result["status"], "blocked")
