"""新套表.xlsm 被害人／涉嫌人／證人通用問句（公司既有罪章題）。

來源：../新套表.xlsm 的「被害人筆錄」「涉嫌人筆錄」「證人筆錄」工作表。
- 欄 A 為通用必問題（對應 company_templates.py 已逐字保留的三份 .doc 題目）。
- 欄 B 起為各罪章專屬題（公司已核定之筆錄套表題）。
- 公式題（CONCATENATE 組合案號、日期等）為樣板插值；靜態文字部分照錄，
  插值處以全形空白佔位，由承辦人在筆錄上補實際資料。
- 含個案判決意旨長段（如北市警刑偵字第1133115422號）保留原文，屬公司核定文字。

載入規則（questions/company-standard.md 第二節）：
- 公司套表罪章題 kind=company_offense，優先於本庫 md 題；語意相同時本庫題不重複。
- 證人題目前僅在角色=witness 時載入（本系統證人筆錄為後續擴充）。
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

XLSM_JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "xlsm_questions.json"

# xlsm 罪章欄名 → 本系統罪章 id（與 question_bank.json 對應）
OFFENSE_NAME_TO_ID: dict[str, str] = {
    "過失傷害": "negligent_injury",
    "傷害": "injury",
    "竊盜": "theft",
    "侵占": "embezzlement",
    "毀損": "damage",
    "妨害電腦使用": "computer",
    "妨害名譽": "defamation",
    "恐嚇": "intimidation",
    "違反保護令": "stalking",
    "妨害自由": "intimidation",
    "偽造文書": "forgery",
    "跟蹤騷擾": "stalking",
    "誣告": "false_accusation",
    "詐欺": "fraud",
    "性騷擾": "sexual_harassment",
    "性騷擾防治法": "sexual_harassment",
    "妨害性隱私": "sexual_harassment",
    "公共危險": "public_danger",
    "毒品危害防制條例": "drugs",
    "妨害秩序": "disorder",
    "通緝": "escape",
    "逃逸外勞": "trafficking",
    "撤回告訴": "complaint",
    "刑事相驗": "homicide",
    "聲請保護令": "stalking",
}

# xlsm 通用欄對應之系統角色
SHEET_ROLE_ALIASES = {"被害人通用": "victim", "涉嫌人通用": "suspect", "證人通用": "witness", "通用": "witness"}

# 明確為樣板插值的公式題，保留為承辦人檢核提示而非問句
_FORMULA_SKIP_MARKERS = ("CONCATENATE", "MID(", "LEFT(")

# 明確屬其他案類且與所標罪章無關的殘留題（跨欄貼上殘留），依內容排除
_UNRELATED_MARKERS = (
    "你向警方表示你係為美國人士",
    "你於民國114年02月09日",
    "你於108年7月1日酒駕新法",
    "6N-5698",
    "台北馬偕醫院，經醫生於113年1月10日",
)


def load_xlsm_questions(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """回傳 {role: [{offense_id, text, col, row}]}. 公式題跳過。"""
    source = path or XLSM_JSON_PATH
    if not source.is_file():
        return {"victim": [], "suspect": [], "witness": []}
    raw = json.loads(source.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, Any]]] = {"victim": [], "suspect": [], "witness": []}
    for role, items in raw.items():
        if role not in result:
            continue
        seen: set[str] = set()
        for item in items:
            text = str(item.get("text", "")).strip()
            if not text or text.startswith("="):
                continue
            if any(marker in text for marker in _UNRELATED_MARKERS):
                continue
            if text in seen:
                continue
            seen.add(text)
            offense_name = str(item.get("offense", "")).strip()
            if offense_name in SHEET_ROLE_ALIASES:
                continue  # 通用欄已由 company_templates.py 逐字涵蓋
            offense_id = OFFENSE_NAME_TO_ID.get(offense_name)
            if offense_id is None:
                continue
            result[role].append({
                "offense_id": offense_id,
                "offense_name": offense_name,
                "text": text,
                "col": item.get("col", ""),
                "row": item.get("row", 0),
            })
    return result


def xlsm_questions_for(bank_questions: list[dict[str, Any]], role: str, offense_id: str) -> list[dict[str, Any]]:
    """取得指定罪章之公司套表題（kind=company_offense）。"""
    cache = getattr(load_xlsm_questions, "_cache", None)
    if cache is None:
        cache = load_xlsm_questions()
        load_xlsm_questions._cache = cache
    questions: list[dict[str, Any]] = []
    seen = {q["text"] for q in bank_questions}
    for index, item in enumerate(cache.get(role, []), start=1):
        if item["offense_id"] != offense_id:
            continue
        if item["text"] in seen:
            continue
        questions.append({
            "id": f"XLSM-{role[0].upper()}-{offense_id}-{item['row']}{item['col']}",
            "text": item["text"],
            "kind": "company_offense",
            "role": role,
            "offense_id": offense_id,
            "offense_name": item["offense_name"],
            "priority": 1,
            "source": {"label": "新套表.xlsm 公司核定套表題", "status": "COMPANY_VERBATIM"},
            "status": "PENDING",
            "answer": "",
        })
        seen.add(item["text"])
    return questions


def reset_cache() -> None:
    if hasattr(load_xlsm_questions, "_cache"):
        del load_xlsm_questions._cache
