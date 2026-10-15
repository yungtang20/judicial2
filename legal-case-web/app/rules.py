from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from .roc_time import format_roc_time
from typing import Any

from .company_templates import company_questions, render_company_text
from .markdown_questions import merge_markdown_questions
from .section_questions import ordered_section_questions
from .xlsm_questions import xlsm_questions_for

# 8 頁防線（spec §7.5）：實測 97 題 = 8 頁（DOCX 上限）；每罪章 core+xls 約 24 題
# 3 罪章 ≈ 97 題（滿 8 頁）；core 不得裁 → 超量由 build_questions fail closed 提示縮小
MAX_SELECTED_OFFENSES = 3

# 8 頁防線（spec §7.5）：實測 DOCX 容量約 97 題（含 company/common）。
# victim 固定 company(7)+common(12)，故 offense 題上限為 97-19=78。
# 超出時 fail closed 提示承辦人縮小候選路由（不得靜默裁 core）
MAX_OFFENSE_QUESTIONS = 78

PROPERTY_TAKING_ACTIONS = ("拿走", "取走", "帶走", "搶走", "奪走", "偷走", "搬走")
PROPERTY_ROUTE_IDS = {"theft", "embezzlement", "robbery"}


class RuleError(ValueError):
    pass


def load_bank(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        bank = json.load(handle)
    if bank.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise RuleError("題庫必須維持人工審查狀態")
    question_root = path.resolve().parents[2] / "questions"
    if not question_root.is_dir():
        raise RuleError("找不到經審核的 Markdown 問句庫")
    merged = merge_markdown_questions(bank, question_root)
    crosswalk_path = path.with_name("legal_route_crosswalk.json")
    if not crosswalk_path.is_file():
        raise RuleError("缺少 legal route crosswalk")
    crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
    if crosswalk.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise RuleError("legal route crosswalk 必須維持人工審查狀態")
    route_meta = {item["id"]: item for item in crosswalk.get("routes", [])}
    offense_ids = {item["id"] for item in merged["offenses"]}
    if set(route_meta) != offense_ids:
        missing = sorted(offense_ids - set(route_meta))
        extra = sorted(set(route_meta) - offense_ids)
        raise RuleError(f"legal route crosswalk 不完整：missing={missing}, extra={extra}")
    for offense in merged["offenses"]:
        meta = deepcopy(route_meta[offense["id"]])
        child_routes = meta.get("child_routes", [])
        excluded_routes = meta.get("excluded_routes", [])
        child_ids = [item.get("id") for item in child_routes]
        if len(child_ids) != len(set(child_ids)):
            raise RuleError(f"legal route child id 重複：{offense['id']}")
        for child in child_routes:
            required = {"id", "route_kind", "law_name", "article_no", "name", "fact_elements", "review_status"}
            if not required.issubset(child):
                raise RuleError(f"legal route child 欄位不完整：{offense['id']}")
            if not child["fact_elements"] or child["review_status"] != "HUMAN_REVIEW_REQUIRED":
                raise RuleError(f"legal route child 必須有事實元素並維持人工審查：{child['id']}")
        for excluded in excluded_routes:
            required = {"id", "article_no", "status", "reason", "source_url"}
            if not required.issubset(excluded) or excluded["status"] not in {"DELETED", "UNCONSTITUTIONAL_INVALIDATED"}:
                raise RuleError(f"excluded legal route 欄位或狀態不正確：{offense['id']}")
        offense["route_type"] = meta["route_type"]
        offense["selection_policy"] = meta.get("selection_policy", "OPTIONAL")
        if offense["selection_policy"] not in {"REQUIRED", "OPTIONAL", "NOT_APPLICABLE"}:
            raise RuleError(f"legal route selection_policy 無效：{offense['id']}")
        offense["crosswalk_status"] = meta["crosswalk_status"]
        offense["crosswalk_note"] = meta["note"]
        offense["legal_routes"] = child_routes
        offense["excluded_legal_routes"] = excluded_routes
        offense["content_review_status"] = "HUMAN_REVIEW_REQUIRED"
    merged["legal_route_crosswalk_version"] = crosswalk["schema_version"]
    return merged


def candidate_element_state(offense: dict[str, Any]) -> tuple[list[str], str, str]:
    labels = [item["label"] for item in offense.get("elements", [])]
    route_type = offense.get("route_type", "substantive")
    crosswalk_status = offense.get("crosswalk_status", "SPLIT_REQUIRED")
    if route_type in {"procedural", "protective"}:
        return ["PROCEDURAL_FACT_MODEL_REQUIRED"], "PROCEDURAL_FACT_MODEL_REQUIRED", "UNMAPPED"
    if not labels or crosswalk_status == "SPLIT_REQUIRED":
        return labels or ["UNMAPPED_ELEMENT_MODEL"], "NEED_LEGAL_ROUTE_MAPPING", "UNMAPPED"
    return labels, "NEED_REVIEW", "MAPPED"


def _fact_status_for_kind(kind: str) -> str:
    """kind → fact_status 對應（spec §4.2 七值枚舉）。"""
    return {"event": "當事人陳述", "statement": "當事人陳述", "unknown": "未知"}.get(kind, "當事人陳述")


def _source_segments(summary: str) -> list[tuple[str, int, int]]:
    """依明確句界切分來源文字，不推斷人物、行為、因果或法律性質。"""
    segments: list[tuple[str, int, int]] = []
    for match in re.finditer(r"[^。！？；\r\n]+[。！？；]?", summary):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if not text:
            continue
        start = match.start() + leading
        segments.append((text, start, start + len(text)))
    return segments


def _property_taking_values(summary: str) -> dict[str, str] | None:
    action = next((item for item in PROPERTY_TAKING_ACTIONS if item in summary), "")
    if not action:
        return None
    actor_match = re.search(r"(?:^|[，。；！？\s])([^，。；！？\s]{1,8})把", summary)
    actor = actor_match.group(1) if actor_match else next(
        (item for item in ("對方", "他", "她", "行為人") if item in summary), "UNKNOWN"
    )
    action_pattern = "|".join(PROPERTY_TAKING_ACTIONS)
    object_match = re.search(
        rf"(?:我的|他的|她的|其)([^，。；！？\s]{{1,12}}?)(?:被)?(?:{action_pattern})",
        summary,
    ) or re.search(
        rf"把([^，。；！？\s]{{1,12}}?)(?:被)?(?:{action_pattern})",
        summary,
    )
    obj = object_match.group(1) if object_match else "UNKNOWN"
    consent = "NO" if any(item in summary for item in ("未經同意", "沒有同意", "不同意")) else (
        "YES" if any(item in summary for item in ("經我同意", "我同意", "同意他")) else "UNKNOWN"
    )
    prior_possession = "YES" if any(item in summary for item in ("借給", "交給他保管", "交由他保管", "代管", "寄放")) else "UNKNOWN"
    force = "YES" if any(item in summary for item in ("強暴", "脅迫", "威脅", "拉扯", "毆打", "搶走", "奪走")) else (
        "NO" if any(item in summary for item in ("沒有使用暴力", "未使用暴力", "沒有威脅", "未威脅")) else "UNKNOWN"
    )
    return_agreement = "YES" if any(item in summary for item in ("約定歸還", "答應歸還", "說好歸還", "借給")) else "UNKNOWN"
    evidence = "YES" if any(item in summary for item in ("訊息", "錄影", "監視器", "證人", "照片")) else "UNKNOWN"
    return {
        "actor": actor,
        "action": "取走物品",
        "object": obj,
        "original_possession": "UNKNOWN",
        "consent": consent,
        "prior_lawful_possession": prior_possession,
        "force_or_threat": force,
        "return_agreement": return_agreement,
        "intent": "UNKNOWN",
        "evidence": evidence,
    }


def analyze_gate1(intake: dict[str, Any], *, use_ai: bool = True) -> dict[str, Any]:
    """Return Gate 1 structured facts with provenance and status.

    LLM 路徑（use_ai）：呼叫 ai.segment_facts 切分摘要為多筆事實；
    每筆 text 皆為摘要逐字子字串（ai.py 已驗證防杜撰），並帶 schema 欄位。
    LLM 無法使用時退回規則路徑（僅依句界建立可回查的來源陳述）。
    """
    summary = intake["summary"].strip()
    # Helper to create a fact object with minimal required fields
    def make_fact(
        text: str,
        fact_kind: str,
        fields: dict[str, str] | None = None,
        *,
        fact_key: str = "",
        value: str = "",
        source_excerpt: str | None = None,
        source_start: int | None = None,
        source_end: int | None = None,
    ) -> dict[str, Any]:
        f = fields or {}
        return {
            "fact_id": str(uuid.uuid4()),
            "fact_key": fact_key,
            "value": value or text,
            "source_ref": "intake.summary",
            "source_excerpt": text if source_excerpt is None else source_excerpt,
            "source_start": source_start,
            "source_end": source_end,
            "normalized_text": text.strip(),
            "subject": f.get("subject", ""),
            "action": f.get("action", ""),
            "object": f.get("object", ""),
            "recipient": f.get("recipient", ""),
            "time": f.get("time", ""),
            "place": f.get("place", ""),
            "possession_state": f.get("possession_state", ""),
            "knowledge_or_intent": f.get("knowledge_or_intent", ""),
            "result": f.get("result", ""),
            "causal_relation": f.get("causal_relation", ""),
            "evidence_refs": [],
            "fact_status": _fact_status_for_kind(fact_kind),
            # FACT 僅表示來源文字明示記載，不表示內容已經查證為真。
            "machine_status": "UNKNOWN" if fact_kind == "unknown" else "FACT",
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }

    facts: list[dict[str, Any]] = []
    segmentation_source = "rules"
    if summary and use_ai:
        try:
            from .ai import segment_facts
            result = segment_facts(summary)
        except Exception:
            result = None
        if result is not None:
            segmentation_source = f"ai:{result['model']}"
            for item in result["facts"]:
                start = summary.find(item["text"])
                facts.append(make_fact(
                    item["text"], item["kind"], item,
                    source_start=start if start >= 0 else None,
                    source_end=start + len(item["text"]) if start >= 0 else None,
                ))
    if not facts and summary:
        # rules fallback：只依句界切分並保留精確 offset，不做語意推測。
        for text, start, end in _source_segments(summary):
            facts.append(make_fact(text, "statement", source_start=start, source_end=end))
    property_values = _property_taking_values(summary)
    if property_values:
        labels = {
            "actor": "行為人",
            "action": "行為",
            "object": "客體",
            "original_possession": "原持有狀態",
            "consent": "是否同意",
            "prior_lawful_possession": "是否曾交付保管或合法持有",
            "force_or_threat": "是否使用強暴、脅迫或拉扯",
            "return_agreement": "是否具有返還約定",
            "intent": "行為人的主觀意圖",
            "evidence": "可供查證的證據",
        }
        for key, value in property_values.items():
            is_unknown = value == "UNKNOWN"
            fields: dict[str, str] = {}
            if key == "actor" and not is_unknown:
                fields["subject"] = value
            elif key == "action" and not is_unknown:
                fields["action"] = value
            elif key == "object" and not is_unknown:
                fields["object"] = value
            facts.append(make_fact(
                labels[key],
                "unknown" if is_unknown else "statement",
                fields,
                fact_key=key,
                value=value,
                source_excerpt="" if is_unknown else summary,
            ))
        default_unknowns = [labels[key] for key, value in property_values.items() if value == "UNKNOWN"]
    else:
        default_unknowns = ["行為人", "行為方式", "結果與行為間關係", "可供查證的證據"]
        for text in default_unknowns:
            facts.append(make_fact(text, "unknown", value="UNKNOWN", source_excerpt=""))

    def unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    source_facts = [item for item in facts if not item.get("fact_key") and item.get("machine_status") != "UNKNOWN"]
    # legacy arrays 是 facts 的相容投影，不另行建立第二份事件真實來源。
    gate1: dict[str, Any] = {
        "people": unique([str(item.get("subject", "")) for item in facts]),
        "events": unique([str(item.get("source_excerpt", "")) for item in source_facts]),
        "segmentation_source": segmentation_source,
        "times": unique([format_roc_time(intake["event_time"])] + [str(item.get("time", "")) for item in facts]),
        "places": unique([intake["location"]] + [str(item.get("place", "")) for item in facts]),
        "objects": unique([str(item.get("object", "")) for item in facts]),
        "behaviors": unique([str(item.get("action", "")) for item in facts]),
        "causation": "UNKNOWN",
        "unknowns": default_unknowns,
        "facts": facts,  # new structured fact list
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    return gate1


_NEGATION_MARKERS = ("並未", "並非", "未提及", "沒有", "尚未", "非因", "不曾", "無證據", "無人", "未遂", "謊稱並無")


def _keyword_negated(keyword: str, summary: str) -> bool:
    """檢查關鍵字是否只出現在否定語句中（spec §5.1：關鍵字不得為唯一機制）。

    找出關鍵字出現位置，向前看 12 個字元內是否有否定標記。
    若全部命中位置都被否定，回傳 True（視為未命中）。
    """
    lowered = summary.casefold()
    kw = keyword.casefold()
    positions: list[int] = []
    start = 0
    while True:
        idx = lowered.find(kw, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    if not positions:
        return True  # 沒出現 = 未命中
    window = 14
    sentence_breaks = ("。", "；", "！", "？")
    for pos in positions:
        context = lowered[max(0, pos - window):pos]
        # 跨句不算否定：從否定標記到關鍵字之間不得有句讀
        clean = context
        for br in sentence_breaks:
            clean = clean.split(br)[-1]
        if not any(marker in clean for marker in _NEGATION_MARKERS):
            return False  # 至少有一個非否定命中
    return True  # 全部命中都在否定語句內


def candidate_offenses(
    summary: str, bank: dict[str, Any], gate1: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    lowered = summary.casefold()
    by_id = {item["id"]: item for item in bank["offenses"]}
    matched_ids: set[str] = set()
    for offense in bank["offenses"]:
        hits = [
            keyword for keyword in offense["keywords"]
            if keyword.casefold() in lowered and not _keyword_negated(keyword, summary)
        ]
        if hits:
            element_labels, candidate_status, element_status = candidate_element_state(offense)
            matched_ids.add(offense["id"])
            matches.append({
                "id": offense["id"],
                "candidate_id": f"candidate:{offense['id']}",
                "name": offense["name"],
                "matched_terms": hits,
                "status": candidate_status,
                "notice": "僅為規則式候選，不代表犯罪成立。",
                "inclusion_reason": f"案情摘要含有本罪章的關鍵詞：{', '.join(hits)}",
                "reservation_reason": "僅基於關鍵字匹配，尚未結合結構化事實分析",
                "supporting_fact_refs": ["intake.summary"],
                "contradicting_fact_refs": [],
                "unknown_elements": element_labels,
                "element_model_status": element_status,
                "route_type": offense.get("route_type", "substantive"),
                "crosswalk_status": offense.get("crosswalk_status", "SPLIT_REQUIRED"),
                "legal_routes": deepcopy(offense.get("legal_routes", [])),
                "excluded_legal_routes": deepcopy(offense.get("excluded_legal_routes", [])),
                "legal_route_selection_status": offense.get("selection_policy", "OPTIONAL"),
                "source": offense["source"],
                "distinguishing_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-D-" in item["id"]][:5] or ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
                "required_evidence_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-R-" in item["id"]][:5] or ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
                "competition_analysis": "NOT_ASSESSED",
                "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
                "version": offense.get("source", {}).get("status", "UNKNOWN"),
            })
    property_taking = _property_taking_values(summary) is not None
    related_ids = {
        related
        for offense_id in matched_ids
        for related in by_id[offense_id].get("related", [])
        if related not in matched_ids and related in by_id
    }
    if property_taking:
        related_ids.discard("aggravated_theft")
        related_ids.update(PROPERTY_ROUTE_IDS - matched_ids)
    for offense_id in sorted(related_ids):
        offense = by_id[offense_id]
        element_labels, candidate_status, element_status = candidate_element_state(offense)
        matches.append({
            "id": offense["id"],
            "candidate_id": f"candidate:{offense['id']}",
            "name": offense["name"],
            "matched_terms": [],
            "status": candidate_status,
            "notice": "區辨用關聯候選，不代表犯罪成立。",
            "inclusion_reason": "由已命中的方向帶入作為競爭假設，只供區辨，不是事實支持。",
            "reservation_reason": "僅為關聯方向，沒有直接事實支持",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": [],
            "unknown_elements": element_labels,
            "element_model_status": element_status,
            "route_type": offense.get("route_type", "substantive"),
            "crosswalk_status": offense.get("crosswalk_status", "SPLIT_REQUIRED"),
            "legal_routes": deepcopy(offense.get("legal_routes", [])),
            "excluded_legal_routes": deepcopy(offense.get("excluded_legal_routes", [])),
            "legal_route_selection_status": offense.get("selection_policy", "OPTIONAL"),
            "source": offense["source"],
            "distinguishing_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-D-" in item["id"]][:5] or ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
            "required_evidence_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-R-" in item["id"]][:5] or ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
            "competition_analysis": "NOT_ASSESSED",
                "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
            "version": offense.get("source", {}).get("status", "UNKNOWN"),
        })
    property_unknowns = {
        item.get("fact_key")
        for item in (gate1 or {}).get("facts", [])
        if item.get("value") == "UNKNOWN"
    }
    dependencies = {
        "theft": ["original_possession", "consent", "intent"],
        "embezzlement": ["prior_lawful_possession", "return_agreement", "intent"],
        "robbery": ["force_or_threat", "original_possession", "intent"],
    }
    for item in matches:
        item["candidate_state"] = "NEED_REVIEW"
        item["unknown_fact_keys"] = [
            key for key in dependencies.get(item["id"], []) if not property_unknowns or key in property_unknowns
        ]
        item["status_reasons"] = []
    return sorted(matches, key=lambda item: (-len(item["matched_terms"]), item["name"]))


