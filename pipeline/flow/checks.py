"""Mechanical checks shared by the v0.3 LLM-backed flow."""

from __future__ import annotations

import re
from typing import Any, Iterable


YES_NO_MARKERS = (
    "是否",
    "有沒有",
    "有無",
    "是不是",
    "對不對",
    "能不能",
    "可不可以",
    "會不會",
    "要不要",
)
GUIDING_MARKERS = (
    "難道",
    "對吧",
    "不是嗎",
    "沒錯吧",
    "你承認",
    "承認",
    "你應該",
    "你不可能",
    "你才是",
)
_ID_CARD_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z][12]\d{8}(?!\d)")
_MOBILE_RE = re.compile(r"(?<!\d)09\d{2}[- ]?\d{3}[- ]?\d{3}(?!\d)")


class MechanicalCheckError(ValueError):
    """Raised when an LLM output fails a deterministic check."""


def validate_required_fields(data: dict[str, Any], required: Iterable[str]) -> None:
    missing = [key for key in required if key not in data]
    if missing:
        raise MechanicalCheckError(f"缺少必要欄位：{missing}")


def validate_warning_chain(previous: list[Any], current: list[Any]) -> None:
    if current[: len(previous)] != previous:
        raise MechanicalCheckError("warning 未完整保留或已被改寫")


def validate_unique_unit_ids(units: dict[str, Any]) -> None:
    seen: set[str] = set()
    for group in units.values():
        if not isinstance(group, list):
            raise MechanicalCheckError("units 分組必須為陣列")
        for unit in group:
            if not isinstance(unit, dict) or not isinstance(unit.get("unit_id"), str):
                raise MechanicalCheckError("單元缺少 unit_id")
            unit_id = unit["unit_id"].strip()
            if not unit_id or unit_id in seen:
                raise MechanicalCheckError("unit_id 空白或重複")
            seen.add(unit_id)


def validate_questions(questions: Iterable[str]) -> None:
    for question in questions:
        if not isinstance(question, str):
            raise MechanicalCheckError("問句必須為字串")
        text = question.strip()
        if not text:
            raise MechanicalCheckError("問句不得為空")
        if any(marker in text for marker in GUIDING_MARKERS):
            raise MechanicalCheckError("問句含引導式用語")
        if any(marker in text for marker in YES_NO_MARKERS):
            raise MechanicalCheckError("問句含是非問法")
        if text.rstrip("？?。.！!").endswith("嗎"):
            raise MechanicalCheckError("問句含是非問法")
        if ";" in text or "；" in text:
            raise MechanicalCheckError("問句不符合 STE100 單一動作原則")


def validate_no_direct_identifiers(value: Any) -> None:
    text = _flatten_text(value)
    if _ID_CARD_RE.search(text) or _MOBILE_RE.search(text):
        raise MechanicalCheckError("輸出含可直接識別之證件號碼或電話")


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_text(item) for item in value)
    return value if isinstance(value, str) else ""
