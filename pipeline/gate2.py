"""Minimal Gate 2 law-table lookup without legal judgment."""

from __future__ import annotations

import sqlite3
import re
from pathlib import Path
from typing import Any

from pipeline.offense_catalog import canonical_article_no, load_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAW_DB_PATH = PROJECT_ROOT / "law" / "judicial2_laws.sqlite3"
_NO_FACT_WARNING = "法條未收錄"
_OFFENSE_WARNING = "罪章名稱待確認"
_VICTIM_QUESTION = "請說明與本案相關的事件經過"
_REPORT_INCOMPLETE_WARNING = "受理條陳欄位未完整"


def _intake_report(
    gate1_output: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    fields = dict(gate1_output.get("fields", {}))
    offense = "、".join(
        item["offense"] for item in candidates if item.get("offense") != "UNKNOWN"
    ) or "UNKNOWN"
    values = {
        "offense": offense,
        "event_time": fields.get("event_time", "UNKNOWN"),
        "location": fields.get("location", "UNKNOWN"),
        "report_time": fields.get("report_time", "UNKNOWN"),
        "summary": fields.get("summary", "UNKNOWN"),
        "case_number": fields.get("案號", fields.get("case_number", "UNKNOWN")),
        "juvenile_case_number": fields.get("婦幼案號", "UNKNOWN"),
        "jurisdiction": fields.get("管轄單位", "UNKNOWN"),
        "officer": fields.get("受理員警", "UNKNOWN"),
    }
    required = ("offense", "event_time", "location", "report_time", "summary")
    status = "待人工核定" if all(values[key] != "UNKNOWN" for key in required) else "INCOMPLETE"
    rendered = "\n".join(
        [
            "吳興所報告：",
            f"一、案由：{values['offense']}",
            f"二、發生時間：{values['event_time']}",
            f"三、發生地點：{values['location']}",
            f"四丶報案時間：{values['report_time']}",
            f"五丶案情摘要：{values['summary']}",
            "六、處理情形：",
            f"(一)依規定受理(證明單案號：{values['case_number']}、婦幼案號：{values['juvenile_case_number']})",
            f"(二)管轄單位：{values['jurisdiction']}",
            f"(三)受理員警：{values['officer']}",
        ]
    )
    return {
        "template_id": "JUDICIAL2-條陳格式-受理報告-v1",
        "status": status,
        "route": "A",
        "candidate_count": len(candidates),
        "source_unit_ids": list(gate1_output.get("source_unit_ids", [])),
        "fields": values,
        "rendered_text": rendered,
    }


def _load_law_index() -> dict[str, dict[str, str]]:
    """Load exact article numbers and statuses from the local law table."""
    uri = f"file:{LAW_DB_PATH.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT article_no, article_text, status FROM laws"
        ).fetchall()
    return {
        article_no: {
            "article_no": article_no,
            "article_text": article_text,
            "status": status,
        }
        for article_no, article_text, status in rows
    }


def _offense_from_article_text(article_text: str) -> str:
    """Use an explicitly labelled name only; never infer one from prose."""
    match = re.search(r"罪章名稱\s*[：:]\s*([^\r\n|]+)", article_text)
    return match.group(1).strip() if match else "UNKNOWN"


def _candidates_from_explicit_facts(
    gate1_output: dict[str, Any], law_index: dict[str, dict[str, str]],
    catalog: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool, bool]:
    """Resolve each fact's article number by exact string equality."""
    facts = gate1_output.get("facts")
    if not isinstance(facts, list) or not facts:
        return [], False, False

    candidates: list[dict[str, Any]] = []
    had_unresolved_reference = False
    had_unknown_offense = False
    for fact in facts:
        if not isinstance(fact, dict):
            had_unresolved_reference = True
            continue
        article_no = fact.get("article_no")
        if not isinstance(article_no, str):
            had_unresolved_reference = True
            continue
        canonical = canonical_article_no(article_no) or article_no
        law = law_index.get(canonical)
        catalog_entries = catalog.get(canonical, [])
        if law is None and not catalog_entries:
            had_unresolved_reference = True
            continue
        if catalog_entries:
            if law is None:
                had_unresolved_reference = True
            for entry in catalog_entries:
                candidates.append(
                    {
                        "article_no": canonical,
                        "source_span": fact.get("source_span"),
                        "source_status": law["status"] if law else "CATALOG_ONLY",
                        "offense": entry["offense"],
                        "direction": law["status"] if law else "待人工核定",
                        "candidate_status": "NEED_REVIEW",
                        "charge_id": entry["charge_id"],
                        "chapter_id": entry["chapter_id"],
                        "required_elements": entry["required_elements"],
                        "catalog_verification": entry["catalog_verification"],
                        "catalog_path": entry["catalog_path"],
                    }
                )
            continue
        offense = _offense_from_article_text(law["article_text"])
        had_unknown_offense = had_unknown_offense or offense == "UNKNOWN"
        candidates.append({
            "article_no": law["article_no"],
            "source_span": fact.get("source_span"),
            "source_status": law["status"],
            "offense": offense,
            "direction": law["status"],
            "candidate_status": "NEED_REVIEW",
        })
    return candidates, had_unresolved_reference, had_unknown_offense


def run(gate1_output: dict[str, Any]) -> dict[str, Any]:
    """Accept Gate 1 output and resolve only explicit local law references."""
    if gate1_output.get("route") != "A":
        return {
            "status": "未進入 Gate 2",
            "route": gate1_output.get("route", "UNKNOWN"),
            "items": [],
            "candidates": [],
            "victim_questions": [],
            "intake_report": {"status": "未產出"},
            "warnings": list(gate1_output.get("warnings", [])),
        }

    law_index = _load_law_index()
    catalog = load_catalog()
    candidates, unresolved, unknown_offense = _candidates_from_explicit_facts(
        gate1_output, law_index, catalog
    )
    warnings = list(gate1_output.get("warnings", []))
    if unresolved:
        if _NO_FACT_WARNING not in warnings:
            warnings.append(_NO_FACT_WARNING)
    if unknown_offense and _OFFENSE_WARNING not in warnings:
        warnings.append(_OFFENSE_WARNING)
    intake_report = _intake_report(gate1_output, candidates)
    if intake_report["status"] == "INCOMPLETE" and _REPORT_INCOMPLETE_WARNING not in warnings:
        warnings.append(_REPORT_INCOMPLETE_WARNING)

    victim_questions = [
        {
            "article_no": candidate["article_no"],
            "source_span": candidate.get("source_span"),
            "questions": [_VICTIM_QUESTION],
        }
        for candidate in candidates
    ]
    return {
        "status": "已接收 Gate 1",
        "items": [],
        "route": "A",
        "candidates": candidates,
        "candidate_status": "MATCHED" if candidates and not unresolved else "UNKNOWN",
        "victim_questions": victim_questions,
        "intake_report": intake_report,
        "warnings": warnings,
    }
