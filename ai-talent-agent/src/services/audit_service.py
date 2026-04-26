from __future__ import annotations

from typing import Any

from src.database.db import execute, json_dumps, utc_now


def log_audit(entity_type: str, entity_id: str | int, action: str, details: dict[str, Any] | None = None) -> None:
    execute(
        """
        INSERT INTO audit_log (entity_type, entity_id, action, details_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_type, str(entity_id), action, json_dumps(details or {}), utc_now()),
    )


def list_audit_logs(entity_type: str | None = None, entity_id: str | int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM audit_log"
    params: list[Any] = []
    clauses: list[str] = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(str(entity_id))
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    from src.database.db import fetch_all

    return fetch_all(query, tuple(params))

