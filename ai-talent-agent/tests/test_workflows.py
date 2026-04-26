from __future__ import annotations

from src.agents.ranking_agent import update_match_stage
from src.database.db import fetch_all
from src.services.analytics_service import build_analytics_snapshot
from src.services.feedback_service import add_feedback, list_feedback
from src.services.outreach_service import create_sequence
from tests.test_support import TalentSignalTestCase


class WorkflowTests(TalentSignalTestCase):
    def test_outreach_sequence_generation_creates_steps(self) -> None:
        sequence = create_sequence("C001", 1, "Hello there")
        self.assertEqual(len(sequence["steps"]), 5)

    def test_feedback_persists(self) -> None:
        add_feedback("C001", 1, "good_match", "Looks promising")
        self.assertTrue(any(item["feedback_type"] == "good_match" for item in list_feedback(1)))

    def test_pipeline_stage_update_persists(self) -> None:
        from src.database.db import execute

        execute(
            """
            INSERT OR IGNORE INTO candidate_role_match (
                candidate_id, role_id, match_score, interest_score, risk_score, final_score,
                recommendation, next_best_action, stage, scorecard_json, duplicate_status_json,
                compliance_status_json, created_at, updated_at
            ) VALUES ('C001', 1, 80, 70, 20, 78, 'Strong Yes', 'Contact now', 'Shortlisted', '{}', '{}', '{}', '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')
            """
        )
        update_match_stage("C001", 1, "Interview")
        rows = fetch_all("SELECT stage FROM candidate_role_match WHERE candidate_id = 'C001' AND role_id = 1")
        self.assertEqual(rows[0]["stage"], "Interview")

    def test_analytics_returns_metrics(self) -> None:
        snapshot = build_analytics_snapshot()
        self.assertIn("total_candidates", snapshot)
        self.assertIn("pipeline_funnel", snapshot)
