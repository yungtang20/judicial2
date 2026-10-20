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
from pathlib import Path
from typing import Any

from .question_hygiene import classify, duplicate_verdict, normalize

XLSM_JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "xlsm_questions.json"

# xlsm 罪章欄名 → 本系統罪章 id（與 question_bank.json 對應）
OFFENSE_NAME_TO_ID: dict[str, str] = {
    "過失傷害": "injury",
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
    # ── AI_* 欄位映射（2026-10-20 P2 階段）──
    # 這些欄名以 AI_ 開頭，代表由 AI 輔助生成而非公司既有套表；
    # 映射到既有 offense_id，使 runtime 可載入，但 source.status 標為 AI_GENERATED
    # 而非 COMPANY_VERBATIM，避免與公司核定逐字題混淆。
    "AI_少年事件": "juvenile",
    "AI_賭博": "gambling",
    "AI_公然猥褻": "public_indecency",
    "AI_槍砲": "firearms",
    "AI_毒品危害": "drugs",
    "AI_妨害性自主": "sexual_assault",
    "AI_兒少性剝削": "child_exploitation",
    "AI_圖利賄賂": "bribery",
}

# xlsm 通用欄對應之系統角色
SHEET_ROLE_ALIASES = {"被害人通用": "victim", "涉嫌人通用": "suspect", "證人通用": "witness", "通用": "witness"}

# 明確為樣板插值的公式題，保留為承辦人檢核提示而非問句
_FORMULA_SKIP_MARKERS = ("CONCATENATE", "MID(", "LEFT(")

# 這些婦幼／保護路由已有公司核定逐字筆錄，runtime 不得再混入本庫
# 同罪章的 markdown 或 JSON 問句。其他 XLSM 罪章題仍可依 company-standard.md
# 規則補充未涵蓋的法定要件。
COMPANY_STANDARD_ONLY_OFFENSES = frozenset({"sexual_harassment", "stalking"})


def _render_verified_placeholders(text: str) -> str:
    """只代入已由主管機關公開資料核對的固定服務專線。

    題庫原文及順序維持不變；不認得的占位符仍原樣保留，讓下游驗證
    fail closed，而不是猜測內容。
    """
    replacements = (
        ("衛生福利部〈代號〉安心專線", "衛生福利部1925安心專線"),
        ("撥打〈代號〉福利諮詢專線", "撥打1957福利諮詢專線"),
        ("法律扶助基金會412-〈代號〉轉2", "法律扶助基金會412-8518轉2"),
    )
    rendered = text
    for placeholder, value in replacements:
        rendered = rendered.replace(placeholder, value)
    return rendered


def _quarantine_record(
    text: str, role: str, item: dict[str, Any], verdict: Any,
) -> dict[str, Any]:
    return {
        "text": text,
        "role": role,
        "source_cell": {"row": item.get("row", 0), "col": item.get("col", "")},
        "rule_id": verdict.rule_id,
        "decision": verdict.decision,
        "reason": verdict.reason,
    }


