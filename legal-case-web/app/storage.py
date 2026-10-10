from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .security import protect_json, unprotect_json


class RevisionConflict(RuntimeError):
    pass


class CaseNotFound(KeyError):
    pass


class CaseStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload BLOB NOT NULL
                )
                """
            )

    def list_cases(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id, revision, state, updated_at FROM cases ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, case_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
        if row is None:
            raise CaseNotFound(case_id)
        return unprotect_json(row["payload"])

    def create(self, case: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        case["revision"] = 1
        case["updated_at"] = now
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO cases(case_id, revision, state, updated_at, payload) VALUES (?, ?, ?, ?, ?)",
                (case["case_id"], 1, case["state"], now, protect_json(case)),
            )
        return case

    def save(self, case: dict[str, Any], expected_revision: int) -> dict[str, Any]:
        next_revision = expected_revision + 1
        now = datetime.now(UTC).isoformat()
        case["revision"] = next_revision
        case["updated_at"] = now
        encrypted = protect_json(case)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE cases SET revision = ?, state = ?, updated_at = ?, payload = ?
                WHERE case_id = ? AND revision = ?
                """,
                (next_revision, case["state"], now, encrypted, case["case_id"], expected_revision),
            )
            if cursor.rowcount != 1:
                raise RevisionConflict("案件已由其他操作更新，請重新載入")
        return case

