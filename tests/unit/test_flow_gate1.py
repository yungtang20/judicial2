import pytest

from pipeline.flow.gate1_flow import Gate1Stop, run_gate1
from pipeline.flow.intake import validate_intake
from pipeline.flow.llm_client import LocalLLMClient, LocalLLMConfig, LocalLLMError
from tests.fixtures.stub_llm.server import running_stub


TEMPLATES = {("虛構所別", "受理報告")}


def _intake(*, reception_type="受理", repeated=False):
    summary = "2099-01-01 10:00 於虛構地點乙發生虛構事件。" if repeated else "虛構角色甲陳述虛構事件。"
    document_type = "受理報告" if reception_type in {"受理", ""} else "NOT_APPLICABLE"
    return validate_intake(
        {
            "station": "虛構所別",
            "document_type": document_type,
            "reception_type": reception_type,
            "event_time": "2099-01-01 10:00",
            "location": "虛構地點乙",
            "summary": summary,
        },
        available_templates=TEMPLATES,
    )


def _run(fixture, *, intake=None, warrant=None):
    with running_stub() as (endpoint, _server):
        client = LocalLLMClient(LocalLLMConfig(endpoint, "stub-fixed"))
        return run_gate1(
            intake or _intake(),
            case_id="case-stub",
            version="v1",
            client=client,
            warrant=warrant,
            stub_fixture=fixture,
        )


def test_t8_declared_basis_and_route_mismatch_is_rejected():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate1_route_mismatch")


def test_t9_warrant_missing_stops_at_gate1():
    with pytest.raises(Gate1Stop, match="通緝書未附"):
        _run(
            "gate1_warrant_missing",
            intake=_intake(reception_type="查獲"),
            warrant={"附件": "未附", "所載案由與罪名": ""},
        )


def test_t10_precheck_warning_is_preserved_unchanged():
    result = _run("gate1_warning_preserved", intake=_intake(repeated=True))
    assert result["warnings"][0]["text"] == "摘要含重複之時間或地點"


def test_t11_duplicate_unit_ids_are_rejected():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate1_duplicate_units")


def test_t12_backup_with_criminal_content_requires_todo():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate1_backup_empty", intake=_intake(reception_type="備案"))


def test_t13_direct_identifier_outside_source_raw_is_rejected():
    with pytest.raises(LocalLLMError, match="3 次"):
        _run("gate1_pii")


def test_blank_reception_stops_with_unknown_route():
    result = _run("gate1_unknown_route", intake=_intake(reception_type=""))
    assert result["route"] == "UNKNOWN"


def test_valid_gate1_stub_output_passes():
    assert _run("gate1_valid")["route"] == "A"
