"""Gate 3 suspect-question builder based on the handbook sections."""

from __future__ import annotations

from typing import Any


_QUESTION_SECTIONS = [
    {
        "section": "一、基本資料與關係",
        "questions": [
            "請說明你的基本資料、與本案相關人員的關係，以及彼此如何認識或聯絡。"
        ],
    },
    {
        "section": "二、事件經過",
        "questions": [
            "請從事情開始到結束，依時間順序說明何時、何地、哪些人在場，以及各自的言行和完整經過。"
        ],
    },
    {
        "section": "三、相關物品、內容或紀錄",
        "questions": [
            "請說明事件相關的物品、對話、影像或其他紀錄，包括來源、內容、保管方式及目前所在。"
        ],
    },
    {
        "section": "四、事後聯絡與態度",
        "questions": [
            "請說明事件後你與相關人員如何聯絡、談了哪些內容，以及你後續如何處理。"
        ],
    },
    {
        "section": "五、其他特殊情形",
        "questions": [
            "請說明當時另有哪些特殊情形會影響事情經過，以及你如何理解和處理那些情形。"
        ],
    },
    {
        "section": "六、補充",
        "questions": [
            "請補充前面尚未說明，但你認為與本案相關的其他情況。"
        ],
    },
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
                "questions": [
                    {
                        "section": section["section"],
                        "questions": list(section["questions"]),
                    }
                    for section in _QUESTION_SECTIONS
                ],
            }
        )
    return groups


def run(gate2_output: dict[str, Any]) -> dict[str, Any]:
    """Build one six-section question group per Gate 2 candidate."""
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
