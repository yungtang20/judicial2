from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .config import MAX_SUMMARY_LENGTH, MAX_TEXT_LENGTH
from .ai import analyze_candidates
from .company_templates import company_questions, copy_identity, render_company_text
from .roc_time import format_roc_time
from .rules import (
    analyze_gate1,
    build_questions,
    candidate_offenses,
    concise_summary,
    required_case_numbers,
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
        raise WorkflowError(f"{field} 不���空白")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise WorkflowError(f"{field} 超過 {MAX_TEXT_LENGTH} 字")
    return normalized


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
        "question_count", "offense_count", "document_type",
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
    case["documents"] = []


def _snapshot(case: dict[str, Any], reason: str) -> None:
    case.setdefault("snapshots", []).append({
        "snapshot_id": str(uuid4()),
        "created_at": _now(),
        "reason": reason,
        "revision_hash": revision_hash(case),
        "state": case["state"],
        "interviews": deepcopy(case.get("interviews", {})),
        "case_numbers": deepcopy(case.get("case_numbers", {})),
        "approvals": deepcopy(case.get("approvals", {})),
        "versions": deepcopy(case.get("versions", {})),
    })


def create_case(raw: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    has_victim = raw.get("has_victim") is True
    intake = {
        "event_kind": _clean_text(raw.get("event_kind", "發生"), "時間類型"),
        "event_time": _clean_text(raw.get("event_time"), "發生／破獲時間"),
        "location": _clean_text(raw.get("location"), "發生／破獲地點"),
        "summary": _clean_text(raw.get("summary"), "案情摘要"),
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
    gate1 = analyze_gate1(intake)
    case = {
        "case_id": str(uuid4()),
        "state": "GATE1_REVIEW",
        "intake": intake,
        "gate1": {
            "people": gate1["people"],
            "events": gate1["events"],
            "times": gate1["times"],
            "places": gate1["places"],
            "objects": gate1["objects"],
            "behaviors": gate1["behaviors"],
            "causation": gate1["causation"],
            "unknowns": gate1["unknowns"],
            "facts": gate1["facts"],
        },
        "people": [],
        "candidates": candidate_offenses(intake["summary"], bank),
        "candidates_source": "rules",
        "selected_offenses": [],
        "question_role": "victim" if has_victim else "transfer",
        "questions": [],
        "interviews": {},
        "profiles": {},
        "interview_sessions": {},
        "case_numbers": {},
        "brief_summary": concise_summary(intake["summary"], MAX_SUMMARY_LENGTH),
        "approvals": {},
        "documents": [],
        "snapshots": [],
        "audit": [],
        "versions": {
            "question_bank": bank["library_version"],
            "template": "company-verbatim-2026-10-11",
            "candidate_engine": "rules-v2+ai",
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


def apply_action(
    case: dict[str, Any], action: str, payload: dict[str, Any], bank: dict[str, Any]
) -> dict[str, Any]:
    if case.get("state") not in ALLOWED_STATES:
        raise WorkflowError("案件狀態無效")
    previous_state = case["state"]

    if action == "update_gate1":
        if case["state"] not in {"GATE1_REVIEW", "GATE2_QA", "CASE_NUMBERS", "OUTPUT_READY"}:
            raise WorkflowError("目前不可修改 Gate 1")
        gate1 = payload.get("gate1")
        if not isinstance(gate1, dict):
            raise WorkflowError("缺少 Gate 1 資料")
        for key in ("people", "events", "times", "places", "objects", "behaviors", "unknowns"):
            values = gate1.get(key, [])
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                raise WorkflowError(f"{key} 必須是文字陣列")
            gate1[key] = [_clean_text(item, key) for item in values]
        facts = gate1.get("facts", [])
        if not isinstance(facts, list):
            raise WorkflowError("facts 必須是陣列")
        for index, fact in enumerate(facts, start=1):
            if not isinstance(fact, dict):
                raise WorkflowError(f"facts[{index}] 必須是物件")
            for field in ("id", "text", "status", "type", "source_ref"):
                if field not in fact:
                    raise WorkflowError(f"facts[{index}] 缺少 {field}")
            fact["text"] = _clean_text(str(fact.get("text", "")), f"facts[{index}].text", required=False)
            fact["status"] = str(fact.get("status", "UNKNOWN"))
            fact["type"] = str(fact.get("type", "statement"))
            fact["source_ref"] = str(fact.get("source_ref", "UNKNOWN"))
            fact["source_excerpt"] = str(fact.get("source_excerpt", fact["text"]))
        gate1["facts"] = facts
        gate1["causation"] = _clean_text(gate1.get("causation", "UNKNOWN"), "因果關係")
        case["gate1"] = gate1
        case["state"] = "GATE1_REVIEW"
        _invalidate(case, "gate1")

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
        case["selected_offenses"] = list(dict.fromkeys(offense_ids))
        case["question_role"] = role
        prior = {item["id"]: item.get("answer", "") for item in case.get("questions", [])}
        case["questions"] = build_questions(bank, role, case["selected_offenses"])
        for item in case["questions"]:
            item["answer"] = prior.get(item["id"], "")
        case["approvals"].pop(f"gate2:{role}", None)
        case["interviews"].pop(f"{role}:default", None)
        _invalidate(case, "gate2")

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
        case["profiles"][f"{role}:default"] = copy_identity(values)
        if isinstance(session, dict):
            case["interview_sessions"][f"{role}:default"] = {
                "start_time": _clean_text(session.get("start_time", ""), "詢問開始時間", required=False),
                "end_time": _clean_text(session.get("end_time", ""), "詢問結束時間", required=False),
                "location": _clean_text(session.get("location", ""), "詢問地點", required=False),
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
        for item in case["questions"]:
            if item["id"] in answers:
                item["answer"] = _clean_text(answers[item["id"]], "回答", required=False)
                item["status"] = "ANSWERED" if item["answer"] else "PENDING"
        case["approvals"].pop(f"gate2:{case['question_role']}", None)
        case["interviews"].pop(f"{case['question_role']}:default", None)
        _invalidate(case, "gate2")

    elif action == "approve_gate2":
        if case["state"] != "GATE2_QA" or payload.get("confirmed") is not True:
            raise WorkflowError("Gate 2 必須由使用者明確確認")
        if not case["selected_offenses"]:
            raise WorkflowError("尚未確認候選罪章")
        unanswered = [item["id"] for item in case["questions"] if not item.get("answer", "").strip()]
        if unanswered:
            raise WorkflowError("所有問句均須作答；不清楚時請明確填寫 UNKNOWN")
        role = case["question_role"]
        interview_id = f"{role}:default"
        if interview_id in case["interviews"]:
            _snapshot(case, f"replace_interview:{role}")
        interview = {
            "interview_id": interview_id,
            "role": role,
            "selected_offenses": deepcopy(case["selected_offenses"]),
            "questions": deepcopy(case["questions"]),
            "approved_at": _now(),
            "case_revision_hash": revision_hash(case),
            "question_bank_version": case["versions"]["question_bank"],
        }
        case["interviews"][interview_id] = interview
        case["approvals"][f"gate2:{role}"] = _approval(case, "gate2", role)
        case["state"] = "OUTPUT_READY" if case.get("case_numbers", {}).get("proof") else "CASE_NUMBERS"

    elif action == "save_case_numbers":
        if case["state"] != "CASE_NUMBERS":
            raise WorkflowError("目前不可填寫案號")
        values = payload.get("case_numbers", {})
        if not isinstance(values, dict):
            raise WorkflowError("案號格式錯誤")
        required = required_case_numbers(case)
        cleaned = {key: _clean_text(values.get(key, ""), key, required=False) for key in ("proof", "women_child", "case_165")}
        missing = [key for key in required if not cleaned.get(key)]
        if missing:
            raise WorkflowError("缺少必要案號：" + "、".join(missing))
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
        summary = payload.get("summary", case["intake"]["summary"])
        if not isinstance(summary, str) or not summary.strip():
            raise WorkflowError("案情摘要不得空白")
        result = analyze_candidates(
            _clean_text(summary, "案情摘要")[:4000],
            [{"id": item["id"], "name": item["name"]} for item in bank["offenses"]],
        )
        if result is None:
            raise WorkflowError("AI 分析無法使用（未設定金鑰或服務失敗）；請改用規則候選或人工選擇")
        by_id = {item["id"]: item for item in bank["offenses"]}
        case["candidates_source"] = "ai"
        case["candidates"] = []
        for item in result["candidates"]:
            offense = by_id[item["id"]]
            case["candidates"].append({
                "id": item["id"],
                "name": offense["name"],
                "matched_terms": [],
                "status": "NEED_REVIEW",
                "notice": f"AI 候選（{item['reason']}）；不代表犯罪成立。",
                "supporting_fact_refs": ["intake.summary"],
                "contradicting_fact_refs": [],
                "unknown_elements": [element["label"] for element in offense.get("elements", [])],
                "source": offense["source"],
            })
        _audit(case, "AI_ANALYZE", rule_id=result["model"])

    elif action == "start_interview":
        if case["state"] != "OUTPUT_READY":
            raise WorkflowError("只有完成目前輸出的案件可新增筆錄")
        role = payload.get("role")
        if role not in {"victim", "suspect", "transfer"}:
            raise WorkflowError("不支援的問句身分")
        if role == "transfer" and case["intake"]["has_victim"]:
            raise WorkflowError("有被害人案件不可使用無被害人移送分支")
        if role == "suspect" and not case["intake"]["has_victim"]:
            raise WorkflowError("無被害人案件請使用移送分支")
        case["question_role"] = role
        prior = case["interviews"].get(f"{role}:default", {})
        case["selected_offenses"] = deepcopy(prior.get("selected_offenses", []))
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
    )
    return case


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(case)


def validate_case_id(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f-]{36}", value):
        raise WorkflowError("案件 ID 格式錯誤")
    return value
