import pytest

from pipeline.flow.intake import IntakeError, validate_intake


TEMPLATES = {("虛構所別", "受理報告")}


def _valid(**changes):
    data = {
        "station": "虛構所別",
        "document_type": "受理報告",
        "reception_type": "受理",
        "event_time": "2099-01-01 10:00",
        "location": "虛構地點乙",
        "summary": "虛構角色甲陳述虛構事件。",
    }
    data.update(changes)
    return data


def test_t1_missing_required_field_is_rejected():
    with pytest.raises(IntakeError, match="案情摘要"):
        validate_intake(_valid(summary=""), available_templates=TEMPLATES)


def test_t2_unknown_field_is_rejected():
    with pytest.raises(IntakeError, match="不支援的欄位"):
        validate_intake(_valid(unknown="虛構值"), available_templates=TEMPLATES)


def test_t3_duplicate_time_and_place_are_retained_with_warning():
    summary = "2099-01-01 10:00 於虛構地點乙發生虛構事件。"
    result = validate_intake(_valid(summary=summary), available_templates=TEMPLATES)
    assert result.fields["summary"] == summary
    assert "摘要含重複之時間或地點" in result.warnings


def test_t4_conflicting_date_is_retained_with_warning():
    summary = "2099-02-02 由虛構角色甲陳述虛構事件。"
    result = validate_intake(_valid(summary=summary), available_templates=TEMPLATES)
    assert result.fields["summary"] == summary
    assert any("日期與發生時間不一致" in warning for warning in result.warnings)


def test_reception_type_can_be_blank():
    result = validate_intake(_valid(reception_type=""), available_templates=TEMPLATES)
    assert result.fields["reception_type"] == ""


def test_document_type_must_match_reception_type():
    with pytest.raises(IntakeError, match="不一致"):
        validate_intake(_valid(document_type="告發報告"), available_templates=TEMPLATES)


def test_non_report_reception_uses_not_applicable():
    result = validate_intake(
        _valid(reception_type="報案", document_type="NOT_APPLICABLE"),
        available_templates=TEMPLATES,
    )
    assert result.fields["document_type"] == "NOT_APPLICABLE"


def test_page_one_case_number_is_rejected_as_unknown_field():
    with pytest.raises(IntakeError, match="不支援的欄位"):
        validate_intake(_valid(case_number="TEST-001"), available_templates=TEMPLATES)
