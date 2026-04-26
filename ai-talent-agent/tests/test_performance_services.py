from __future__ import annotations

from src.services.batch_scoring_service import (
    get_top_matches,
    invalidate_scores_for_role,
    score_candidates_for_role,
)
from src.services.candidate_service import list_candidates_page
from src.services.role_service import list_roles
from src.services.talent_scan_service import run_talent_scan
from tests.test_support import TalentSignalTestCase


class PerformanceServiceTests(TalentSignalTestCase):
    def test_candidate_pagination_returns_small_pages(self) -> None:
        page_one = list_candidates_page(page=1, page_size=5)
        page_two = list_candidates_page(page=2, page_size=5)
        self.assertLessEqual(len(page_one["items"]), 5)
        self.assertEqual(page_one["page_size"], 5)
        self.assertGreaterEqual(page_one["total"], len(page_one["items"]))
        if page_one["total"] > 5 and page_two["items"]:
            self.assertNotEqual(page_one["items"][0]["id"], page_two["items"][0]["id"])

    def test_batch_scoring_persists_top_matches(self) -> None:
        role = list_roles()[0]
        candidate_page = list_candidates_page(page=1, page_size=10)
        candidate_ids = [row["id"] for row in candidate_page["items"]]
        summary = score_candidates_for_role(role["id"], candidate_ids=candidate_ids, batch_size=5)
        top = get_top_matches(role["id"], limit=5)
        self.assertEqual(summary["scored_count"], len(candidate_ids))
        self.assertTrue(top)
        self.assertIn("scorecard", top[0])

    def test_cached_scores_invalidate_cleanly(self) -> None:
        role = list_roles()[0]
        candidate_page = list_candidates_page(page=1, page_size=8)
        candidate_ids = [row["id"] for row in candidate_page["items"]]
        score_candidates_for_role(role["id"], candidate_ids=candidate_ids, batch_size=4)
        get_top_matches.cache_clear()
        get_top_matches(role["id"], limit=5)
        get_top_matches(role["id"], limit=5)
        self.assertGreaterEqual(get_top_matches.cache_info().hits, 1)
        invalidate_scores_for_role(role["id"])
        self.assertEqual(get_top_matches.cache_info().currsize, 0)

    def test_talent_scan_returns_summary(self) -> None:
        role = list_roles()[0]
        candidate_page = list_candidates_page(page=1, page_size=12)
        expected = len(candidate_page["items"])
        summary = run_talent_scan(
            role["id"],
            {
                "max_candidates": expected,
                "batch_size": 5,
                "score_threshold": 0,
                "generate_outreach_for_top_n": 2,
                "skip_duplicates": False,
                "skip_compliance_blocked": False,
                "automation_mode": "review_first",
            },
        )
        self.assertEqual(summary["processed_count"], expected)
        self.assertEqual(summary["scored_count"], expected)
        self.assertIn("top_candidates", summary)
        self.assertLessEqual(len(summary["top_candidates"]), 10)
