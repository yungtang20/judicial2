from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .company_templates import company_questions, render_company_text
from .markdown_questions import merge_markdown_questions
from .section_questions import ordered_section_questions
from .xlsm_questions import xlsm_questions_for

MAX_OFFENSE_QUESTIONS = 30


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
    return merge_markdown_questions(bank, question_root)


def analyze_gate1(intake: dict[str, Any]) -> dict[str, Any]:
    summary = intake["summary"].strip()
    return {
        "people": [],
        "events": [summary],
        "times": [intake["event_time"]],
        "places": [intake["location"]],
        "objects": [],
        "behaviors": [],
        "causation": "UNKNOWN",
        "unknowns": ["行為人", "行為方式", "結果與行為間關係", "可供查證的證據"],
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }


def candidate_offenses(summary: str, bank: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    lowered = summary.casefold()
    by_id = {item["id"]: item for item in bank["offenses"]}
    matched_ids: set[str] = set()
    for offense in bank["offenses"]:
        hits = [keyword for keyword in offense["keywords"] if keyword.casefold() in lowered]
        if hits:
            matched_ids.add(offense["id"])
            matches.append({
                "id": offense["id"],
                "name": offense["name"],
                "matched_terms": hits,
                "status": "NEED_REVIEW",
                "notice": "僅為規則式候選，不代表犯罪成立。",
                "supporting_fact_refs": ["intake.summary"],
                "contradicting_fact_refs": [],
                "unknown_elements": [item["label"] for item in offense["elements"]],
                "source": offense["source"],
            })
    related_ids = {
        related
        for offense_id in matched_ids
        for related in by_id[offense_id].get("related", [])
        if related not in matched_ids and related in by_id
    }
    for offense_id in sorted(related_ids):
        offense = by_id[offense_id]
        matches.append({
            "id": offense["id"],
            "name": offense["name"],
            "matched_terms": [],
            "status": "NEED_REVIEW",
            "notice": "區辨用關聯候選，不代表犯罪成立。",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": [],
            "unknown_elements": [item["label"] for item in offense["elements"]],
            "source": offense["source"],
        })
    return sorted(matches, key=lambda item: (-len(item["matched_terms"]), item["name"]))


def build_questions(
    bank: dict[str, Any], role: str, offense_ids: list[str]
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

    offenses = {item["id"]: item for item in bank["offenses"]}
    for offense_id in offense_ids:
        offense = offenses.get(offense_id)
        if offense is None:
            raise RuleError(f"未知罪章：{offense_id}")
        # 1) 公司套表罪章題（新套表.xlsm 各罪章欄）
        for question in xlsm_questions_for(questions, role, offense_id):
            if question["text"] in seen:
                continue
            if _offense_questions(questions) and len(_offense_questions(questions)) >= MAX_OFFENSE_QUESTIONS:
                continue
            questions.append(question)
            seen.add(question["text"])
        # 2) md 核心與補充（含區分、加重依 section 順序）
        sections = offense.get("section_questions", {}).get(role, {})
        for question in ordered_section_questions(
            sections, role, offense_id, offense["name"], offense["source"],
        ):
            if question["text"] in seen:
                continue
            if _offense_questions(questions) and len(_offense_questions(questions)) >= MAX_OFFENSE_QUESTIONS:
                continue
            questions.append(question)
            seen.add(question["text"])
        # 3) JSON 要件題（僅在 md 未涵蓋同一 element 時補入）
        for element in offense.get("elements", []):
            if len(_offense_questions(questions)) >= MAX_OFFENSE_QUESTIONS:
                break
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


def concise_summary(text: str, limit: int = 100) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip("，、；： ") + "…"
