from __future__ import annotations

from src.config import get_settings


class LeverAdapter:
    provider_name = "lever"

    def __init__(self) -> None:
        self.api_key = get_settings().lever_api_key

    def _placeholder(self) -> dict[str, str]:
        return {
            "status": "not_configured" if not self.api_key else "placeholder",
            "detail": "Lever adapter scaffold is ready; plug in live endpoints only when credentials are supplied.",
        }

    def search_candidate(self, **_: object) -> list[dict[str, str]]:
        return [self._placeholder()]

    def get_candidate_history(self, candidate_id: str) -> list[dict[str, str]]:
        return [{**self._placeholder(), "candidate_id": candidate_id}]

    def create_or_update_candidate(self, candidate: dict[str, object]) -> dict[str, str]:
        return {**self._placeholder(), "candidate_id": str(candidate.get("id", ""))}

    def update_candidate_stage(self, candidate_id: str, role_id: int, stage: str) -> dict[str, str | int]:
        return {**self._placeholder(), "candidate_id": candidate_id, "role_id": role_id, "stage": stage}

    def add_note(self, candidate_id: str, note: str) -> dict[str, str]:
        return {**self._placeholder(), "candidate_id": candidate_id, "note": note}

    def check_duplicate(self, candidate: dict[str, object]) -> dict[str, str]:
        return {**self._placeholder(), "candidate_id": str(candidate.get("id", ""))}

