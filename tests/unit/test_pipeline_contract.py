from pipeline import gate1, gate2, gate3
from pipeline.web import execute_payload
from pipeline.model_provider import _local_endpoint
from pipeline.label_normalizer import normalize_offense_label


def test_structured_record_routes_without_keyword_offense_inference():
    result = gate1.run(
        {
            "case_id": "synthetic-001",
            "summary": "虛構事件摘要",
            "gate1_fields": {
                "受理性質": "受理",
                "案號": "TEST-001",
                "刑事行為": "是",
                "被害人": "虛構角色",
            },
        }
    )
    assert result["route"] == "A"
    assert result["source_unit_ids"] == ["synthetic-001"]


def test_gate2_and_gate3_preserve_unknown_law_boundary():
    first = gate1.run(
        "受理性質：受理\n案號：TEST-002\n刑事行為：是\n被害人：虛構角色\n刑法第 999 條"
    )
    second = gate2.run(first)
    third = gate3.run(second)
    assert second["candidates"] == []
    assert "法條未收錄" in second["warnings"]
    assert third["warnings"] == second["warnings"]


def test_local_web_adapter_is_json_only():
    result = execute_payload({"record": "虛構案件文字"})
    assert set(result) == {"gate1", "gate2", "gate3"}
    assert result["gate1"]["route"] == "UNKNOWN"


def test_known_explicit_article_uses_review_only_catalog_candidate():
    first = gate1.run(
        "受理性質：受理\n案號：TEST-003\n刑事行為：是\n被害人：虛構角色\n刑法第 319 條之 1"
    )
    second = gate2.run(first)
    assert len(second["candidates"]) == 1
    assert second["candidates"][0]["candidate_status"] == "NEED_REVIEW"
    assert second["candidates"][0]["source_status"] == "待人工核定"
    assert second["intake_report"]["template_id"] == "JUDICIAL2-條陳格式-受理報告-v1"
    assert "四丶報案時間：" in second["intake_report"]["rendered_text"]
    third = gate3.run(second)
    assert third["apprehension_report"]["status"] == "模板未提供"
    assert "破獲條陳模板未提供" in third["warnings"]


def test_model_provider_rejects_non_loopback_endpoint(monkeypatch):
    monkeypatch.setenv("JUDICIAL2_LOCAL_LLM_ENDPOINT", "https://example.invalid/v1/chat")
    try:
        _local_endpoint()
    except RuntimeError as exc:
        assert "loopback-local" in str(exc)
    else:
        raise AssertionError("non-loopback endpoint was accepted")


def test_offense_label_normalization_only_removes_procedural_formatting():
    assert normalize_offense_label("虛構罪名案（受理）") == "虛構罪名"
