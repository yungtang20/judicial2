from __future__ import annotations

import pytest

from app.workflow import WorkflowError, apply_action, create_case
from tests.helpers import BANK, completed_case, intake


def test_summary_labels_supply_time_kind_and_location_when_fields_are_omitted():
    case = create_case({
        "summary": (
            "查獲時間：民國115年10月15日10時許\n"
            "查獲地點：臺北市○○區○○路1號\n"
            "案情經過：員警在現場查獲測試物品。"
        ),
        "has_victim": False,
    }, BANK)
    assert case["intake"]["event_kind"] == "查獲"
    assert case["intake"]["event_time"] == "民國115年10月15日10時許"
    assert case["intake"]["location"] == "臺北市○○區○○路1號"
    assert case["gate1"]["times"][0] == "民國115年10月15日10時許"
    assert case["gate1"]["places"][0] == "臺北市○○區○○路1號"


def test_auto_prepare_selects_candidate_route_and_questions_from_summary():
    summary = (
        "曹富生、顏大鈞前與羅世亮在法務部矯正署新店戒治所中因抽煙問題生有嫌隙，"
        "共同徒手毆打羅世亮，致羅世亮受有上唇瘀腫及門牙折斷等傷害。"
    )
    case = create_case(intake(summary=summary), BANK)

    prepared = apply_action(case, "auto_prepare", {}, BANK)

    assert prepared["state"] == "GATE2_QA"
    assert prepared["selected_offenses"] == ["injury"]
    assert prepared["selected_legal_routes"]
    assert prepared["questions"]
    assert prepared["preparation_mode"] == "SYSTEM_AUTO_PREPARED_HUMAN_REVIEW_REQUIRED"
    assert prepared["audit"][-1]["event"] == "AUTO_PREPARE"


def test_missing_summary_labels_fail_closed_to_unknown_without_guessing():
    case = create_case({"summary": "有人在某處拿走物品。", "has_victim": True}, BANK)
    assert case["intake"]["event_kind"] == "發生"
    assert case["intake"]["event_time"] == "UNKNOWN"
    assert case["intake"]["location"] == "UNKNOWN"


def test_legacy_intake_fields_override_summary_labels_and_gate1_can_correct_them():
    case = create_case(intake(summary="發生時間：摘要時間\n發生地點：摘要地點\n案情經過：測試。"), BANK)
    assert case["intake"]["event_time"] == "2026-10-10T10:30"
    assert case["intake"]["location"] == "測試地點"
    case = apply_action(case, "update_gate1", {
        "gate1": {"times": ["民國115年10月16日11時許"], "places": ["修正地點"]},
    }, BANK)
    assert case["intake"]["event_time"] == "民國115年10月16日11時許"
    assert case["intake"]["location"] == "修正地點"


def test_gate1_summary_change_recomputes_facts_and_candidates():
    case = create_case(intake(summary="他把我的手機拿走了。"), BANK)
    # D1（人工核定 B 修正版，2026-10-20）：缺受託持有與強暴脅迫區辨事實，
    # 不再自動帶出侵占／強盜 related。
    assert {item["id"] for item in case["candidates"]} == {"theft"}
    case = apply_action(case, "update_gate1", {"gate1": {"events": ["事情發生了。"]}}, BANK)
    assert case["intake"]["summary"] == "事情發生了。"
    assert case["candidates"] == []
    assert case["alternative_routes"] == []
    assert all(not item.get("fact_key") for item in case["gate1"]["facts"])


def test_gates_cannot_be_skipped():
    case = create_case(intake(), BANK)
    with pytest.raises(WorkflowError):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)

def test_case_carries_acts_linked_to_facts_not_conclusions():
    case = create_case(intake(summary="有人未經同意拿走店內物品。"), BANK)
    assert case["acts"], "acts 應非空（由 gate1.facts 擷取）"
    act = case["acts"][0]
    for key in ("act_id", "event_id", "actor_ref", "action", "object",
                "time", "purpose", "result", "related_fact_ids",
                "related_candidate_ids", "evidence_refs", "review_status"):
        assert key in act, f"act 缺少欄位 {key}"
    # 行為是分析方向，非法律結論
    assert "分析方向" in act["note"]


