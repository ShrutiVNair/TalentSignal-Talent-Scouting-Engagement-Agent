from __future__ import annotations

from typing import Any

from src.services.audit_service import log_audit
from src.services.candidate_service import search_candidates, upsert_candidate
from src.services.deduplication_service import check_duplicate
from src.database.db import fetch_all


class MockATSAdapter:
    provider_name = "mock"

    def search_candidate(self, email: str | None = None, phone: str | None = None, linkedin_url: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        query = email or phone or linkedin_url or name or ""
        return search_candidates(query) if query else []

    def get_candidate_history(self, candidate_id: str) -> list[dict[str, Any]]:
        return fetch_all(
            "SELECT role_id, stage, recommendation, updated_at, hiring_manager_status FROM candidate_role_match WHERE candidate_id = ? ORDER BY updated_at DESC",
            (candidate_id,),
        )

    def create_or_update_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        upsert_candidate(candidate, source="mock_ats")
        log_audit("candidate", candidate["id"], "ats_sync", {"provider": self.provider_name})
        return {"status": "upserted", "provider": self.provider_name}

    def update_candidate_stage(self, candidate_id: str, role_id: int, stage: str) -> dict[str, Any]:
        from src.agents.ranking_agent import update_match_stage

        update_match_stage(candidate_id, role_id, stage)
        return {"status": "updated", "stage": stage}

    def add_note(self, candidate_id: str, note: str) -> dict[str, Any]:
        log_audit("candidate", candidate_id, "ats_note_added", {"note": note, "provider": self.provider_name})
        return {"status": "noted"}

    def check_duplicate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        result = check_duplicate(candidate)
        history = self.get_candidate_history(candidate["id"]) if candidate.get("id") else []
        return {**result, "history": history}

