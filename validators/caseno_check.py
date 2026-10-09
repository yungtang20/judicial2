"""Deterministic validation for the explicitly defined case-number formats."""

from __future__ import annotations

import re
from typing import TypedDict


class CheckResult(TypedDict, total=False):
    normalized: str
    kind: str
    status: str
    raw: str
    warning: str


_E_CASE_NUMBER = re.compile(r"Z[A-Za-z0-9]{9}")
_CASE_165_NUMBER = re.compile(r"\d{10}")
_WHITESPACE = re.compile(r"\s+")
_WARNING = "案號格式待確認"


def _unconfirmed(raw: str, normalized: str, kind: str, status: str) -> CheckResult:
    return {
        "normalized": normalized,
        "kind": kind,
        "status": status,
        "raw": raw,
        "warning": _WARNING,
    }


def check(raw: str) -> CheckResult:
    """Normalize whitespace and validate a supported case-number format."""
    if not isinstance(raw, str):
        raise TypeError("raw must be str")

    normalized = _WHITESPACE.sub("", raw)

    if _E_CASE_NUMBER.fullmatch(normalized):
        return {"normalized": normalized, "kind": "Z字e化案號", "status": "符合"}
    if _CASE_165_NUMBER.fullmatch(normalized):
        return {"normalized": normalized, "kind": "165案號", "status": "符合"}
    if "婦幼" in normalized:
        return _unconfirmed(raw, normalized, "婦幼案號", "UNKNOWN")
    if normalized.startswith("Z"):
        return _unconfirmed(raw, normalized, "Z字e化案號", "不符")
    if normalized.isdigit():
        return _unconfirmed(raw, normalized, "165案號", "不符")
    return _unconfirmed(raw, normalized, "未知", "UNKNOWN")
