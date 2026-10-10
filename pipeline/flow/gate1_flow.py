"""LLM-executed Gate 1 with deterministic output validation."""

from __future__ import annotations

from typing import Any

from pipeline.flow.checks import (
    MechanicalCheckError,
    validate_no_direct_identifiers,
    validate_required_fields,
    validate_unique_unit_ids,
    validate_warning_chain,
)
from pipeline.flow.intake import IntakeResult
from pipeline.flow.llm_client import LocalLLMClient


ROUTES = frozenset({"A", "B", "C", "D", "E", "UNKNOWN"})
WARRANT_STATUSES = frozenset({"已附", "未附", "NOT_APPLICABLE"})
ROUTE_A_RECEPTIONS = frozenset({"受理", "告訴", "告發", "受理（依案號推定）"})
ROUTE_B_RECEPTIONS = frozenset(
    {"受理", "告訴", "告發", "查獲", "受理（依案號推定）"}
)
NO_NUMBER_RECEPTIONS = frozenset({"報案", "通報", "函送", "移送"})
PROCEDURE_FIELDS = (
    "告訴狀態",
    "告訴期間狀態",
    "追訴權狀態",
    "相關罪章檢核",
    "承辦人待辦",
)

GATE1_SCHEMA = {
    "gate": "G1",
    "case_id": "string",
    "version": "v1",
    "route": "A|B|C|D|E|UNKNOWN",
    "route_basis": {
        "受理性質": "string",
        "有被害人": "是|否|UNKNOWN",
        "刑事行為": "是|否|不明",
        "案號": "string|UNKNOWN",
        "行政裁處": "是|否|UNKNOWN",
        "依據條次": "string",
    },
    "units": {"victim": [], "actor": []},
    "procedure_facts": {field: "value" for field in PROCEDURE_FIELDS},
    "warnings": [],
    "self_check": "PASS|FAIL",
}


class Gate1Stop(RuntimeError):
    """Gate 1 requires user supplementation and must not continue."""


def _precheck_warnings(warnings: list[str]) -> list[dict[str, str]]:
    return [
        {"id": f"PRE-W{index:02d}", "source_gate": "PRECHECK", "text": text}
        for index, text in enumerate(warnings, start=1)
    ]


def expected_route_from_declared_basis(basis: dict[str, Any]) -> str:
    """Map declared fields to a route without inspecting case narrative."""
    validate_required_fields(
        basis,
        ("受理性質", "有被害人", "刑事行為", "案號", "行政裁處", "依據條次"),
    )
    reception = basis["受理性質"]
    victim = basis["有被害人"]
    criminal = basis["刑事行為"]
    case_number = basis["案號"]
    administrative = basis["行政裁處"]
    if victim not in {"是", "否", "UNKNOWN"}:
        raise MechanicalCheckError("有被害人值域錯誤")
    if criminal not in {"是", "否", "不明"}:
        raise MechanicalCheckError("刑事行為值域錯誤")
    if administrative not in {"是", "否", "UNKNOWN"}:
        raise MechanicalCheckError("行政裁處值域錯誤")
    if not reception:
        return "UNKNOWN"
    if administrative == "是":
        return "E"
    if criminal == "是" and victim == "是" and reception in ROUTE_A_RECEPTIONS:
        return "A"
    if criminal == "是" and victim == "否" and reception in ROUTE_B_RECEPTIONS:
        return "B"
    if criminal == "是" and reception in NO_NUMBER_RECEPTIONS and case_number == "UNKNOWN":
        if victim == "是":
            return "A"
        if victim == "否":
            return "B"
    if criminal == "否" and case_number != "UNKNOWN":
        return "C"
    return "D"


def _without_source_raw(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_source_raw(item)
            for key, item in value.items()
            if key != "source_raw"
        }
    if isinstance(value, list):
        return [_without_source_raw(item) for item in value]
    return value


def validate_gate1_output(
    output: dict[str, Any],
    *,
    case_id: str,
    previous_warnings: list[dict[str, str]],
    warrant: dict[str, str],
) -> None:
    validate_required_fields(output, GATE1_SCHEMA)
    if output["gate"] != "G1" or output["case_id"] != case_id:
        raise MechanicalCheckError("Gate 1 識別欄位不一致")
    if output["route"] not in ROUTES:
        raise MechanicalCheckError("路由值域錯誤")
    if output["self_check"] != "PASS":
        raise MechanicalCheckError("Gate 1 自我檢查未通過")
    if not isinstance(output["route_basis"], dict):
        raise MechanicalCheckError("route_basis 必須為物件")
    if output["route"] != expected_route_from_declared_basis(output["route_basis"]):
        raise MechanicalCheckError("宣告依據與路由不一致")
    if not isinstance(output["warnings"], list):
        raise MechanicalCheckError("warnings 必須為陣列")
    validate_warning_chain(previous_warnings, output["warnings"])
    if not isinstance(output["units"], dict):
        raise MechanicalCheckError("units 必須為物件")
    validate_unique_unit_ids(output["units"])
    for group in output["units"].values():
        for unit in group:
            validate_required_fields(unit, ("unit_id", "source_raw", "warnings"))
    procedure = output["procedure_facts"]
    if not isinstance(procedure, dict):
        raise MechanicalCheckError("procedure_facts 必須為物件")
    validate_required_fields(procedure, PROCEDURE_FIELDS)
    basis = output["route_basis"]
    if basis["受理性質"] == "備案" and basis["刑事行為"] == "是":
        if not isinstance(procedure["承辦人待辦"], list) or not procedure["承辦人待辦"]:
            raise MechanicalCheckError("備案含刑事內容時承辦人待辦不得為空")
    validate_no_direct_identifiers(_without_source_raw(output))
    if output["route"] == "B" and basis["受理性質"] == "查獲" and warrant["附件"] == "未附":
        raise Gate1Stop("通緝書未附，流程停止於 Gate 1")


def run_gate1(
    intake: IntakeResult,
    *,
    case_id: str,
    version: str,
    client: LocalLLMClient,
    warrant: dict[str, str] | None = None,
    stub_fixture: str | None = None,
) -> dict[str, Any]:
    warrant_value = warrant or {"附件": "NOT_APPLICABLE", "所載案由與罪名": ""}
    if set(warrant_value) != {"附件", "所載案由與罪名"}:
        raise ValueError("warrant 欄位不完整")
    if warrant_value["附件"] not in WARRANT_STATUSES:
        raise ValueError("通緝書附件值域錯誤")
    previous_warnings = _precheck_warnings(intake.warnings)
    gate_input = {
        "case_id": case_id,
        "version": version,
        "intake": intake.fields,
        "source_raw": intake.original_summary,
        "warrant": warrant_value,
        "warnings": previous_warnings,
    }

    def validator(output: dict[str, Any]) -> None:
        validate_gate1_output(
            output,
            case_id=case_id,
            previous_warnings=previous_warnings,
            warrant=warrant_value,
        )

    return client.complete_json(
        system_prompt=(
            "依 JUDICIAL2 v20 第 4、6、10 節執行 Gate 1。"
            "只根據輸入宣告 route_basis。受理性質空白時 route 必須為 UNKNOWN。"
            "使用 STE100：一句一項判斷，依據可回溯，只輸出指定 JSON。"
        ),
        gate_input=gate_input,
        output_schema=GATE1_SCHEMA,
        validator=validator,
        stub_fixture=stub_fixture,
    )