def test_candidate_act_linking_is_not_assumed():
    case = create_case(intake(summary="對方以假客服名義要求匯款，疑似詐騙"), BANK)
    for candidate in case["candidates"]:
        # 系統不得武斷把行為套到罪名；須保留人工連結
        assert candidate["act_ids"] == ["HUMAN-ACT-LINKING-REQUIRED"]
        assert "NOT_ASSESSED" not in candidate["competition_analysis"] or "待" in candidate["competition_analysis"] or "人工" in candidate["competition_analysis"]



def test_gate2_requires_human_selected_offense_and_all_answers():
    case = create_case(intake(summary="無法自動辨識的案件"), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    assert case["candidates"] == []
    with pytest.raises(WorkflowError):
        apply_action(case, "set_offenses", {"offense_ids": [], "role": "victim"}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
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
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "suspect"}, BANK)
    case = apply_action(case, "save_profile", {
        "profile": {"name": "測試涉嫌人"},
        "session": {"start_time": "2026-10-11T14:00", "end_time": "2026-10-11T14:30"},
    }, BANK)
    answers = {item["id"]: "UNKNOWN" for item in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    assert case["state"] == "OUTPUT_READY"
    assert set(case["interviews"]) == {"victim:default", "suspect:default"}


def test_gate2_approval_requires_fields_needed_by_the_interview_document():
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {
        "offense_ids": ["theft"],
        "legal_route_ids": [],
        "route_review_confirmed": True,
        "role": "suspect",
    }, BANK)
    answers = {question["id"]: "UNKNOWN" for question in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)

    with pytest.raises(WorkflowError, match="缺少受詢問人姓名"):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)

    case = apply_action(case, "save_profile", {
        "profile": {"name": "合成測試"},
    }, BANK)
    with pytest.raises(WorkflowError, match="缺少詢問起訖時間"):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)

    case = apply_action(case, "save_profile", {
        "profile": {"name": "合成測試"},
        "session": {"start_time": "2026-10-19T10:00", "end_time": "2026-10-19T10:30"},
    }, BANK)
    approved = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    assert approved["state"] == "CASE_NUMBERS"


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
    monkey_data = {
        "candidates": [{
            "id": "fraud", "reason": "以詐術使人交付", "basis_quote": "以假客服名義要求匯款",
            "basis_start": 0, "basis_end": 10, "missing": ["交付情形待確認"],
        }],
        "status": {"subject_identified": "unknown", "has_victim": "true", "is_solved": "unknown"},
        "model": "test-model",
        "contract": {
            "schema_version": "case-analysis-v3-contract-v1", "request_id": "req-test",
            "input_hash": "0" * 64, "source_snapshot_hashes": {"catalog": "1" * 64},
            "attempt_count": 1,
        },
    }
    monkeypatch_ai = lambda summary, offenses, **kwargs: monkey_data
    import app.workflow as wf
    original = wf.analyze_candidates_v3
    wf.analyze_candidates_v3 = monkeypatch_ai
    try:
        case = completed_case()
        case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
        case = apply_action(case, "analyze_candidates", {"external_ai_consent": True}, BANK)
        assert case["candidates_source"] == "ai+rules"
        # AI 與規則來源分標（spec §5.6 不得混為同一來源）
        fraud_candidate = [c for c in case["candidates"] if c["id"] == "fraud"][0]
        assert "ai" in fraud_candidate["candidate_sources"]
        assert case["candidates"][0]["id"] == "fraud"
        assert "AI 候選" in case["candidates"][0]["notice"]
        assert fraud_candidate["classification_missing"] == ["交付情形待確認"]
        assert case["candidate_classification_status"]["has_victim"] == "true"
        assert case["candidate_analysis_contract"]["schema_version"] == "case-analysis-v3-contract-v1"
    finally:
        wf.analyze_candidates_v3 = original


def test_ai_analyze_requires_explicit_consent():
    case = completed_case()
    case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
    import pytest
    with pytest.raises(Exception, match="明確同意"):
        apply_action(case, "analyze_candidates", {}, BANK)


