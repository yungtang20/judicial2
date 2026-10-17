from __future__ import annotations

import sqlite3
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .security import protect_json, unprotect_json


class RevisionConflict(RuntimeError):
    pass


class CaseNotFound(KeyError):
    pass


class EphemeralCaseStore:
    """Single-case, process-memory store for the no-history browser workflow."""

    def __init__(self) -> None:
        self._cases: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def list_cases(self) -> list[dict[str, Any]]:
        return []

    def list_cases_meta(self) -> list[dict[str, Any]]:
        return []

    def get(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                raise CaseNotFound(case_id)
            return deepcopy(case)

    def create(self, case: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        created = deepcopy(case)
        created["revision"] = 1
        created["updated_at"] = now
        with self._lock:
            self._cases.clear()
            self._cases[created["case_id"]] = deepcopy(created)
        return created

    def save(self, case: dict[str, Any], expected_revision: int) -> dict[str, Any]:
        with self._lock:
            current = self._cases.get(case["case_id"])
            if current is None or current.get("revision") != expected_revision:
                raise RevisionConflict("案件已由其他操作更新，請重新載入")
            updated = deepcopy(case)
            updated["revision"] = expected_revision + 1
            updated["updated_at"] = datetime.now(UTC).isoformat()
            self._cases[updated["case_id"]] = deepcopy(updated)
            return updated


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

    def list_cases_meta(self) -> list[dict[str, Any]]:
        """案件清單＋是否已選罪章（供 UI 標示「未選罪章」）。不取問答內容。"""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id, revision, state, updated_at, payload FROM cases ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            damaged = False
            has_offenses = False
            try:
                payload = unprotect_json(row["payload"])
                selected = set(payload.get("selected_offenses", []))
                for interview in payload.get("interviews", {}).values():
                    selected.update(interview.get("selected_offenses", []))
                has_offenses = bool(selected)
            except Exception:
                # 密文損壞：不得靜默標記為「未選罪章」（誤導承辦人）；明確標記 damaged
                damaged = True
            result.append({
                "case_id": row["case_id"],
                "revision": row["revision"],
                "state": row["state"],
                "updated_at": row["updated_at"],
                "has_offenses": has_offenses,
                "damaged": damaged,
            })
        return result

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

