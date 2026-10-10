from __future__ import annotations

import pytest

from app.workflow import WorkflowError, apply_action, create_case
from tests.helpers import BANK, completed_case, intake


def test_gates_cannot_be_skipped():
    case = create_case(intake(), BANK)
    with pytest.raises(WorkflowError):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)


def test_gate2_requires_human_selected_offense_and_all_answers():
    case = create_case(intake(summary="無法自動辨識的案件"), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    assert case["candidates"] == []
    with pytest.raises(WorkflowError):
        apply_action(case, "set_offenses", {"offense_ids": [], "role": "victim"}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "role": "victim"}, BANK)
    with pytest.raises(WorkflowError, match="所有問句"):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)


def test_backward_edit_invalidates_downstream_approvals():
    case = completed_case()
    assert case["state"] == "OUTPUT_READY"
    reopened = apply_action(case, "reopen", {}, BANK)
    assert reopened["state"] == "GATE1_REVIEW"
    assert reopened["approvals"] == {}
    assert reopened["documents"] == []


def test_same_case_can_continue_from_victim_to_suspect():
    case = completed_case("victim")
    victim_snapshot = case["interviews"]["victim:default"]
    case = apply_action(case, "start_interview", {"role": "suspect"}, BANK)
    assert case["state"] == "GATE2_QA"
    assert case["interviews"]["victim:default"] == victim_snapshot
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "role": "suspect"}, BANK)
    answers = {item["id"]: "UNKNOWN" for item in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    assert case["state"] == "OUTPUT_READY"
    assert set(case["interviews"]) == {"victim:default", "suspect:default"}


def test_profile_save_and_invalidation():
    case = completed_case()
    case = apply_action(case, "start_interview", {"role": "suspect"}, BANK)
    case = apply_action(case, "save_profile", {
        "role": "suspect",
        "profile": {"name": "測試涉嫌人", "gender": "女"},
        "session": {"start_time": "2026-10-11T14:00", "end_time": "2026-10-11T14:30", "location": "測試所"},
    }, BANK)
    # session 原樣保存（ISO），輸出文件時才轉民國
    assert case["interview_sessions"]["suspect:default"]["start_time"] == "2026-10-11T14:00"


def test_gate1_times_use_roc_era():
    case = create_case(intake(), BANK)
    assert case["gate1"]["times"] == ["115年10月10日10時30分"]


def test_brief_dates_are_roc_era():
    case = completed_case()
    from app.documents import brief_text
    text = brief_text(case, "victim")
    assert "發生時間：115年10月10日10時30分" in text
    assert "報案時間：115年10月10日11時00分" in text
    assert "2026-10-10" not in text


def test_ai_analyze_updates_candidates_and_marks_source():
    from app import ai as ai_module

    monkey_data = {"candidates": [{"id": "fraud", "reason": "以詐術使人交付"}], "model": "test-model"}
    monkeypatch_ai = lambda summary, offenses, max_candidates=6: monkey_data
    import app.workflow as wf
    original = wf.analyze_candidates
    wf.analyze_candidates = monkeypatch_ai
    try:
        case = completed_case()
        case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
        case = apply_action(case, "analyze_candidates", {}, BANK)
        assert case["candidates_source"] == "ai"
        assert case["candidates"][0]["id"] == "fraud"
        assert "AI 候選" in case["candidates"][0]["notice"]
    finally:
        wf.analyze_candidates = original


def test_company_questions_precede_common_questions():
    case = completed_case()
    case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "role": "victim"}, BANK)
    kinds = [item["kind"] for item in case["questions"]]
    assert kinds[0] == "company"
    assert kinds.index("common") > kinds.index("company")
    # 新套表.xlsm 公司罪章題（竊盜欄）已載入
    assert "company_offense" in kinds
    xlsm_texts = [item["text"] for item in case["questions"] if item["kind"] == "company_offense"]
    assert any("遭何人竊取" in text for text in xlsm_texts)


def test_no_victim_case_cannot_enter_regular_suspect_branch():
    case = completed_case("transfer")
    with pytest.raises(WorkflowError):
        apply_action(case, "start_interview", {"role": "suspect"}, BANK)