def load_xlsm_questions(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """回傳 {role: [{offense_id, text, col, row}]}. 公式題跳過。

    不在訪談頻道的格子改存於 `load_xlsm_questions.quarantine`（同 role 鍵），
    供呼叫端回報；判定只換通道，公司原文不改。
    """
    source = path or XLSM_JSON_PATH
    quarantine: dict[str, list[dict[str, Any]]] = {"victim": [], "suspect": [], "witness": []}
    load_xlsm_questions.quarantine = quarantine
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
            offense_name = str(item.get("offense", "")).strip()
            if offense_name in SHEET_ROLE_ALIASES:
                continue  # 通用欄已由 company_templates.py 逐字涵蓋
            offense_id = OFFENSE_NAME_TO_ID.get(offense_name)
            if offense_id is None:
                continue
            key = normalize(text)
            if key in seen:
                quarantine[role].append(
                    _quarantine_record(text, role, item, duplicate_verdict())
                )
                continue
            verdict = classify(text, role)
            if verdict.decision != "SERVE":
                quarantine[role].append(_quarantine_record(text, role, item, verdict))
                continue
            seen.add(key)
            is_ai_generated = offense_name.startswith("AI_")
            result[role].append({
                "offense_id": offense_id,
                "offense_name": offense_name,
                "text": text,
                "col": item.get("col", ""),
                "row": item.get("row", 0),
                "source_status": "AI_GENERATED" if is_ai_generated else "COMPANY_VERBATIM",
            })
    return result


def xlsm_quarantine() -> list[dict[str, Any]]:
    """公司套表題在載入邊界被移出訪談頻道的全部紀錄。

    回傳跨角色的清單：紀錄本身帶 role 與來源格，供承辦人核對被扣留的題目。
    """
    cache = getattr(load_xlsm_questions, "_cache", None)
    if cache is None:
        cache = load_xlsm_questions()
        load_xlsm_questions._cache = cache
    quarantine = getattr(load_xlsm_questions, "quarantine", {})
    return [
        record
        for role_records in quarantine.values()
        for record in role_records
    ]


def xlsm_questions_for(
    bank_questions: list[dict[str, Any]],
    role: str,
    offense_id: str,
    legal_route_ids: list[str] | None = None,
    gate1: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """取得指定罪章之公司套表題（kind=company_offense）。"""
    cache = getattr(load_xlsm_questions, "_cache", None)
    if cache is None:
        cache = load_xlsm_questions()
        load_xlsm_questions._cache = cache
    questions: list[dict[str, Any]] = []
    seen = {normalize(q["text"]) for q in bank_questions}
    source_text = " ".join(
        str(fact.get("source_excerpt", ""))
        for fact in (gate1 or {}).get("facts", [])
    )
    for index, item in enumerate(cache.get(role, []), start=1):
        if item["offense_id"] != offense_id:
            continue
        selected_routes = set(legal_route_ids or [])
        if offense_id == "injury" and "injury_277_general" in selected_routes:
            if "過失" in item["offense_name"]:
                continue
        if offense_id == "injury" and "injury_284_negligent" in selected_routes:
            medical_context = any(
                term in source_text for term in ("手術", "醫師", "診所", "醫院", "病歷", "醫療")
            )
            if medical_context:
                # 現行公司「過失傷害」及「傷害」欄均非醫療事故專用；
                # 保留原始題庫不改字，只避免把車禍／一般攻擊題套入醫療事件。
                continue
            if "過失" not in item["offense_name"] and item["offense_name"] != "傷害":
                continue
        if offense_id == "fraud" and "fraud_339_general" in selected_routes:
            if "信用卡" in item["text"] and "信用卡" not in source_text and "盜刷" not in source_text:
                continue
        if offense_id == "sexual_harassment":
            sexual_image_context = any(
                term in source_text
                for term in ("性影像", "偷拍", "拍攝", "攝錄", "散布", "上傳", "供人觀覽")
            )
            if item["offense_name"] == "妨害性隱私" and not sexual_image_context:
                # 同一 XLSM 中的性騷擾與性影像欄共用 parent offense id；
                # 保留公司原文，但沒有影像事實時不得把性影像題混入觸摸案件。
                continue
        if normalize(item["text"]) in seen:
            continue
        rendered_text = _render_verified_placeholders(item["text"])
        is_ai = item.get("source_status") == "AI_GENERATED"
        source_label = "新套表.xlsm AI 輔助生成題" if is_ai else "新套表.xlsm 公司核定套表題"
        source_status = "AI_GENERATED" if is_ai else "COMPANY_VERBATIM"
        questions.append({
            "id": f"XLSM-{role[0].upper()}-{offense_id}-{item['row']}{item['col']}",
            "text": rendered_text,
            "kind": "company_offense",
            "role": role,
            "offense_id": offense_id,
            "offense_name": item["offense_name"],
            "priority": 1,
            "source": {"label": source_label, "status": source_status},
            "status": "PENDING",
            "answer": "",
            "meta": {
                "legacy_fixed": True,
                "legacy_compound": item["text"].count("？") + item["text"].count("?") > 1,
                "answer_mode": "narrative_only",
                "machine_effects": [],
                "source_cell": {"row": item.get("row", 0), "col": item.get("col", "")},
                "applicability_route_ids": sorted(selected_routes),
                "template_text": item["text"],
                "interpolation_status": (
                    "VERIFIED_FIXED_VALUE" if rendered_text != item["text"] else "NOT_APPLICABLE"
                ),
            },
        })
        seen.add(normalize(rendered_text))
    return questions


def has_company_standard_questions(role: str, offense_id: str) -> bool:
    """判斷指定角色／罪章是否已有公司核定套表題。

    有公司題時，runtime 不再把本庫同一罪章的 md/JSON 題混入，
    以免公司逐字標準筆錄被自建題改寫或重複。
    """
    cache = getattr(load_xlsm_questions, "_cache", None)
    if cache is None:
        cache = load_xlsm_questions()
        load_xlsm_questions._cache = cache
    return offense_id in COMPANY_STANDARD_ONLY_OFFENSES and any(
        item["offense_id"] == offense_id for item in cache.get(role, [])
    )


def reset_cache() -> None:
    if hasattr(load_xlsm_questions, "_cache"):
        del load_xlsm_questions._cache