def test_create_case_gate1_never_calls_external_ai(monkeypatch):
    from app import ai as ai_module
    monkeypatch.setattr(ai_module, "segment_facts", lambda summary: (_ for _ in ()).throw(AssertionError("Gate 1 外送")))
    case = create_case(intake(), BANK)
    assert case["gate1"]["segmentation_source"] == "rules"


def test_initial_case_summary_is_preserved_while_statement_brief_is_capped():
    original = "發生時間：民國115年1月1日\n" + ("案情詳細經過。" * 120)
    case = create_case(intake(summary=original), BANK)
    assert case["intake"]["summary"] == original
    assert len(case["brief_summary"]) == 500


def test_ai_only_candidate_keeps_crosswalk_fail_closed_metadata():
    monkey_data = {
        "candidates": [{
            "id": "opium", "reason": "AI 建議辨識鴉片章", "basis_quote": "摘要沒有規則關鍵詞",
            "basis_start": 0, "basis_end": 10, "missing": ["物品性質待確認"],
        }],
        "status": {"subject_identified": "unknown", "has_victim": "unknown", "is_solved": "unknown"},
        "model": "test-model",
        "contract": {
            "schema_version": "case-analysis-v3-contract-v1", "request_id": "req-test",
            "input_hash": "0" * 64, "source_snapshot_hashes": {"catalog": "1" * 64},
            "attempt_count": 1,
        },
    }
    monkeypatch_ai = lambda summary, offenses, **kwargs: monkey_data
    import app.workflow as wf
    original = wf.analyze_candidates_v3
    wf.analyze_candidates_v3 = monkeypatch_ai
    try:
        case = completed_case()
        case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
        case["intake"]["summary"] = "摘要沒有規則關鍵詞"
        case = apply_action(case, "analyze_candidates", {"external_ai_consent": True}, BANK)
        candidate = next(item for item in case["candidates"] if item["id"] == "opium")
        assert candidate["candidate_sources"] == ["ai"]
        assert candidate["status"] == "NEED_LEGAL_ROUTE_MAPPING"
        assert candidate["element_model_status"] == "UNMAPPED"
        assert candidate["crosswalk_status"] == "SPLIT_REQUIRED"
        assert len(candidate["legal_routes"]) == 10
        assert candidate["legal_route_selection_status"] == "OPTIONAL"
    finally:
        wf.analyze_candidates_v3 = original


def test_company_questions_precede_common_questions():
    case = completed_case()
    case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    kinds = [item["kind"] for item in case["questions"]]
    assert kinds[0] == "company"
    assert kinds.index("common") > kinds.index("company")
    # 新套表.xlsm 公司罪章題（竊盜欄）已載入
    assert "company_offense" in kinds
    xlsm_texts = [item["text"] for item in case["questions"] if item["kind"] == "company_offense"]
    assert any("遭何人竊取" in text for text in xlsm_texts)


def test_company_standard_offense_route_does_not_mix_local_chapter_questions():
    for offense_id in ("sexual_harassment", "stalking"):
        case = completed_case()
        case = apply_action(case, "start_interview", {"role": "victim"}, BANK)
        case = apply_action(
            case,
            "set_offenses",
            {
                "offense_ids": [offense_id],
                "legal_route_ids": [],
                "route_review_confirmed": True,
                "role": "victim",
            },
            BANK,
        )
        assert all(
            item["kind"] in {"company", "common", "company_offense"}
            for item in case["questions"]
        )


def test_no_victim_case_cannot_enter_regular_suspect_branch():
    case = completed_case("transfer")
    with pytest.raises(WorkflowError):
        apply_action(case, "start_interview", {"role": "suspect"}, BANK)



def test_version_bump_invalidates_downstream():
    case = completed_case()
    assert case["state"] == "OUTPUT_READY"
    # 模擬題庫版本變更
    old_bank = dict(BANK)
    old_bank["library_version"] = "CHANGED-VERSION"
    updated = apply_action(case, "update_gate1", {"gate1": {"events": ["新描述"]}}, old_bank)
    # 版本 bump → gate1 失效 → 所有下游核准被清空
    assert updated["approvals"] == {}
    assert updated["versions"]["question_bank"] == "CHANGED-VERSION"

