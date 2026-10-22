from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .config import MAX_BODY_BYTES, MAX_SUMMARY_LENGTH, MAX_TEXT_LENGTH
from .ai import analyze_candidates_v3
from .acts import competition_relationships, extract_acts, link_acts_to_candidates
from .company_templates import copy_identity
from .xlsm_questions import xlsm_quarantine
from .v3_contracts import canonical_sha256
from .rules import (
    MAX_SELECTED_OFFENSES,
    analyze_gate1,
    alternative_legal_routes,
    build_questions,
    candidate_element_state,
    candidate_offenses,
    classify_candidates,
    concise_summary,
    required_case_numbers,
    truncate_summary,
)


CURRENT_TEMPLATE_VERSION = "company-verbatim-2026-10-11"
CURRENT_CANDIDATE_ENGINE = "rules-v3+ai-contract-v1"
MAX_PROFILE_FIELD_LENGTH = 200
MAX_FACTS = 50
# 行為時法查對只針對已選罪章的法條；上限避免整個罪章範圍（例如 20 條）乘以
# 多個罪章後把案件回應撐大。
MAX_VERSION_AUDIT_ARTICLES = 80
MACHINE_STATUSES = {"FACT", "INFERENCE", "UNKNOWN", "DISPUTED"}
SUMMARY_CONTEXT_RE = re.compile(
    r"(?P<kind>發生|破獲|查獲)(?P<field>時間|地點)\s*[：:]\s*(?P<value>[^\r\n，,；;。]+)"
)


class WorkflowError(ValueError):
    pass


ALLOWED_STATES = {
    "GATE1_REVIEW",
    "GATE2_QA",
    "CASE_NUMBERS",
    "OUTPUT_READY",
}


