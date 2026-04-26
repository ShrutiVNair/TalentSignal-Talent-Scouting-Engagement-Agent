from __future__ import annotations

from src.agents.compliance_agent import run_compliance
from src.services.candidate_service import list_candidates
from src.services.compliance_service import upsert_compliance
from tests.test_support import TalentSignalTestCase


class ComplianceTests(TalentSignalTestCase):
    def test_compliance_blocks_opt_out_candidate(self) -> None:
        candidate = list_candidates()[0]
        upsert_compliance(candidate["id"], {"opt_out": True})
        result = run_compliance(candidate, {"jd_text": "", "title": "Backend Engineer"}, {"duplicate_risk": "none"})
        self.assertFalse(result["outreach_allowed"])

