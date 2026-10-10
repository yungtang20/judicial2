import pytest

from pipeline.flow.gate2_flow import (
    Gate2NotEntered,
    load_all_laws,
    run_gate2,
    run_gate2_final,
)
from pipeline.flow.intake import validate_intake
from pipeline.flow.llm_client import LocalLLMClient, LocalLLMConfig, LocalLLMError
from tests.fixtures.stub_llm.server import running_stub


TEMPLATES = {("虛構所別", "受理報告")}


def _intake(*, reception_type="受理"):
    return validate_intake(
        {
            "station": "虛構所別",
            "document_type": "受理報告" if reception_type == "受理" else "NOT_APPLICABLE",
            "reception_type": reception_type,
            "event_time": "2099-01-01 10:00",
            "location": "虛構地點乙",
            "summary": "虛構角色甲陳述虛構事件。",
        },
        available_templates=TEMPLATES,
    )


def _gate1():
    return {
        "route": "A",
        "units": {
            "victim": [{"unit_id": "V-STUB-001", "source_raw": "虛構事件", "warnings": []}],
            "actor": [{"unit_id": "A-STUB-001", "source_raw": "虛構事件", "warnings": []}],
        },
        "procedure_facts": {
            "告訴狀態": "UNKNOWN", "告訴期間狀態": "UNKNOWN", "追訴權狀態": "UNKNOWN",
            "相關罪章檢核": "UNKNOWN", "承辦人待辦": [],
        },
        "warnings": [],
    }


def _run(fixture, *, gate1=None, intake=None):
    with running_stub() as (endpoint, _server):
        client = LocalLLMClient(LocalLLMConfig(endpoint, "stub-fixed"))
        return run_gate2(gate1 or _gate1(), intake or _intake(), client=client, stub_fixture=fixture)


def test_t14_each_candidate_has_question_group():
    result = _run("gate2_valid")
    assert len(result["candidates"]) == len(result["victim_questions"]) == 1


def test_t15_invalid_question_style_is_rejected():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate2_bad_question")


def test_t16_procedure_status_must_equal_gate1():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate2_bad_procedure")


def test_t17_each_victim_requires_questions():
    gate1 = _gate1()
    gate1["units"]["victim"].append({"unit_id": "V-STUB-002", "source_raw": "另一虛構事件", "warnings": []})
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate2_multi_victim_missing", gate1=gate1)


def test_t18_non_a_route_does_not_enter_gate2():
    gate1 = _gate1()
    gate1["route"] = "B"
    with pytest.raises(Gate2NotEntered):
        _run("gate2_valid", gate1=gate1)


def test_not_applicable_has_no_acceptance_draft():
    result = _run("gate2_not_applicable", intake=_intake(reception_type="報案"))
    assert result["acceptance_draft"] is None


def test_full_law_table_has_only_allowed_fields():
    rows = load_all_laws()
    assert len(rows) == 61
    assert all(set(row) == {"article_no", "article_text", "status"} for row in rows)


def test_gate2_final_summary_is_nonempty_and_structured():
    gate1 = _gate1()
    gate2 = _run("gate2_valid")
    with running_stub() as (endpoint, _server):
        client = LocalLLMClient(LocalLLMConfig(endpoint, "stub-fixed"))
        result = run_gate2_final(
            original_summary="虛構事件摘要",
            gate1_output=gate1,
            gate2_output=gate2,
            answers={"Q-001": "虛構回答"},
            client=client,
            stub_fixture="gate2_final_valid",
        )
    assert result["gate"] == "G2-FINAL"
    assert result["final_summary"]
