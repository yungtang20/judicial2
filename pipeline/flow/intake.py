"""Deterministic validation for page-one intake data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = PROJECT_ROOT / "templates"
NOT_APPLICABLE = "NOT_APPLICABLE"

REQUIRED_FIELDS = ("station", "document_type", "event_time", "location", "summary")
OPTIONAL_FIELDS = ("reception_type", "report_stage")
ALLOWED_FIELDS = frozenset((*REQUIRED_FIELDS, *OPTIONAL_FIELDS))
RECEPTION_TYPES = frozenset(
    {
        "受理",
        "告訴",
        "告發",
        "報案",
        "備案",
        "通報",
        "申訴",
        "函送",
        "移送",
        "查獲",
        "保護令",
        "受理（依案號推定）",
        "其他",
    }
)
REPORT_STAGES = frozenset({"初報", "續報", "結報", "更正", "單一報告"})
DOCUMENT_TYPES = frozenset({"受理報告", "告發報告", NOT_APPLICABLE})
DOCUMENT_TYPE_BY_RECEPTION = {
    "受理": "受理報告",
    "告訴": "受理報告",
    "受理（依案號推定）": "受理報告",
    "告發": "告發報告",
}

_DATETIME_RE = re.compile(
    r"(?:民國\s*)?\d{2,4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"
    r"(?:\s*\d{1,2}\s*時(?:\s*\d{1,2}\s*分)?)?"
    r"|\d{4}-\d{1,2}-\d{1,2}(?:[ T]\d{1,2}:\d{2})?"
)


class IntakeError(ValueError):
    """Raised when page-one input is incomplete or inconsistent."""


@dataclass(frozen=True)
class IntakeResult:
    fields: dict[str, str]
    original_summary: str
    warnings: list[str] = field(default_factory=list)


def discover_template_pairs(root: Path = TEMPLATE_ROOT) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    if not root.exists():
        return pairs
    for path in root.glob("**/*.json"):
        try:
            template = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        station = template.get("station")
        document_type = template.get("document_type")
        if isinstance(station, str) and isinstance(document_type, str):
            pairs.add((station, document_type))
    return pairs


def _digits(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def _is_prefix(short: tuple[int, ...], long: tuple[int, ...]) -> bool:
    return len(short) <= len(long) and long[: len(short)] == short


def validate_intake(
    raw: dict[str, Any],
    *,
    available_templates: set[tuple[str, str]] | None = None,
) -> IntakeResult:
    if not isinstance(raw, dict):
        raise TypeError("頁 1 輸入必須為物件")
    unknown = set(raw) - ALLOWED_FIELDS
    if unknown:
        raise IntakeError(f"不支援的欄位：{sorted(unknown)}")

    labels = {
        "station": "所別",
        "document_type": "文件類型",
        "event_time": "發生時間",
        "location": "發生地點",
        "summary": "案情摘要",
    }
    fields: dict[str, str] = {}
    missing: list[str] = []
    for key in REQUIRED_FIELDS:
        value = str(raw.get(key, "") or "").strip()
        fields[key] = value
        if not value:
            missing.append(labels[key])
    if missing:
        raise IntakeError(f"缺少必填欄位：{'、'.join(missing)}")

    reception_type = str(raw.get("reception_type", "") or "").strip()
    if reception_type and reception_type not in RECEPTION_TYPES:
        raise IntakeError("受理性質不在允許值域")
    fields["reception_type"] = reception_type

    document_type = fields["document_type"]
    if document_type not in DOCUMENT_TYPES:
        raise IntakeError("文件類型不在允許值域")
    expected_document = DOCUMENT_TYPE_BY_RECEPTION.get(reception_type)
    if reception_type and document_type != (expected_document or NOT_APPLICABLE):
        raise IntakeError("文件類型與受理性質不一致")
    if document_type != NOT_APPLICABLE:
        templates = available_templates if available_templates is not None else discover_template_pairs()
        if (fields["station"], document_type) not in templates:
            raise IntakeError("模板未提供")

    report_stage = str(raw.get("report_stage", "單一報告") or "").strip()
    if report_stage not in REPORT_STAGES:
        raise IntakeError("報告階段不在允許值域")
    fields["report_stage"] = report_stage

    summary = fields["summary"]
    warnings: list[str] = []
    if fields["event_time"] in summary or fields["location"] in summary:
        warnings.append("摘要含重複之時間或地點")

    event_digits = _digits(fields["event_time"])
    for match in _DATETIME_RE.finditer(summary):
        found = _digits(match.group(0))
        if found and not (
            _is_prefix(found, event_digits) or _is_prefix(event_digits, found)
        ):
            warnings.append("摘要日期與發生時間不一致，已保留原文，請人工確認")
            break

    return IntakeResult(fields=fields, original_summary=summary, warnings=warnings)
