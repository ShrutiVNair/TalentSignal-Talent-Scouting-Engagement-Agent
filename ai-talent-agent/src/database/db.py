from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from src.config import DEFAULT_DB_PATH, get_settings


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def resolve_db_path(database_url: str | None = None) -> Path:
    raw_url = (database_url or get_settings().database_url).strip()
    if raw_url.startswith("sqlite:///"):
        return Path(raw_url.removeprefix("sqlite:///")).resolve()
    parsed = urlparse(raw_url)
    if parsed.scheme == "sqlite":
        return Path(parsed.path or str(DEFAULT_DB_PATH)).resolve()
    return DEFAULT_DB_PATH.resolve()


def get_connection(database_url: str | None = None) -> sqlite3.Connection:
    db_path = resolve_db_path(database_url)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_cursor(database_url: str | None = None) -> Iterator[sqlite3.Cursor]:
    connection = get_connection(database_url)
    try:
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    finally:
        connection.close()


def fetch_all(query: str, params: tuple[Any, ...] = (), database_url: str | None = None) -> list[dict[str, Any]]:
    connection = get_connection(database_url)
    try:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def fetch_one(query: str, params: tuple[Any, ...] = (), database_url: str | None = None) -> dict[str, Any] | None:
    connection = get_connection(database_url)
    try:
        row = connection.execute(query, params).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def execute(query: str, params: tuple[Any, ...] = (), database_url: str | None = None) -> int:
    connection = get_connection(database_url)
    try:
        cursor = connection.execute(query, params)
        connection.commit()
        return int(cursor.lastrowid or 0)
    finally:
        connection.close()


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)

