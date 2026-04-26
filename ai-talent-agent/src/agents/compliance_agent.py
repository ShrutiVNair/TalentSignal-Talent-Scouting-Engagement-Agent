from __future__ import annotations

from typing import Any

from src.services.compliance_service import evaluate_compliance


def run_compliance(candidate: dict[str, Any], role: dict[str, Any], duplicate_result: dict[str, Any], active_other_process: bool = False, recent_rejection: bool = False) -> dict[str, Any]:
    return evaluate_compliance(candidate, role, duplicate_result, active_other_process=active_other_process, recent_rejection=recent_rejection)