def _clean_text(value: Any, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise WorkflowError(f"{field} 必須是文字")
    normalized = value.strip()
    if required and not normalized:
        raise WorkflowError(f"{field} 不得空白")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise WorkflowError(f"{field} 超過 {MAX_TEXT_LENGTH} 字")
    return normalized


def _clean_summary(value: Any) -> str:
    """保留完整原始案情；僅受 HTTP body 的安全上限約束，不套用條陳摘要上限。"""
    if not isinstance(value, str):
        raise WorkflowError("案情摘要 必須是文字")
    normalized = value.strip()
    if not normalized:
        raise WorkflowError("案情摘要 不得空白")
    if len(normalized.encode("utf-8")) > MAX_BODY_BYTES:
        raise WorkflowError(f"案情摘要超過 {MAX_BODY_BYTES} bytes")
    return normalized


def _summary_context(summary: str) -> dict[str, str]:
    """只讀取摘要中明示標籤，不從一般敘述猜測時間或地點。"""
    result = {"event_kind": "發生", "event_time": "UNKNOWN", "location": "UNKNOWN"}
    for match in SUMMARY_CONTEXT_RE.finditer(summary):
        field = match.group("field")
        value = match.group("value").strip()
        if not value:
            continue
        if field == "時間" and result["event_time"] == "UNKNOWN":
            result["event_kind"] = match.group("kind")
            result["event_time"] = value
        elif field == "地點" and result["location"] == "UNKNOWN":
            result["location"] = value
    return result


def _provided_or_derived(raw: dict[str, Any], key: str, derived: str, field: str) -> str:
    """保留既有 API 欄位；空白或未提供時改用摘要明示值。"""
    if key in raw and raw[key] is not None:
        provided = _clean_text(raw[key], field, required=False)
        if provided:
            return provided
    return derived


def _now() -> str:
    return datetime.now(UTC).isoformat()


def revision_hash(case: dict[str, Any]) -> str:
    snapshot = deepcopy(case)
    for field in ("revision", "updated_at", "approvals", "audit"):
        snapshot.pop(field, None)
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _audit(case: dict[str, Any], event: str, **metadata: Any) -> None:
    allowed = {
        "from_state", "to_state", "role", "rule_id", "reason_code",
        "question_count", "offense_count", "document_type", "quarantine_count",
        "schema_version", "request_id", "input_hash", "source_snapshot_hashes",
        "attempt_count",
    }
    case.setdefault("audit", []).append({
        "event": event,
        "at": _now(),
        "revision_hash": revision_hash(case),
        "metadata": {key: value for key, value in metadata.items() if key in allowed},
    })


def _invalidate(case: dict[str, Any], from_gate: str) -> None:
    order = ["gate1", "gate2", "case_numbers", "output"]
    start = order.index(from_gate)
    for gate in order[start:]:
        case.setdefault("approvals", {}).pop(gate, None)
        if from_gate == "gate1":
            for key in list(case["approvals"]):
                if key.startswith(f"{gate}:"):
                    case["approvals"].pop(key, None)
    if from_gate == "gate1":
        case["interviews"] = {}
        case["questions"] = []
        case["selected_offenses"] = []
        case["selected_legal_routes"] = []
        case["legal_route_review"] = None
        case["route_selection_status"] = "PENDING"
        case["question_coverage_by_route"] = None
        case["route_fact_observations"] = {}
        case["route_fact_overlay"] = {}
        case["selected_legal_route_states"] = {}
    case["documents"] = []


def _snapshot(case: dict[str, Any], reason: str) -> None:
    case.setdefault("snapshots", []).append({
        "snapshot_id": str(uuid4()),
        "created_at": _now(),
        "reason": reason,
        "revision_hash": revision_hash(case),
        "state": case["state"],
        "gate1": deepcopy(case.get("gate1", {})),
        "interviews": deepcopy(case.get("interviews", {})),
        "case_numbers": deepcopy(case.get("case_numbers", {})),
        "approvals": deepcopy(case.get("approvals", {})),
        "versions": deepcopy(case.get("versions", {})),
    })


def create_case(raw: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    has_victim = raw.get("has_victim") is True
    summary = _clean_summary(raw.get("summary"))
    summary_context = _summary_context(summary)
    intake = {
        "event_kind": _provided_or_derived(raw, "event_kind", summary_context["event_kind"], "時間類型"),
        "event_time": _provided_or_derived(raw, "event_time", summary_context["event_time"], "發生／破獲時間"),
        "location": _provided_or_derived(raw, "location", summary_context["location"], "發生／破獲地點"),
        "summary": summary,
        "has_victim": has_victim,
        "victim_identifier": _clean_text(raw.get("victim_identifier", ""), "被害人姓名或代號", required=False),
        "victim_is_code": raw.get("victim_is_code") is True,
        "station": _clean_text(raw.get("station", "○○所"), "單位"),
        "officer": _clean_text(raw.get("officer", "○○○"), "處理員警"),
        "report_time": _clean_text(raw.get("report_time", ""), "報案時間", required=False),
        "arrest_time": _clean_text(raw.get("arrest_time", ""), "破獲時間", required=False),
        "jurisdiction": _clean_text(raw.get("jurisdiction", ""), "本案管轄", required=False),
        "disposition": _clean_text(raw.get("disposition", ""), "後續偵辦情形", required=False),
    }
    # 原始案情不限條陳摘要字數，完整保留供 Gate 1 回查；條陳另行產生 500 字摘要。
    # Gate 1 只在本機執行 deterministic segmentation。外部 AI 僅能由 Gate 2
    # 的明示操作觸發，避免僅因環境存在 API key 就外送案情摘要。
    gate1 = analyze_gate1(intake, use_ai=False)
    if has_victim and not intake["victim_identifier"]:
        derived_victim = next((
            item for item in gate1.get("person_attributes", [])
            if item.get("role") == "victim" and item.get("person_code")
        ), None)
        if derived_victim:
            intake["victim_identifier"] = str(derived_victim["person_code"])
            intake["victim_is_code"] = True
    candidates = candidate_offenses(intake["summary"], bank, gate1)
    acts = extract_acts(gate1)
    link_acts_to_candidates(acts, candidates)
    competition_relationships(candidates)
    case = {
        "case_id": str(uuid4()),
        "state": "GATE1_REVIEW",
        "intake": intake,
        "gate1": gate1,
        "acts": acts,
        "people": [],
        "candidates": candidates,
        "alternative_routes": alternative_legal_routes(gate1),
        "fact_updates": [],
        "fact_overlay": {},
        "candidates_source": "rules",
        "selected_offenses": [],
        "selected_legal_routes": [],
        "legal_route_review": None,
        "route_selection_status": "PENDING",
        "question_coverage_by_route": None,
        "route_fact_observations": {},
        "route_fact_overlay": {},
        "selected_legal_route_states": {},
        "question_role": "victim" if has_victim else "transfer",
        "questions": [],
        "interviews": {},
        "profiles": {},
        "interview_sessions": {},
        "case_numbers": {},
        "brief_summary": truncate_summary(intake["summary"], MAX_SUMMARY_LENGTH),
        "approvals": {},
        "documents": [],
        "snapshots": [],
        "audit": [],
        "versions": {
            "question_bank": bank["library_version"],
            "template": CURRENT_TEMPLATE_VERSION,
            "candidate_engine": CURRENT_CANDIDATE_ENGINE,
            "legal_route_crosswalk": bank["legal_route_crosswalk_version"],
        },
    }
    _audit(case, "CASE_CREATED", to_state=case["state"])
    return case


def _approval(case: dict[str, Any], gate: str, role: str = "operator") -> dict[str, Any]:
    return {
        "at": _now(),
        "role": role,
        "case_revision_hash": revision_hash(case),
        "question_bank_version": case["versions"]["question_bank"],
        "template_version": case["versions"]["template"],
    }


def _sync_versions(case: dict[str, Any], bank: dict[str, Any]) -> None:
    """同步目前治理版本；任何漂移都使既有下游核准失效。"""
    current = {
        "question_bank": bank["library_version"],
        "template": CURRENT_TEMPLATE_VERSION,
        "candidate_engine": CURRENT_CANDIDATE_ENGINE,
        "legal_route_crosswalk": bank["legal_route_crosswalk_version"],
    }
    if case.setdefault("versions", {}) != current:
        case["versions"] = current
        _invalidate(case, "gate1")
        case["state"] = "GATE1_REVIEW"


def _clean_fact(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise WorkflowError("facts 每一項必須是物件")
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            cleaned[key] = _clean_text(value, f"facts.{key}", required=False)
        elif isinstance(value, list):
            if any(not isinstance(item, str) for item in value):
                raise WorkflowError(f"facts.{key} 必須是文字陣列")
            cleaned[key] = [_clean_text(item, f"facts.{key}", required=False) for item in value]
        elif value is None or isinstance(value, (bool, int, float)):
            cleaned[key] = value
        else:
            raise WorkflowError(f"facts.{key} 格式錯誤")
    machine_status = cleaned.get("machine_status")
    if machine_status is not None and machine_status not in MACHINE_STATUSES:
        raise WorkflowError("facts.machine_status 必須是 FACT、INFERENCE、UNKNOWN 或 DISPUTED")
    if machine_status is None:
        cleaned["machine_status"] = "UNKNOWN" if cleaned.get("fact_status") in {"未知", "UNKNOWN"} else "FACT"
    return cleaned


def _clean_short_mapping(values: dict[str, Any], field: str) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(value, str):
            raise WorkflowError(f"{field}.{key} 必須是文字")
        normalized = value.strip()
        if len(normalized) > MAX_PROFILE_FIELD_LENGTH:
            raise WorkflowError(f"{field}.{key} 超過 {MAX_PROFILE_FIELD_LENGTH} 字")
        cleaned[key] = normalized
    return cleaned


def _resolve_legal_routes(
    bank: dict[str, Any], offense_ids: list[str], route_ids: list[str]
) -> list[dict[str, str]]:
    offenses = {item["id"]: item for item in bank["offenses"]}
    selected_offenses = set(offense_ids)
    available: dict[str, tuple[str, dict[str, Any]]] = {}
    excluded: set[str] = set()
    for offense_id, offense in offenses.items():
        for route in offense.get("legal_routes", []):
            available[route["id"]] = (offense_id, route)
        excluded.update(item["id"] for item in offense.get("excluded_legal_routes", []))

    snapshots: list[dict[str, str]] = []
    selected_by_parent: dict[str, int] = {}
    for route_id in route_ids:
        if route_id in excluded:
            raise WorkflowError(f"法律路由已停用或排除：{route_id}")
        pair = available.get(route_id)
        if pair is None:
            raise WorkflowError(f"包含未知法律路由：{route_id}")
        parent_id, route = pair
        if parent_id not in selected_offenses:
            raise WorkflowError(f"法律路由不屬於已選候選罪章：{route_id}")
        if offenses[parent_id].get("selection_policy", "OPTIONAL") == "NOT_APPLICABLE":
            raise WorkflowError(f"候選罪章不適用子法律路由選擇：{parent_id}")
        if route.get("review_status") != "HUMAN_REVIEW_REQUIRED":
            raise WorkflowError(f"法律路由狀態不可使用：{route_id}")
        selected_by_parent[parent_id] = selected_by_parent.get(parent_id, 0) + 1
        snapshots.append({
            "route_id": route_id,
            "parent_offense_id": parent_id,
            "route_kind": str(route.get("route_kind", "")),
            "name": str(route.get("name", "")),
            "crosswalk_version": bank["legal_route_crosswalk_version"],
            "review_status": str(route.get("review_status", "")),
        })

    for offense_id in offense_ids:
        policy = offenses[offense_id].get("selection_policy", "OPTIONAL")
        if policy == "REQUIRED" and not selected_by_parent.get(offense_id):
            raise WorkflowError(f"候選罪章 {offense_id} 必須選擇至少一個法律路由")
    return snapshots


def _validate_legal_route_review(case: dict[str, Any], bank: dict[str, Any]) -> None:
    review = case.get("legal_route_review")
    if not isinstance(review, dict) or review.get("confirmed") is not True:
        raise WorkflowError("尚未完成法律路由人工檢視")
    if review.get("crosswalk_version") != bank["legal_route_crosswalk_version"]:
        raise WorkflowError("法律路由版本已變更，必須重新檢視")
    snapshots = case.get("selected_legal_routes")
    if not isinstance(snapshots, list):
        raise WorkflowError("法律路由選擇資料缺漏")
    route_ids = [item.get("route_id") for item in snapshots if isinstance(item, dict)]
    if len(route_ids) != len(snapshots) or any(not isinstance(item, str) for item in route_ids):
        raise WorkflowError("法律路由選擇資料格式錯誤")
    _resolve_legal_routes(bank, case.get("selected_offenses", []), route_ids)


def apply_action(
    case: dict[str, Any], action: str, payload: dict[str, Any], bank: dict[str, Any]
) -> dict[str, Any]:
    if case.get("state") not in ALLOWED_STATES:
        raise WorkflowError("案件狀態無效")
    _sync_versions(case, bank)
    previous_state = case["state"]

    if action == "update_gate1":
        if case["state"] not in {"GATE1_REVIEW", "GATE2_QA", "CASE_NUMBERS", "OUTPUT_READY"}:
            raise WorkflowError("目前不可修改 Gate 1")
        incoming = payload.get("gate1")
        if not isinstance(incoming, dict):
            raise WorkflowError("缺少 Gate 1 資料")
        gate1 = deepcopy(case.get("gate1", {}))
        for key in ("people", "events", "times", "places", "objects", "behaviors", "results", "evidence", "unknowns"):
            if key not in incoming:
                continue
            values = incoming[key]
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                raise WorkflowError(f"{key} 必須是文字陣列")
            gate1[key] = [_clean_text(item, key) for item in values]
        if "facts" in incoming:
            facts = incoming["facts"]
            if not isinstance(facts, list):
                raise WorkflowError("facts 必須是陣列")
            if len(facts) > MAX_FACTS:
                raise WorkflowError(f"facts 不得超過 {MAX_FACTS} 項")
            gate1["facts"] = [_clean_fact(item) for item in facts]
        if "causation" in incoming:
            gate1["causation"] = _clean_text(incoming["causation"], "因果關係")
        elif "causation" not in gate1:
            gate1["causation"] = "UNKNOWN"
        if "facts" in incoming:
            source_facts = [
                item for item in gate1.get("facts", [])
                if not item.get("fact_key") and item.get("machine_status") != "UNKNOWN"
            ]
            gate1["events"] = list(dict.fromkeys(
                str(item.get("source_excerpt") or item.get("normalized_text") or "").strip()
                for item in source_facts
                if str(item.get("source_excerpt") or item.get("normalized_text") or "").strip()
            ))
            gate1["people"] = list(dict.fromkeys(str(item.get("subject", "")).strip() for item in gate1["facts"] if str(item.get("subject", "")).strip()))
            gate1["objects"] = list(dict.fromkeys(str(item.get("object", "")).strip() for item in gate1["facts"] if str(item.get("object", "")).strip()))
            gate1["results"] = list(dict.fromkeys(str(item.get("result", "")).strip() for item in gate1["facts"] if str(item.get("result", "")).strip()))
            gate1["evidence"] = list(dict.fromkeys(str(item.get("value", "")).strip() for item in gate1["facts"] if item.get("fact_key") == "evidence" and str(item.get("value", "")).strip()))
            gate1["behaviors"] = list(dict.fromkeys(str(item.get("action", "")).strip() for item in gate1["facts"] if str(item.get("action", "")).strip()))
        separator = "" if "facts" in incoming else "；"
        current_summary = separator.join(gate1.get("events", []))
        # Gate 1 更新的是條陳摘要來源，超過 500 字必須拒絕，
        # 不得靜默截斷造成事實遺失；初始輸入仍可不限字數，僅由 brief_summary 截成 500 字。
        validated_summary = concise_summary(current_summary, MAX_SUMMARY_LENGTH) if current_summary.strip() else ""
        if "events" in incoming and "facts" not in incoming and current_summary.strip():
            refreshed = analyze_gate1({
                **case["intake"],
                "summary": current_summary,
                "location": gate1.get("places", [case["intake"]["location"]])[0],
            }, use_ai=False)
            gate1["facts"] = refreshed["facts"]
            gate1["unknowns"] = refreshed["unknowns"]
            gate1["segmentation_source"] = refreshed["segmentation_source"]
        if "times" in incoming:
            case["intake"]["event_time"] = gate1["times"][0] if gate1["times"] else "UNKNOWN"
        if "places" in incoming:
            case["intake"]["location"] = gate1["places"][0] if gate1["places"] else "UNKNOWN"
        case["gate1"] = gate1
        case["acts"] = extract_acts(gate1)
        if current_summary.strip():
            case["intake"]["summary"] = current_summary
            case["brief_summary"] = validated_summary
            case["candidates"] = candidate_offenses(current_summary, bank, gate1)
            case["alternative_routes"] = alternative_legal_routes(gate1)
            link_acts_to_candidates(case["acts"], case["candidates"])
            competition_relationships(case["candidates"])
        case["fact_updates"] = []
        case["fact_overlay"] = {}
        # 行為日或罪章一旦變動，先前的行為時法判定即失效；罪章選擇已由
        # _invalidate 清空，這裡必須一併清掉，避免舊判定跟著新案情顯示。
        case["temporal_law_warnings"] = []
        case["law_version_audits"] = []
        case["law_version_summary"] = None
        case["state"] = "GATE1_REVIEW"
        _invalidate(case, "gate1")

    elif action == "auto_prepare":
        if case["state"] != "GATE1_REVIEW":
            raise WorkflowError("目前不可自動分析")
        primary: list[dict[str, Any]] = []
        route_ids: list[str] = []
        for item in case.get("candidates", []):
            if item.get("selection_origin") == "related_hint":
                continue
            if item.get("candidate_eligibility") != "ELIGIBLE_CANDIDATE":
                continue
            route_states = item.get("legal_route_states") or {}
            eligible_routes = [
                route_id for route_id in item.get("suggested_legal_route_ids") or []
                if route_states.get(route_id) == "ELIGIBLE_CANDIDATE"
            ]
            # 構成要件矩陣不適用（程序／保護令類路線，states 為空）時仍可自動選取；
            # 但矩陣適用卻沒有任何路線達到門檻者，只代表關鍵詞命中，不足以代表本案方向。
            # 這種候選若一併自動選取，會連帶產生整組無關問句
            # （例：「強制採驗尿液許可書」命中妨害自由、「下注」命中賭博）。
            if route_states and not eligible_routes:
                continue
            primary.append(item)
            if eligible_routes:
                route_ids.append(eligible_routes[0])
            if len(primary) >= MAX_SELECTED_OFFENSES:
                break
        if not primary:
            raise WorkflowError("目前摘要不足以產生候選罪章，請補充可辨識的事件、行為或結果")
        offense_ids = [item["id"] for item in primary]
        case["state"] = "GATE2_QA"
        case = apply_action(case, "set_offenses", {
            "offense_ids": offense_ids,
            "legal_route_ids": route_ids,
            "route_review_confirmed": True,
            "role": case.get("question_role", "victim" if case["intake"].get("has_victim") else "transfer"),
        }, bank)
        case["preparation_mode"] = "SYSTEM_AUTO_PREPARED_HUMAN_REVIEW_REQUIRED"
        case["preparation_notice"] = "系統已依摘要自動整理候選罪章、法律路由與問句。請直接審核結果，必要時再修改。"

    elif action == "approve_gate1":
        if case["state"] != "GATE1_REVIEW" or payload.get("confirmed") is not True:
            raise WorkflowError("Gate 1 必須由使用者明確確認")
        case["approvals"]["gate1"] = _approval(case, "gate1")
        case["state"] = "GATE2_QA"

    elif action == "set_offenses":
        if case["state"] != "GATE2_QA":
            raise WorkflowError("目前不可選擇候選罪章")
        offense_ids = payload.get("offense_ids")
        if not isinstance(offense_ids, list) or not offense_ids:
            raise WorkflowError("至少由人工選擇一個候選罪章")
        valid = {item["id"] for item in bank["offenses"]}
        if any(item not in valid for item in offense_ids):
            raise WorkflowError("包含未知罪章")
        role = payload.get("role", case["question_role"])
        if role not in {"victim", "suspect", "transfer"}:
            raise WorkflowError("不支援的問句身分")
        selected = list(dict.fromkeys(offense_ids))
        if len(selected) > MAX_SELECTED_OFFENSES:
            raise WorkflowError(f"候選方向最多選擇 {MAX_SELECTED_OFFENSES} 個，請先由承辦人縮小範圍")
        if payload.get("route_review_confirmed") is not True:
            raise WorkflowError("必須明確完成法律路由人工檢視")
        route_ids = payload.get("legal_route_ids")
        if not isinstance(route_ids, list) or any(not isinstance(item, str) for item in route_ids):
            raise WorkflowError("法律路由必須是文字陣列")
        if len(route_ids) != len(set(route_ids)):
            raise WorkflowError("法律路由不得重複")
        route_snapshots = _resolve_legal_routes(bank, selected, route_ids)
        previous_route_ids = [
            item.get("route_id") for item in case.get("selected_legal_routes", [])
            if isinstance(item, dict)
        ]
        same_question_context = (
            case.get("selected_offenses") == selected
            and case.get("question_role") == role
            and sorted(previous_route_ids) == sorted(route_ids)
            and (case.get("legal_route_review") or {}).get("crosswalk_version")
                == bank["legal_route_crosswalk_version"]
        )
        prior = (
            {
                item["id"]: {
                    "answer": item.get("answer", ""),
                    "answer_code": item.get("answer_code", "UNKNOWN"),
                }
                for item in case.get("questions", [])
            }
            if same_question_context else {}
        )

        # 先完成問句 materialization；失敗時不得先清除既有題目或答案。
        confirmed_at = _now()
        built_questions = build_questions(
            bank,
            role,
            selected,
            gate1=case.get("gate1", {}),
            candidates=case.get("candidates", []),
            legal_route_ids=route_ids,
            materialized_at=confirmed_at,
        )
        for question in built_questions:
            question.setdefault("meta", {})["route_context_ids"] = deepcopy(route_ids)
        built_coverage = deepcopy(getattr(build_questions, "question_coverage_by_route", None))
        built_quality_checks = deepcopy(getattr(build_questions, "last_validation", {}))
        pruned = deepcopy(getattr(build_questions, "pruned_questions", []))

        # offense、route 與 questions 在所有驗證通過後才原子寫入。
        case["selected_offenses"] = selected
        case["selected_legal_routes"] = route_snapshots
        case["legal_route_review"] = {
            "confirmed": True,
            "confirmed_at": confirmed_at,
            "crosswalk_version": bank["legal_route_crosswalk_version"],
        }
        case["route_selection_status"] = "SELECTED" if route_snapshots else "REVIEWED_NONE_SELECTED"
        case["question_role"] = role
        case["questions"] = built_questions
        case["question_coverage_by_route"] = built_coverage
        case["question_quality_checks"] = built_quality_checks
        case["question_budget_warnings"] = ([{
            "level": "BUDGET_PRUNED",
            "pruned_count": len(pruned),
            "pruned_questions": pruned,
            "message": "選配問句超出預算並已記錄；必要核心題不得裁除。",
        }] if pruned else [])

        # 被移出訪談頻道的公司套表題是參考資料，不是本庫題；
        # 逐筆保留原因供承辦人核對，並在稽核軌跡留下扣留筆數。
        case["question_quarantine"] = xlsm_quarantine()
        _audit(
            case,
            "QUESTION_QUARANTINE",
            role=role,
            reason_code="QUESTION_HYGIENE",
            quarantine_count=len(case["question_quarantine"]),
        )

        from .law_reference import (
            check_constitutional_validity,
            check_event_time_against_law,
            parse_article_spec,
        )
        from . import law_version

        temporal_warnings: list[dict[str, Any]] = []
        constitutional_warnings: list[dict[str, Any]] = []
        articles_by_offense: list[tuple[str, list[tuple[str, str]]]] = []
        event_time = case.get("intake", {}).get("event_time", "")
        offenses = {item["id"]: item for item in bank["offenses"]}
        for offense_id in selected:
            source = offenses[offense_id].get("source", {})
            warning = check_event_time_against_law(event_time, source.get("law_modified_date", ""))
            if warning:
                temporal_warnings.append({"offense_id": offense_id, **warning})
            articles = [(source.get("law_name", ""), source.get("article_no", ""))]
            articles.extend(
                (item.get("law_name", ""), item.get("article_no", ""))
                for item in source.get("related_articles", [])
            )
            articles_by_offense.append((offense_id, articles))
            for law_name, article_no in articles:
                invalidated = check_constitutional_validity(law_name, article_no)
                if invalidated:
                    constitutional_warnings.append({
                        "offense_id": offense_id,
                        "law_name": law_name,
                        "article_no": article_no,
                        **invalidated,
                    })
        case["temporal_law_warnings"] = temporal_warnings
        case["constitutional_warnings"] = constitutional_warnings

        # 行為時法：把「現行法核實」升級為「這條在行為日是哪一版」。只讀官方沿革
        # 快照，不重建歷史條文；資料不可用時明示未完成，不得當成「無須調閱」。
        law_version_audits: list[dict[str, Any]] = []
        audit_skipped: list[str] = []
        truncated = False
        if event_time:
            try:
                audit_snapshot = law_version.get_snapshot()
            except Exception as exc:  # 快照缺失、毀損或格式不符
                audit_snapshot = None
                audit_failure = type(exc).__name__
            else:
                audit_failure = ""
            if audit_snapshot is None:
                case["law_version_audits"] = []
                case["law_version_summary"] = law_version.unavailable_summary(
                    event_time, audit_failure
                )
                _audit(
                    case,
                    "LAW_VERSION_AUDIT_UNAVAILABLE",
                    role=role,
                    reason_code="LAW_VERSION_SNAPSHOT_UNAVAILABLE",
                    schema_version=law_version.SUMMARY_SCHEMA,
                )
            else:
                pending: list[tuple[str, str]] = []
                seen_pairs: set[tuple[str, str]] = set()
                for offense_id, articles in articles_by_offense:
                    for law_name, article_no in articles:
                        if not law_version.matches_law(law_name):
                            continue
                        expanded = parse_article_spec(article_no)
                        if not expanded:
                            audit_skipped.append(f"{law_name}{article_no}")
                            continue
                        for spec in expanded:
                            pair = (offense_id, spec)
                            if pair in seen_pairs:
                                continue
                            seen_pairs.add(pair)
                            pending.append(pair)
                if len(pending) > MAX_VERSION_AUDIT_ARTICLES:
                    audit_skipped.extend(
                        f"第{spec}條" for _, spec in pending[MAX_VERSION_AUDIT_ARTICLES:]
                    )
                    pending = pending[:MAX_VERSION_AUDIT_ARTICLES]
                    truncated = True
                if pending:
                    results = law_version.audit_articles(
                        audit_snapshot, event_time, [spec for _, spec in pending]
                    )
                    for (offense_id, _), audit in zip(pending, results):
                        entry = dict(audit)
                        entry["offense_id"] = offense_id
                        entry["article_no"] = f"第{audit.get('article')}條"
                        law_version_audits.append(entry)
                case["law_version_audits"] = law_version_audits
                case["law_version_summary"] = law_version.summarize(
                    law_version_audits, event_time, audit_snapshot
                )
                if audit_skipped or truncated:
                    case["law_version_summary"]["skipped"] = audit_skipped
                    case["law_version_summary"]["truncated"] = truncated
                _audit(
                    case,
                    "LAW_VERSION_AUDIT",
                    role=role,
                    reason_code="LAW_VERSION_SNAPSHOT_READ",
                    schema_version=law_version.SUMMARY_SCHEMA,
                )
        else:
            case["law_version_audits"] = []
            case["law_version_summary"] = law_version.unavailable_summary(
                "", "EVENT_TIME_MISSING"
            )
        for item in case["questions"]:
            prior_item = prior.get(item["id"], {})
            item["answer"] = prior_item.get("answer", item.get("answer", ""))
            if item.get("meta", {}).get("answer_map"):
                item["answer_code"] = prior_item.get("answer_code", "UNKNOWN")
        from .questions import reevaluate_legal_routes_from_answers
        route_result = reevaluate_legal_routes_from_answers(case)
        case.update(route_result)
        case["approvals"].pop(f"gate2:{role}", None)
        case["interviews"].pop(f"{role}:default", None)
        _invalidate(case, "gate2")

        # F32: set_offenses post-verification
        # 欄位級驗證：確保 set_offenses 後問題已正確載入
        if not case.get("questions"):
            raise WorkflowError("set_offenses 後問題未載入，build_questions 可能失敗")

    elif action == "save_profile":
        if case["state"] != "GATE2_QA" or not case.get("question_role"):
            raise WorkflowError("請先選擇本次筆錄身分")
        role = case["question_role"]
        if payload.get("role", role) != role:
            raise WorkflowError("身分與目前問答不一致")
        values = payload.get("profile")
        if not isinstance(values, dict):
            raise WorkflowError("年籍資料格式錯誤")
        session = payload.get("session")
        if session is not None and not isinstance(session, dict):
            raise WorkflowError("詢問時間格式錯誤")
        cleaned_values = _clean_short_mapping(values, "年籍資料")
        case["profiles"][f"{role}:default"] = copy_identity(cleaned_values)
        if isinstance(session, dict):
            cleaned_session = _clean_short_mapping(session, "詢問時間")
            case["interview_sessions"][f"{role}:default"] = {
                "start_time": cleaned_session.get("start_time", ""),
                "end_time": cleaned_session.get("end_time", ""),
                "location": cleaned_session.get("location", ""),
            }
        case["approvals"].pop(f"gate2:{role}", None)
        case["interviews"].pop(f"{role}:default", None)
        _invalidate(case, "gate2")

    elif action == "save_answers":
        if case["state"] != "GATE2_QA" or not case["questions"]:
            raise WorkflowError("請先選擇候選罪章")
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise WorkflowError("回答格式錯誤")
        valid_ids = {item["id"] for item in case["questions"]}
        if set(answers) - valid_ids:
            raise WorkflowError("包含未知題號")
        answer_codes = payload.get("answer_codes", {})
        if not isinstance(answer_codes, dict) or set(answer_codes) - valid_ids:
            raise WorkflowError("回答狀態格式錯誤")
        questions_by_id = {item["id"]: item for item in case["questions"]}
        for question_id, value in answer_codes.items():
            answer_map = questions_by_id[question_id].get("meta", {}).get("answer_map")
            if not isinstance(answer_map, dict) or value not in answer_map:
                raise WorkflowError(f"回答狀態不符合題目快照：{question_id}")
        for item in case["questions"]:
            if item["id"] in answers:
                item["answer"] = _clean_text(answers[item["id"]], "回答", required=False)
                item["status"] = "ANSWERED" if item["answer"] else "PENDING"
            if item["id"] in answer_codes and item.get("meta", {}).get("answer_map"):
                item["answer_code"] = answer_codes[item["id"]]
        case["approvals"].pop(f"gate2:{case['question_role']}", None)
        case["interviews"].pop(f"{case['question_role']}:default", None)
        _invalidate(case, "gate2")
        from .questions import reevaluate_candidates_from_answers
        reevaluated = reevaluate_candidates_from_answers(case, bank)
        case["candidates"] = reevaluated["candidates"]
        case["candidate_contradictions"] = reevaluated["contradictions"]
        case["fact_updates"] = reevaluated["fact_updates"]
        case["fact_overlay"] = reevaluated["fact_overlay"]
        from .questions import reevaluate_legal_routes_from_answers
        route_result = reevaluate_legal_routes_from_answers(case)
        case.update(route_result)

    elif action == "approve_gate2":
        if case["state"] != "GATE2_QA" or payload.get("confirmed") is not True:
            raise WorkflowError("Gate 2 必須由使用者明確確認")
        if not case["selected_offenses"]:
            raise WorkflowError("尚未確認候選罪章")
        _validate_legal_route_review(case, bank)
        role = case.get("question_role")
        if role not in {"victim", "suspect", "transfer"}:
            raise WorkflowError("請先選擇本次筆錄身分")
        unanswered = [
            item["id"] for item in case["questions"]
            if not item.get("answer", "").strip()
            and not item.get("meta", {}).get("known_from_summary")
        ]
        if unanswered:
            raise WorkflowError("所有問句均須作答；不清楚時請明確填寫 UNKNOWN")
        profile = case.get("profiles", {}).get(f"{role}:default", {})
        if not profile.get("name", "").strip():
            raise WorkflowError("缺少受詢問人姓名")
        if role in {"suspect", "transfer"}:
            session = case.get("interview_sessions", {}).get(f"{role}:default", {})
            if not session.get("start_time") or not session.get("end_time"):
                raise WorkflowError("缺少詢問起訖時間")
        interview_id = f"{role}:default"
        if interview_id in case["interviews"]:
            _snapshot(case, f"replace_interview:{role}")
        interview = {
            "interview_id": interview_id,
            "role": role,
            "selected_offenses": deepcopy(case["selected_offenses"]),
            "selected_legal_routes": deepcopy(case["selected_legal_routes"]),
            "route_selection_status": case["route_selection_status"],
            "legal_route_review": deepcopy(case["legal_route_review"]),
            "question_coverage_by_route": deepcopy(case["question_coverage_by_route"]),
            "route_fact_observations": deepcopy(case.get("route_fact_observations", {})),
            "route_fact_overlay": deepcopy(case.get("route_fact_overlay", {})),
            "selected_legal_route_states": deepcopy(case.get("selected_legal_route_states", {})),
            "questions": deepcopy(case["questions"]),
            "approved_at": _now(),
            "case_revision_hash": revision_hash(case),
            "question_bank_version": case["versions"]["question_bank"],
        }
        case["interviews"][interview_id] = interview
        case["approvals"][f"gate2:{role}"] = _approval(case, "gate2", role)
        case["state"] = "OUTPUT_READY" if case.get("case_numbers", {}).get("proof") else "CASE_NUMBERS"

    elif action == "save_case_numbers":
        if case["state"] not in {"CASE_NUMBERS", "OUTPUT_READY"}:
            raise WorkflowError("目前不可填寫案號")
        values = payload.get("case_numbers", {})
        if not isinstance(values, dict):
            raise WorkflowError("案號格式錯誤")
        required = required_case_numbers(case)
        cleaned = {key: _clean_text(values.get(key, ""), key, required=False) for key in ("proof", "women_child", "case_165")}
        missing = [key for key in required if not cleaned.get(key)]
        if missing:
            raise WorkflowError("缺少必要案號：" + "、".join(missing))
        if case["state"] == "OUTPUT_READY":
            _snapshot(case, "before_case_number_correction")
        case["case_numbers"] = cleaned
        case["approvals"]["case_numbers"] = _approval(case, "case_numbers")
        case["state"] = "OUTPUT_READY"

    elif action == "reopen":
        if case["state"] != "OUTPUT_READY":
            raise WorkflowError("只有已完成案件可重新開啟")
        _snapshot(case, "reopen_from_output")
        case["state"] = "GATE1_REVIEW"
        _invalidate(case, "gate1")

    elif action == "analyze_candidates":
        if case["state"] != "GATE2_QA":
            raise WorkflowError("目前不可重新分析候選罪章")
        if payload.get("external_ai_consent") is not True:
            raise WorkflowError("外部 AI 分析必須由承辦人明確同意")
        summary = payload.get("summary", case["intake"]["summary"])
        if not isinstance(summary, str) or not summary.strip():
            raise WorkflowError("案情摘要不得空白")
        clean_summary = _clean_summary(summary)
        offense_catalog = [
            {"id": item["id"], "name": item["name"]} for item in bank["offenses"]
        ]
        source_snapshot_hashes = {
            "question_bank": canonical_sha256({"version": bank["library_version"]}),
            "legal_route_crosswalk": canonical_sha256(
                {"version": bank["legal_route_crosswalk_version"]}
            ),
            "offense_catalog": canonical_sha256(offense_catalog),
        }
        result = analyze_candidates_v3(
            clean_summary,
            offense_catalog,
            case_revision=int(case.get("revision", 0)),
            source_snapshot_hashes=source_snapshot_hashes,
        )
        rule_candidates = candidate_offenses(clean_summary, bank)
        if result is None:
            # 外部 AI 不可用時仍回傳可回查的規則候選；不把失敗轉成空候選。
            fallback = classify_candidates(clean_summary, bank)
            rule_candidates = fallback["candidates"]
            result = {
                "candidates": [],
                "status": fallback["status"],
                "model": "rules-fallback",
                "contract": {
                    "schema_version": "rules-fallback-v1",
                    "request_id": "rules-fallback",
                    "input_hash": canonical_sha256({"case_text": clean_summary}),
                    "source_snapshot_hashes": source_snapshot_hashes,
                    "attempt_count": 0,
                },
            }
        by_id = {item["id"]: item for item in bank["offenses"]}
        merged = {item["id"]: item for item in rule_candidates}
        for item in merged.values():
            item["candidate_sources"] = ["rules"]
        for item in result["candidates"]:
            offense = by_id[item["id"]]
            if item["id"] in merged:
                candidate = merged[item["id"]]
                candidate["candidate_sources"].append("ai")
                candidate["notice"] = f"AI 候選（{item['reason']}）；規則亦命中；不代表犯罪成立。"
                candidate["inclusion_reason"] = item["reason"] or candidate.get("inclusion_reason", "")
                candidate["classification_basis"] = {
                    "quote": item["basis_quote"],
                    "start": item["basis_start"],
                    "end": item["basis_end"],
                }
                candidate["classification_missing"] = item["missing"]
                continue
            element_labels, candidate_status, element_status = candidate_element_state(offense)
            merged[item["id"]] = {
                "id": item["id"],
                "candidate_id": f"candidate:{item['id']}",
                "name": offense["name"],
                "matched_terms": [],
                "status": candidate_status,
                "notice": f"AI 候選（{item['reason']}）；不代表犯罪成立。",
                "inclusion_reason": item["reason"] or "AI 建議列入人工區辨",
                "reservation_reason": "AI 僅提供候選方向，仍須由承辦人逐項確認",
                "supporting_fact_refs": ["intake.summary"],
                "contradicting_fact_refs": [],
                "unknown_elements": element_labels,
                "element_model_status": element_status,
                "route_type": offense.get("route_type", "substantive"),
                "crosswalk_status": offense.get("crosswalk_status", "SPLIT_REQUIRED"),
                "legal_routes": deepcopy(offense.get("legal_routes", [])),
                "excluded_legal_routes": deepcopy(offense.get("excluded_legal_routes", [])),
                "legal_route_selection_status": offense.get("selection_policy", "OPTIONAL"),
                "distinguishing_question_ids": ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
                "required_evidence_question_ids": ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
                "competition_analysis": "待人工評估",
                "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
                "candidate_sources": ["ai"],
                "classification_basis": {
                    "quote": item["basis_quote"],
                    "start": item["basis_start"],
                    "end": item["basis_end"],
                },
                "classification_missing": item["missing"],
                "source": offense["source"],
            }
        case["candidates_source"] = "ai+rules" if result["model"] != "rules-fallback" else "rules"
        case["candidate_classification_status"] = result["status"]
        case["candidate_analysis_contract"] = deepcopy(result["contract"])
        ai_order = [item["id"] for item in result["candidates"]]
        remaining = [item for oid, item in merged.items() if oid not in ai_order]
        case["candidates"] = [merged[oid] for oid in ai_order if oid in merged] + remaining
        link_acts_to_candidates(case.get("acts", []), case["candidates"])
        competition_relationships(case["candidates"])
        contract = result["contract"]
        _audit(
            case,
            "AI_ANALYZE",
            rule_id=result["model"],
            schema_version=contract["schema_version"],
            request_id=contract["request_id"],
            input_hash=contract["input_hash"],
            source_snapshot_hashes=contract["source_snapshot_hashes"],
            attempt_count=contract["attempt_count"],
        )

    elif action == "start_interview":
        if case["state"] != "OUTPUT_READY":
            raise WorkflowError("只有完成目前輸出的案件可新增筆錄")
        role = payload.get("role")
        if role not in {"victim", "suspect", "transfer"}:
            raise WorkflowError("不支援的問句身分")
        if role == "transfer" and case["intake"]["has_victim"]:
            raise WorkflowError("有被害人案件不可使用無被害人移送分支")
        if role == "victim" and not case["intake"]["has_victim"]:
            raise WorkflowError("無被害人案件不可使用被害人分支")
        if role == "suspect" and not case["intake"]["has_victim"]:
            raise WorkflowError("無被害人案件請使用移送分支")
        case["question_role"] = role
        prior = case["interviews"].get(f"{role}:default", {})
        case["selected_offenses"] = deepcopy(prior.get("selected_offenses", []))
        case["selected_legal_routes"] = deepcopy(prior.get("selected_legal_routes", []))
        case["legal_route_review"] = deepcopy(prior.get("legal_route_review"))
        case["route_selection_status"] = prior.get("route_selection_status", "PENDING")
        case["question_coverage_by_route"] = deepcopy(prior.get("question_coverage_by_route"))
        case["route_fact_observations"] = deepcopy(prior.get("route_fact_observations", {}))
        case["route_fact_overlay"] = deepcopy(prior.get("route_fact_overlay", {}))
        case["selected_legal_route_states"] = deepcopy(prior.get("selected_legal_route_states", {}))
        case["questions"] = deepcopy(prior.get("questions", []))
        case["state"] = "GATE2_QA"
        case["documents"] = [
            item for item in case.get("documents", []) if item.get("role") != role
        ]

    else:
        raise WorkflowError("未知操作")

    _audit(
        case,
        action.upper(),
        from_state=previous_state,
        to_state=case["state"],
        role=case.get("question_role"),
        question_count=len(case.get("questions", [])),
        offense_count=len(case.get("selected_offenses", [])),
        legal_route_count=len(case.get("selected_legal_routes", [])),
    )
    return case


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(case)
    if "legal_route_review" not in result:
        result["legal_route_review"] = None
        result["selected_legal_routes"] = None
        result["route_selection_status"] = "LEGACY_MISSING"
        result["question_coverage_by_route"] = None
    result.setdefault("route_fact_observations", {})
    result.setdefault("route_fact_overlay", {})
    result.setdefault("selected_legal_route_states", {})
    result.setdefault("question_quarantine", [])
    return result


def validate_case_id(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f-]{36}", value):
        raise WorkflowError("案件 ID 格式錯誤")
    return value
