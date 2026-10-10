"""LLM-executed Gate 2 and post-answer final summary validation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pipeline.flow.checks import (
    MechanicalCheckError,
    validate_no_direct_identifiers,
    validate_questions,
    validate_required_fields,
    validate_warning_chain,
)
from pipeline.flow.intake import IntakeResult, NOT_APPLICABLE
from pipeline.flow.llm_client import LocalLLMClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAW_DB = PROJECT_ROOT / "law" / "judicial2_laws.sqlite3"
CANDIDATE_STATUSES = frozenset({"MATCHED", "NEED_REVIEW", "UNKNOWN"})
PROCEDURE_FIELDS = ("告訴狀態", "告訴期間狀態", "追訴權狀態")
QUESTION_FIELDS = (
    "核心問句",
    "判定缺少的補充問句",
    "事實釐清問句",
    "證據蒐集問句",
    "關係釐清問句",
    "時間序問句",
    "程序告知問句",
    "其他必要問句",
)
WOMEN_CHILD_LAWS = (
    "家庭暴力防治法",
    "性侵害犯罪防治法",
    "性騷擾防治法",
    "兒童及少年福利與權益保障法",
    "兒童及少年性剝削防制條例",
    "少年事件處理法",
    "跟蹤騷擾防制法",
    "性別平等工作法",
    "性別平等教育法",
    "人口販運防制法",
)
WOMEN_CHILD_WARNING = "婦幼案件，請確認代號與婦幼案號"

GATE2_SCHEMA = {
    "gate": "G2",
    "candidates": [],
    "victim_questions": [],
    "procedure_questions": [],
    "procedure_status": {field: "string" for field in PROCEDURE_FIELDS},
    "acceptance_draft": "object|null",
    "warnings": [],
}
GATE2_FINAL_SCHEMA = {"gate": "G2-FINAL", "final_summary": "string", "warnings": []}


class Gate2NotEntered(RuntimeError):
    """Raised when a route other than A attempts to enter Gate 2."""


def load_all_laws(path: Path = LAW_DB) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"法條表不存在：{path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT article_no, article_text, status FROM laws ORDER BY article_no"
        ).fetchall()
    return [
        {"article_no": article_no, "article_text": article_text, "status": status}
        for article_no, article_text, status in rows
    ]


def _question_text(output: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    for group in output["victim_questions"]:
        validate_required_fields(group, ("unit_id", "候選罪章", *QUESTION_FIELDS))
        for field in QUESTION_FIELDS:
            values = group[field]
            if not isinstance(values, list):
                raise MechanicalCheckError(f"{field} 必須為陣列")
            questions.extend(values)
    for group in output["procedure_questions"]:
        if not isinstance(group, dict):
            raise MechanicalCheckError("程序問句分組必須為物件")
        for key, values in group.items():
            if key == "unit_id":
                continue
            if not isinstance(values, list):
                raise MechanicalCheckError(f"{key} 必須為陣列")
            questions.extend(values)
    return questions


def _warning_texts(warnings: list[Any]) -> set[str]:
    return {
        warning.get("text", "") if isinstance(warning, dict) else str(warning)
        for warning in warnings
    }


def validate_gate2_output(
    output: dict[str, Any],
    *,
    gate1_output: dict[str, Any],
    intake: IntakeResult,
    laws: list[dict[str, str]],
) -> None:
    validate_required_fields(output, GATE2_SCHEMA)
    if output["gate"] != "G2":
        raise MechanicalCheckError("Gate 2 識別欄位不一致")
    for field in ("candidates", "victim_questions", "procedure_questions", "warnings"):
        if not isinstance(output[field], list):
            raise MechanicalCheckError(f"{field} 必須為陣列")
    validate_warning_chain(gate1_output["warnings"], output["warnings"])

    expected_procedure = {
        field: gate1_output["procedure_facts"][field] for field in PROCEDURE_FIELDS
    }
    if output["procedure_status"] != expected_procedure:
        raise MechanicalCheckError("Gate 2 程序狀態未原樣承接 Gate 1")

    if intake.fields["document_type"] == NOT_APPLICABLE:
        if output["acceptance_draft"] is not None:
            raise MechanicalCheckError("NOT_APPLICABLE 不得產出受理條陳")
    elif not isinstance(output["acceptance_draft"], dict):
        raise MechanicalCheckError("適用文件類型時須產出受理條陳草稿")

    law_by_article = {row["article_no"]: row for row in laws}
    question_pairs = {
        (group.get("unit_id"), group.get("候選罪章"))
        for group in output["victim_questions"]
        if isinstance(group, dict)
    }
    women_child_candidate = False
    for candidate in output["candidates"]:
        if not isinstance(candidate, dict):
            raise MechanicalCheckError("候選罪章必須為物件")
        validate_required_fields(
            candidate,
            (
                "unit_id", "案類", "法條", "法條狀態", "既遂未遂", "告訴乃論",
                "告訴乃論依據", "告訴狀態", "候選狀態", "事實基礎", "理由",
            ),
        )
        if candidate["候選狀態"] not in CANDIDATE_STATUSES:
            raise MechanicalCheckError("候選狀態值域錯誤")
        law = law_by_article.get(candidate["法條"])
        if law is None or candidate["法條狀態"] != law["status"]:
            raise MechanicalCheckError("候選法條不存在或狀態不一致")
        if law["status"] != "已確認" and candidate["候選狀態"] == "MATCHED":
            raise MechanicalCheckError("未確認法條的候選狀態不得高於 NEED_REVIEW")
        if (candidate["unit_id"], candidate["案類"]) not in question_pairs:
            raise MechanicalCheckError("每個候選罪章須有對應被害人問句")
        women_child_candidate = women_child_candidate or any(
            str(candidate["法條"]).startswith(name) for name in WOMEN_CHILD_LAWS
        )
    if women_child_candidate and WOMEN_CHILD_WARNING not in _warning_texts(output["warnings"]):
        raise MechanicalCheckError("婦幼法規候選缺少確認 warning")

    victim_ids = {unit["unit_id"] for unit in gate1_output["units"]["victim"]}
    question_ids = {group["unit_id"] for group in output["victim_questions"]}
    if not victim_ids.issubset(question_ids):
        raise MechanicalCheckError("多被害人未逐一產出問句")

    questions = _question_text(output)
    validate_questions(questions)
    validate_no_direct_identifiers(questions)


def run_gate2(
    gate1_output: dict[str, Any],
    intake: IntakeResult,
    *,
    client: LocalLLMClient,
    law_db: Path = LAW_DB,
    stub_fixture: str | None = None,
) -> dict[str, Any]:
    if gate1_output.get("route") != "A":
        raise Gate2NotEntered("路由 A 以外不進入 Gate 2")
    laws = load_all_laws(law_db)
    gate_input = {
        "gate1": {
            "units": gate1_output["units"],
            "procedure_facts": gate1_output["procedure_facts"],
            "warnings": gate1_output["warnings"],
        },
        "document_type": intake.fields["document_type"],
        "laws": laws,
    }

    def validator(output: dict[str, Any]) -> None:
        validate_gate2_output(output, gate1_output=gate1_output, intake=intake, laws=laws)

    return client.complete_json(
        system_prompt=(
            "依 JUDICIAL2 v20 第 7 節執行 Gate 2。法律判斷限於輸入的完整本地法條表。"
            "問句使用 STE100：簡短、白話、開放式，一題只要求一個回答動作。"
            "只輸出指定 JSON。"
        ),
        gate_input=gate_input,
        output_schema=GATE2_SCHEMA,
        validator=validator,
        stub_fixture=stub_fixture,
    )


def run_gate2_final(
    *,
    original_summary: str,
    gate1_output: dict[str, Any],
    gate2_output: dict[str, Any],
    answers: dict[str, str],
    client: LocalLLMClient,
    stub_fixture: str | None = None,
) -> dict[str, Any]:
    previous_warnings = gate2_output["warnings"]

    def validator(output: dict[str, Any]) -> None:
        validate_required_fields(output, GATE2_FINAL_SCHEMA)
        if output["gate"] != "G2-FINAL":
            raise MechanicalCheckError("G2-FINAL 識別欄位不一致")
        if not isinstance(output["final_summary"], str) or not output["final_summary"].strip():
            raise MechanicalCheckError("final_summary 不得為空")
        if not isinstance(output["warnings"], list):
            raise MechanicalCheckError("warnings 必須為陣列")
        validate_warning_chain(previous_warnings, output["warnings"])

    return client.complete_json(
        system_prompt=(
            "依 JUDICIAL2 v20 G2-FINAL 重寫受理報告案情摘要。"
            "保留原文與回答中的必要事實。不得新增候選以外的罪章。"
            "使用 STE100：簡明、透明、有依據且可回溯。只輸出指定 JSON。"
        ),
        gate_input={
            "original_summary": original_summary,
            "gate1_units": gate1_output["units"],
            "candidates": gate2_output["candidates"],
            "answers": answers,
            "warnings": previous_warnings,
        },
        output_schema=GATE2_FINAL_SCHEMA,
        validator=validator,
        stub_fixture=stub_fixture,
    )
