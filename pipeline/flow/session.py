"""Per-case forward-only state machine for the v0.3 intake flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pipeline.flow.intake import IntakeResult, validate_intake


ANSWER_LIMIT = 20_000


class FlowStateError(RuntimeError):
    """Raised when an invalid state transition is requested."""


class AnswerError(ValueError):
    """Raised when answers are missing, unknown, empty, or too long."""


def question_ids(gate2_output: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for section in ("victim_questions", "procedure_questions"):
        for group_index, group in enumerate(gate2_output.get(section, [])):
            for field_name, values in group.items():
                if field_name in {"unit_id", "候選罪章"} or not isinstance(values, list):
                    continue
                ids.extend(
                    f"{section}:{group_index}:{field_name}:{question_index}"
                    for question_index, _question in enumerate(values)
                )
    return ids


@dataclass
class FlowSession:
    case_id: str = field(default_factory=lambda: str(uuid4()))
    version_number: int = 1
    state: str = "NEW"
    intake: IntakeResult | None = None
    gate1_output: dict[str, Any] | None = None
    gate2_output: dict[str, Any] | None = None
    gate2_final_output: dict[str, Any] | None = None
    answers: dict[str, str] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return f"v{self.version_number}"

    def submit_intake(
        self,
        raw: dict[str, Any],
        *,
        available_templates: set[tuple[str, str]] | None = None,
    ) -> IntakeResult:
        self._require("NEW")
        self.intake = validate_intake(raw, available_templates=available_templates)
        self.state = "INTAKE"
        return self.intake

    def accept_gate1(self, output: dict[str, Any]) -> None:
        self._require("INTAKE")
        self.gate1_output = output
        self._apply_gate1_route()

    def _apply_gate1_route(self) -> None:
        route = (self.gate1_output or {}).get("route")
        if route in {"A", "UNKNOWN"}:
            self.state = "GATE1"
        elif route == "B":
            self.state = "DONE_ROUTE_B_PENDING_GATE3"
        elif route in {"C", "D", "E"}:
            self.state = "DONE_RECORD"
        else:
            raise FlowStateError("Gate 1 路由無法進入下一狀態")

    def accept_gate2(self, output: dict[str, Any]) -> None:
        self._require("GATE1")
        if self.gate1_output is None or self.gate1_output.get("route") != "A":
            raise FlowStateError("只有路由 A 可接受 Gate 2 輸出")
        self.gate2_output = output
        self.state = "GATE2"

    def begin_answering(self) -> list[str]:
        self._require("GATE2")
        if self.gate2_output is None:
            raise FlowStateError("缺少 Gate 2 輸出")
        self.state = "ANSWERING"
        return question_ids(self.gate2_output)

    def submit_answers(self, answers: dict[str, str]) -> None:
        self._require("ANSWERING")
        if self.gate2_output is None:
            raise FlowStateError("缺少 Gate 2 輸出")
        expected = set(question_ids(self.gate2_output))
        if set(answers) != expected:
            raise AnswerError("所有問句均須作答，且不得加入未知題號")
        for answer in answers.values():
            if not isinstance(answer, str) or not answer.strip():
                raise AnswerError("回答不得為空")
            if len(answer) > ANSWER_LIMIT:
                raise AnswerError("回答超過 20000 個 Unicode 字元")
        self.answers = dict(answers)

    def begin_final_summary(self) -> None:
        self._require("ANSWERING")
        if set(self.answers) != set(question_ids(self.gate2_output or {})):
            raise AnswerError("所有問句均須作答")
        self.state = "GATE2_FINAL_SUMMARY"

    def accept_final_summary(self, output: dict[str, Any]) -> None:
        self._require("GATE2_FINAL_SUMMARY")
        if output.get("gate") != "G2-FINAL" or not str(output.get("final_summary", "")).strip():
            raise FlowStateError("G2-FINAL 輸出不完整")
        self.gate2_final_output = output
        self.state = "COMPLETED"

    def number(self) -> None:
        self._require("COMPLETED")
        self.state = "NUMBERED"

    def supplement_current_gate(self, gate: str, output: dict[str, Any]) -> None:
        if gate == "G1" and self.state == "GATE1":
            self.gate1_output = output
            self._apply_gate1_route()
            return
        if gate == "G2" and self.state == "GATE2":
            self.gate2_output = output
            return
        raise FlowStateError("補件不屬於目前 Gate")

    def restart_from_gate1(self) -> None:
        if self.intake is None:
            raise FlowStateError("尚未完成頁 1")
        self.version_number += 1
        self.gate1_output = None
        self.gate2_output = None
        self.gate2_final_output = None
        self.answers.clear()
        self.result.clear()
        self.state = "INTAKE"

    def _require(self, expected: str) -> None:
        if self.state != expected:
            raise FlowStateError(f"目前狀態 {self.state}，預期狀態 {expected}")
