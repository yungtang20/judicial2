"""Minimal Gate 3 question skeleton builder."""

from __future__ import annotations

from typing import Any


_QUESTION_SKELETONS = [
    "請說明與本案相關的事件經過",
    "請說明你與案件中其他人的關係",
    "請說明相關時間、地點及你當時所做的事情",
]
_MISSING_TEMPLATE_WARNING = "破獲條陳模板未提供"


def _question_groups(gate2_output: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = gate2_output.get("candidates")
    if not isinstance(candidates, list):
        return []

    groups: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        groups.append(
            {
                "article_no": candidate.get("article_no"),
                "source_span": candidate.get("source_span"),
                "offense": candidate.get("offense", "UNKNOWN"),
                "candidate_status": candidate.get("candidate_status", "NEED_REVIEW"),
                "questions": list(_QUESTION_SKELETONS),
            }
        )
    return groups


def run(gate2_output: dict[str, Any]) -> dict[str, Any]:
    """Build one fixed question group per Gate 2 candidate."""
    warnings = list(gate2_output.get("warnings", []))
    if gate2_output.get("candidates") and _MISSING_TEMPLATE_WARNING not in warnings:
        warnings.append(_MISSING_TEMPLATE_WARNING)
    result = {
        "suspect_questions": _question_groups(gate2_output),
        "internal_mapping": [],
        "apprehension_report": {
            "status": "模板未提供" if gate2_output.get("candidates") else "未產出",
            "candidate_count": len(gate2_output.get("candidates", []))
            if isinstance(gate2_output.get("candidates"), list) else 0,
            "route": gate2_output.get("route", "UNKNOWN"),
            "candidate_articles": [
                item.get("article_no") for item in gate2_output.get("candidates", [])
                if isinstance(item, dict)
            ],
        },
        "warnings": warnings,
    }
    if gate2_output.get("status") == "未進入 Gate 2":
        return {"status": "未進入 Gate 3", **result}
    return {"status": "已進入 Gate 3", **result}
