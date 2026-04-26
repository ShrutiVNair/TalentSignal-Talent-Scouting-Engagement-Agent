from __future__ import annotations

from src.services.deduplication_service import check_duplicate
from src.services.candidate_service import list_candidates
from tests.test_support import TalentSignalTestCase


class DeduplicationTests(TalentSignalTestCase):
    def test_duplicate_detection_catches_same_email(self) -> None:
        candidate = list_candidates()[0]
        clone = {**candidate, "id": "DUP-1", "email": candidate["email"]}
        result = check_duplicate(clone, candidate_pool=list_candidates())
        self.assertEqual(result["duplicate_risk"], "high")
        self.assertTrue(result["matched_candidate_ids"])

