from __future__ import annotations

from src.agents.next_best_action import decide_next_best_action
from tests.test_support import TalentSignalTestCase


class NextBestActionTests(TalentSignalTestCase):
    def test_blocked_candidate_returns_do_not_contact(self) -> None:
        result = decide_next_best_action(
            {"final_score": 90, "match_score": 90, "compensation_risk": "low"},
            {"outreach_allowed": False, "reasons": ["Candidate opted out"]},
            {"duplicate_risk": "none"},
            "Shortlisted",
        )
        self.assertEqual(result["action"], "Do not contact")