def alternative_legal_routes(gate1: dict[str, Any]) -> list[dict[str, Any]]:
    keys = {item.get("fact_key") for item in gate1.get("facts", [])}
    if not {"action", "object"}.issubset(keys):
        return []
    return [{
        "route_id": "civil_possession_dispute",
        "name": "民事占有或返還爭議",
        "status": "NEED_REVIEW",
        "selectable_as_offense": False,
        "reason_fact_keys": [
            "original_possession", "consent", "prior_lawful_possession", "return_agreement",
        ],
        "notice": "僅為非刑事替代檢查方向，不代表民事關係成立。",
    }]


def build_questions(
    bank: dict[str, Any],
    role: str,
    offense_ids: list[str],
    *,
    gate1: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    legal_route_ids: list[str] | None = None,
    materialized_at: str | None = None,
) -> list[dict[str, Any]]:
    """依序建立問句：公司必問 → 通用程序 → 各罪章 md 區段 → JSON 要件。

    預算上限 MAX_OFFENSE_QUESTIONS 是 8 頁防線的一部分；超出時以後選罪章的
    區分題與加重題先被裁掉，公司必問與核心題不受預算刪除。
    """
    if role not in bank["common"]:
        raise RuleError("不支援的受詢問人身分")
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in company_questions(role):
        text = render_company_text(raw["text"], today="　", now_time="　年　月　日　時　分")
        questions.append({
            "id": raw["id"],
            "text": text,
            "kind": "company",
            "role": role,
            "priority": 1,
            "source": {"label": "公司範本必問", "status": "COMPANY_VERBATIM"},
            "status": "PENDING",
            "answer": "",
        })
        seen.add(raw["text"])

    for raw in bank["common"][role]:
        item = deepcopy(raw)
        item.update({"kind": "common", "role": role, "status": "PENDING", "answer": ""})
        questions.append(item)
        seen.add(item["text"])

    from .questions import (
        THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS,
        THEFT_320_1_MOVABLE_PACK_VERSION,
        THEFT_320_1_MOVABLE_ROUTE_ID,
        THEFT_320_1_MOVABLE_WORK_ITEM_HASH,
        build_property_taking_questions,
    )

    candidate_ids = {item.get("id") for item in (candidates or [])}
    route_ids = list(dict.fromkeys(legal_route_ids or []))
    focused_questions = build_property_taking_questions(
        role,
        candidate_ids,
        gate1 or {},
        set(route_ids),
        materialized_at,
    )
    for question in focused_questions:
        questions.append(question)
        seen.add(question["text"])

    offenses = {item["id"]: item for item in bank["offenses"]}
    for offense_id in offense_ids:
        offense = offenses.get(offense_id)
        if offense is None:
            raise RuleError(f"未知罪章：{offense_id}")
        # 1) 公司套表罪章題（新套表.xlsm 各罪章欄）— 不受即時預算限制（公司核定題）
        for question in xlsm_questions_for(questions, role, offense_id):
            if question["text"] in seen:
                continue
            questions.append(question)
            seen.add(question["text"])
        if focused_questions and offense_id in PROPERTY_ROUTE_IDS:
            continue
        # 2) md 核心與補充（含區分、加重依 section 順序）— 先全部收集
        sections = offense.get("section_questions", {}).get(role, {})
        for question in ordered_section_questions(
            sections, role, offense_id, offense["name"], offense["source"],
        ):
            if question["text"] in seen:
                continue
            questions.append(question)
            seen.add(question["text"])
        # 3) JSON 要件題（僅在 md 未涵蓋同一 element 時補入）— 先全部收集
        for element in offense.get("elements", []):
            text = element["victim" if role == "victim" else "suspect"]
            if text in seen:
                continue
            questions.append({
                "id": f"{role[0].upper()}-{offense_id}-{element['id']}",
                "text": text,
                "kind": "core",
                "role": role,
                "offense_id": offense_id,
                "offense_name": offense["name"],
                "element_id": element["id"],
                "element_label": element["label"],
                "priority": 1,
                "source": offense["source"],
                "status": "PENDING",
                "answer": "",
            })
            seen.add(text)
    # spec §7.5：統一按優先序裁切（core/company/common 保護；區分/加重先被裁）
    # 8 頁防線：offense 題（非 company/common）上限 MAX_OFFENSE_QUESTIONS
    from .questions import (
        QuestionBudgetExceeded,
        apply_question_budget,
        enrich_question_metadata,
        validate_generated_questions,
    )
    all_questions = list(questions)
    try:
        questions = apply_question_budget(questions, max_offense_questions=MAX_OFFENSE_QUESTIONS)
    except QuestionBudgetExceeded as exc:
        raise RuleError(str(exc)) from exc
    # 裁切透明化（docs/QUESTION_DESIGN_AND_USE.md §6）：被裁的題目記錄，不靜默丟棄
    kept_ids = {q["id"] for q in questions}
    pruned = [q for q in all_questions if q.get("id") not in kept_ids]
    # spec §7.2：metadata 豐富化；candidates 以本次選擇的罪章近似（供 distinguishing 的 legal_targets）
    pseudo_candidates = [
        {"id": oid, "offense_id": oid} for oid in offense_ids
    ]
    questions = enrich_question_metadata(questions, {}, pseudo_candidates)

    # spec §7.2/§7.3 品質檢核（docs/QUESTION_DESIGN_AND_USE.md §8）：problems 即 fail closed
    validation = validate_generated_questions(questions, role)
    if validation["problems"]:
        raise RuleError("問句品質檢核失敗：" + "；".join(validation["problems"][:3]))
    build_questions.last_validation = validation
    build_questions.pruned_questions = [
        {
            "id": q.get("id"),
            "text": q.get("text"),
            "kind": q.get("kind"),
            "offense_id": q.get("offense_id"),
            "question_concept_id": q.get("meta", {}).get("question_concept_id"),
            "pack_id": q.get("meta", {}).get("pack_id"),
        }
        for q in pruned
    ]
    if pruned:
        build_questions.last_validation["warnings"].append(
            f"Q8 裁切 {len(pruned)} 題（區分/加重/補充優先），已記錄於 pruned_questions 供承辦人參考"
        )
    coverage_by_route: dict[str, dict[str, Any]] = {}
    for route_id in route_ids:
        if route_id != THEFT_320_1_MOVABLE_ROUTE_ID:
            coverage_by_route[route_id] = {
                "pack_scope": "LEGACY_PARENT_PACK",
                "materialization_status": "NOT_APPLICABLE",
                "approval_status": "HUMAN_REVIEW_REQUIRED",
                "coverage_claim": "NONE",
                "expected_concept_ids": [],
                "materialized_question_ids": [],
                "missing_concept_ids": [],
                "pruned_concept_ids": [],
                "human_review_required": True,
            }
            continue
        pack_questions = [
            q for q in questions
            if q.get("meta", {}).get("pack_id") == route_id
        ]
        materialized_concepts = {
            q.get("meta", {}).get("question_concept_id") for q in pack_questions
        }
        expected = list(THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS)
        missing = [concept_id for concept_id in expected if concept_id not in materialized_concepts]
        pruned_concepts = sorted({
            q.get("meta", {}).get("question_concept_id") for q in pruned
            if q.get("meta", {}).get("pack_id") == route_id
            and q.get("meta", {}).get("question_concept_id")
        })
        complete = not missing and not pruned_concepts
        coverage_by_route[route_id] = {
            "pack_id": route_id,
            "pack_version": THEFT_320_1_MOVABLE_PACK_VERSION,
            "work_item_hash": THEFT_320_1_MOVABLE_WORK_ITEM_HASH,
            "pack_scope": "EXACT_CHILD_PACK",
            "materialization_status": "COMPLETE" if complete else "PARTIAL",
            "approval_status": "STATIC_HUMAN_APPROVED",
            "coverage_claim": "BOUNDED_TO_APPROVED_WORK_ITEM" if complete else "NONE",
            "expected_concept_ids": expected,
            "materialized_question_ids": [q["id"] for q in pack_questions],
            "missing_concept_ids": missing,
            "pruned_concept_ids": pruned_concepts,
            "human_review_required": True,
            "legal_conclusion": False,
        }
    build_questions.question_coverage_by_route = {
        "route_context_ids": route_ids,
        "routes": coverage_by_route,
        "human_review_required": True,
        "legal_conclusion": False,
    }
    return questions


def _offense_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in questions if item["kind"] not in {"common", "company"}]


def is_victim_code(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{1,8}\d{3,20}", value.strip()))


def required_case_numbers(case: dict[str, Any]) -> list[str]:
    required = ["proof"]
    offense_ids = set(case.get("selected_offenses", []))
    for interview in case.get("interviews", {}).values():
        offense_ids.update(interview.get("selected_offenses", []))
    if "fraud" in offense_ids:
        required.append("case_165")
    intake = case["intake"]
    if intake.get("victim_is_code") or is_victim_code(intake.get("victim_identifier", "")):
        required.append("women_child")
    return required


def concise_summary(text: str, limit: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > limit:
        raise RuleError(f"條陳案情摘要超過 {limit} 字上限")
    return normalized