def test_template_version_bump_invalidates_downstream():
    from app import workflow as wf
    case = completed_case()
    original = wf.CURRENT_TEMPLATE_VERSION
    try:
        # 模擬公司範本版本升級
        wf.CURRENT_TEMPLATE_VERSION = "company-verbatim-NEW"
        updated = apply_action(case, "update_gate1", {"gate1": {"events": ["改"]}}, BANK)
        assert updated["versions"]["template"] == "company-verbatim-NEW"
        assert updated["approvals"] == {}
    finally:
        wf.CURRENT_TEMPLATE_VERSION = original


def test_candidate_engine_version_bump_invalidates_downstream():
    from app import workflow as wf
    case = completed_case()
    original = wf.CURRENT_CANDIDATE_ENGINE
    try:
        wf.CURRENT_CANDIDATE_ENGINE = "rules-v3+ai+facts"
        updated = apply_action(case, "update_gate1", {"gate1": {"events": ["改"]}}, BANK)
        assert updated["versions"]["candidate_engine"] == "rules-v3+ai+facts"
        assert updated["approvals"] == {}
    finally:
        wf.CURRENT_CANDIDATE_ENGINE = original

def test_competition_hint_includes_verified_judgment_anchor():
    from app.acts import competition_relationships
    candidates = [
        {"id": "theft", "name": "竊盜", "distinguishing_question_ids": ["T-D-01"]},
        {"id": "embezzlement", "name": "侵占", "distinguishing_question_ids": ["E-D-01"]},
    ]
    competition_relationships(candidates)
    text = candidates[0]["competition_analysis"]
    # 含經核實之裁判錨點（最高法院43年台上字第675號）
    assert "43年台上字第675號" in text
    # 明示僅供參考，非定性
    assert "非定性" in text


def test_competition_hint_includes_fraud_intimidation_anchor():
    """第二十輪：詐欺與恐嚇取財區辨裁判錨點（最高法院84年台上字第1993號）。"""
    from app.acts import competition_relationships
    candidates = [
        {"id": "fraud", "name": "詐欺", "distinguishing_question_ids": ["F-D-01"]},
        {"id": "intimidation", "name": "恐嚇取財", "distinguishing_question_ids": ["I-D-01"]},
    ]
    competition_relationships(candidates)
    text = candidates[0]["competition_analysis"]
    assert "84年度台上字第1993號" in text
    assert "CYDM,112,易,613" in text
    assert "非定性" in text
    assert "陷於錯誤" in text
    assert "心生畏懼" in text

def test_update_gate1_facts_length_and_count_limits():
    """spec §10 API 輸入驗證：facts 欄位不得無限膨脹 payload（第十二輪盤點發現）。"""
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    # 超長 excerpt 被拒
    with pytest.raises(WorkflowError, match="超過"):
        apply_action(case, "update_gate1", {
            "gate1": {"facts": [{"fact_id": "x", "source_excerpt": "x" * 200000}]}
        }, BANK)
    # 超量 facts 被拒
    with pytest.raises(WorkflowError, match="不得超過 50"):
        apply_action(case, "update_gate1", {
            "gate1": {"facts": [{"fact_id": f"x{i}"} for i in range(51)]}
        }, BANK)
    # 正常範圍通過
    updated = apply_action(case, "update_gate1", {
        "gate1": {"facts": [{"fact_id": "ok1", "source_excerpt": "正常長度"}]}
    }, BANK)
    assert updated["gate1"]["facts"][0]["fact_id"] == "ok1"

def test_save_profile_field_length_limits():
    """spec §10：年籍與詢問時間欄位長度限制（第十二輪盤點發現）。"""
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    with pytest.raises(WorkflowError, match="超過 200 字"):
        apply_action(case, "save_profile", {"profile": {"name": "z" * 100000}}, BANK)
    with pytest.raises(WorkflowError, match="超過 200 字"):
        apply_action(case, "save_profile", {
            "profile": {"name": "測試"},
            "session": {"start_time": "s" * 100000},
        }, BANK)
    # 正常通過
    updated = apply_action(case, "save_profile", {"profile": {"name": "測試"}}, BANK)
    assert updated["profiles"]["victim:default"]["name"] == "測試"

