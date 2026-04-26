from __future__ import annotations

import os

from src.agents.ranking_agent import get_match
from src.integrations.communication.email_adapter import send_email_safe
from src.services.batch_scoring_service import score_candidates_for_role
from src.services.compliance_service import get_compliance_record, upsert_compliance
from src.services.engagement_service import build_hr_decision_summary, capture_candidate_reply, list_reply_timeline
from src.services.scheduling_service import create_mock_meeting_recommendation
from tests.test_support import TalentSignalTestCase


class DemoEmailEngagementTests(TalentSignalTestCase):
    def setUp(self) -> None:
        score_candidates_for_role(1, candidate_ids=["C001"])
        upsert_compliance("C001", {"do_not_contact": 0, "opt_out": 0, "compliance_notes": ""})

    def test_email_test_send_goes_only_to_test_recipient(self) -> None:
        os.environ["EMAIL_PROVIDER"] = "smtp"
        os.environ["TEST_EMAIL_RECIPIENT"] = "test-inbox@example.com"
        result = send_email_safe(
            {"id": "C001", "email": "candidate@example.com"},
            {"title": "Role"},
            "Hello",
            "Body",
            "test",
        )
        self.assertEqual(result["actual_recipient"], "test-inbox@example.com")
        self.assertNotEqual(result["actual_recipient"], "candidate@example.com")

    def test_manual_reply_capture_persists(self) -> None:
        capture_candidate_reply("C001", 1, "Can you share more details about compensation?")
        timeline = list_reply_timeline("C001", 1)
        self.assertTrue(any("compensation" in item["reply_text"].lower() for item in timeline))

    def test_positive_reply_increases_interest_score(self) -> None:
        before = float(get_match("C001", 1)["interest_score"])
        capture_candidate_reply("C001", 1, "Sounds good, I am interested and available tomorrow. Let's schedule.")
        after = float(get_match("C001", 1)["interest_score"])
        self.assertGreater(after, before)

    def test_negative_reply_decreases_interest_and_blocks_when_explicit(self) -> None:
        before = float(get_match("C001", 1)["interest_score"])
        capture_candidate_reply("C001", 1, "Not interested, please remove me and do not contact.")
        after = float(get_match("C001", 1)["interest_score"])
        summary = build_hr_decision_summary("C001", 1)
        compliance = get_compliance_record("C001")
        self.assertLess(after, before)
        self.assertEqual(summary["recommended_next_step"], "Do not contact")
        self.assertTrue(compliance["do_not_contact"])
        self.assertTrue(compliance["opt_out"])

    def test_hr_summary_generated(self) -> None:
        capture_candidate_reply("C001", 1, "Happy to chat this week, please send details.")
        summary = build_hr_decision_summary("C001", 1)
        self.assertEqual(summary["status"], "ready")
        self.assertIn("recommended_next_step", summary)
        self.assertGreaterEqual(summary["reply_count"], 1)

    def test_mock_scheduled_interview_creation(self) -> None:
        result = create_mock_meeting_recommendation("C001", 1)
        self.assertEqual(result["status"], "recommended")
        self.assertGreater(result["interview_id"], 0)

    def test_email_services_do_not_require_twilio(self) -> None:
        os.environ.pop("TWILIO_SID", None)
        os.environ.pop("TWILIO_AUTH_TOKEN", None)
        os.environ["EMAIL_PROVIDER"] = "mock"
        result = send_email_safe({"id": "C001", "email": "candidate@example.com"}, {"title": "Role"}, "Hello", "Body", "mock")
        self.assertEqual(result["status"], "mock_sent")
