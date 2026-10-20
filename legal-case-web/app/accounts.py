from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from pathlib import Path
from threading import RLock


_PASSWORD_ITERATIONS = 310_000
_DUMMY_SALT = bytes.fromhex("a95c22d11b7342878f7400cab30e5ea4")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class AccountStore:
    """Single-owner account store; persists credentials, never case content."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    username TEXT NOT NULL UNIQUE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL
                )"""
            )
        self.path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    def has_account(self) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM account WHERE id = 1").fetchone() is not None

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS)

    def register(self, username: str, password: str, invite_code: str, expected_invite: str) -> bool:
        username = username.strip()
        if not _USERNAME_RE.fullmatch(username):
            return False
        if len(password) < 14 or len(password) > 256:
            return False
        if len(expected_invite) < 32 or not hmac.compare_digest(invite_code, expected_invite):
            return False
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password, salt)
        with self._lock, self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO account (id, username, salt, password_hash) VALUES (1, ?, ?, ?)",
                    (username, salt, password_hash),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def authenticate(self, username: str, password: str) -> bool:
        username = username.strip()
        if len(password) > 256:
            self._password_hash(password[:256], _DUMMY_SALT)
            return False
        with self._connect() as db:
            row = db.execute(
                "SELECT username, salt, password_hash FROM account WHERE id = 1"
            ).fetchone()
        if row is None:
            self._password_hash(password, _DUMMY_SALT)
            return False
        stored_username, salt, password_hash = row
        candidate = self._password_hash(password, salt)
        return hmac.compare_digest(username, stored_username) and hmac.compare_digest(candidate, password_hash)