def test_reopen_snapshot_includes_gate1_facts():
    """spec §8.4：reopen 快照必須含 gate1（含 facts）——審計斷鏈缺陷（第十四輪盤點發現）。"""
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    original_fact_ids = [f["fact_id"] for f in case["gate1"]["facts"]]
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_profile", {"profile": {"name": "測試"}}, BANK)
    case = apply_action(case, "save_answers", {"answers": {q["id"]: "回答" for q in case["questions"]}}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    case = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "Z123"}}, BANK)
    reopened = apply_action(case, "reopen", {}, BANK)
    snap = reopened["snapshots"][-1]
    assert "gate1" in snap, "快照缺 gate1"
    snap_fact_ids = [f["fact_id"] for f in snap["gate1"].get("facts", [])]
    assert snap_fact_ids == original_fact_ids, "快照 facts 與開案時不一致"

def test_update_gate1_replace_semantics_allow_deletion():
    """F33：舊 append 語意使承辦人無法刪除錯誤事實；replace 語意 + 未提供 key 保留。"""
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    # 初始 facts 來自 analyze_gate1（events 含 intake summary）
    initial_events = list(case["gate1"]["events"])
    # 建案後有初始 events；送 replace 清單（不同內容）
    updated = apply_action(case, "update_gate1", {
        "gate1": {"events": ["修正後的唯一事件描述"]}
    }, BANK)
    # replace 語意：舊事件被刪除，只剩新描述
    assert updated["gate1"]["events"] == ["修正後的唯一事件描述"]
    assert initial_events[0] not in updated["gate1"]["events"] or initial_events[0] == "修正後的唯一事件描述"
    # 未提供的 key 保留原值
    assert updated["gate1"]["unknowns"] == case["gate1"]["unknowns"]


def test_brief_summary_follows_gate1_fact_changes():
    """F33：事實修改後 brief_summary 須反映現行版本（spec §9）。"""
    from app.config import MAX_SUMMARY_LENGTH
    case = create_case(intake(summary="初始摘要甲"), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_profile", {"profile": {"name": "測試"}}, BANK)
    case = apply_action(case, "save_answers", {"answers": {q["id"]: "回答" for q in case["questions"]}}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    case = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "Z123"}}, BANK)
    case = apply_action(case, "reopen", {}, BANK)
    updated = apply_action(case, "update_gate1", {
        "gate1": {"events": ["修正後的事件描述乙"]}
    }, BANK)
    assert "初始摘要甲" not in updated["brief_summary"], "條陳摘要殘留舊事實"
    assert "修正後的事件描述乙" in updated["brief_summary"]
    assert len(updated["brief_summary"]) <= MAX_SUMMARY_LENGTH

def test_case_numbers_correction_after_output_ready():
    """F35：OUTPUT_READY 後承辦人無法更正錯誤案號（只能 reopen 重跑全流程）。
    修：OUTPUT_READY 允許重新 save_case_numbers（新核准取代舊核准，舊值入快照）。"""
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_profile", {"profile": {"name": "測試"}}, BANK)
    case = apply_action(case, "save_answers", {"answers": {q["id"]: "回答" for q in case["questions"]}}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    case = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "錯誤案號"}}, BANK)
    assert case["state"] == "OUTPUT_READY"
    old_at = case["approvals"]["case_numbers"]["at"]
    # 更正（重新核准，非繞過）
    corrected = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "正確案號Z999"}}, BANK)
    assert corrected["case_numbers"]["proof"] == "正確案號Z999"
    assert corrected["approvals"]["case_numbers"]["at"] != old_at, "更正須產生新核准記錄"
    # 舊值可追溯
    assert any("錯誤案號" in str(s.get("case_numbers", {})) for s in corrected["snapshots"])
    # 驗證不完整的更正被拒（fail closed）
    import pytest
    from app.workflow import WorkflowError
    with pytest.raises(WorkflowError, match="缺少必要案號"):
        apply_action(corrected, "save_case_numbers", {"case_numbers": {"proof": ""}}, BANK)
