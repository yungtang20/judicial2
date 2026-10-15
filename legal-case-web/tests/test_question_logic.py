"""Phase 5 問句生成邏輯測試（metadata、預算、條件觸發、答案重評估）。"""

from __future__ import annotations

import pytest

from app.questions import (
    THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS,
    THEFT_320_1_MOVABLE_PACK_VERSION,
    QuestionBudgetExceeded,
    apply_question_budget,
    deduplicate_questions,
    enrich_question_metadata,
    filter_active_questions,
    reevaluate_candidates_from_answers,
    reevaluate_legal_routes_from_answers,
    sort_questions_by_priority,
)
from app.section_questions import read_section_questions

from tests.helpers import BANK


def _sample_questions() -> list[dict]:
    return [
        {"id": "V-COM-000", "text": "公司題", "kind": "company", "priority": 1},
        {"id": "V-COM-001", "text": "通用題", "kind": "common", "priority": 1},
        {"id": "V-theft-prop", "text": "核心題", "kind": "core", "offense_id": "theft", "priority": 1},
        {"id": "V-theft-S-1", "text": "補充題", "kind": "supplemental", "section": "evidence_gap", "offense_id": "theft", "priority": 2},
        {"id": "V-theft-R-1", "text": "補強題", "kind": "reinforce", "section": "reinforce", "offense_id": "theft", "priority": 3},
        {"id": "V-theft-D-1", "text": "區分題", "kind": "distinguishing", "section": "distinguishing", "offense_id": "theft", "priority": 4},
        {"id": "V-theft-A-1", "text": "加重題", "kind": "aggravating", "section": "aggravating", "offense_id": "theft", "priority": 5},
    ]


def test_markdown_parser_preserves_parent_role_scope(tmp_path):
    question_file = tmp_path / "role-scoped.md"
    question_file.write_text(
        "# 測試題庫\n"
        "## 被害人端\n"
        "### 核心問句\n"
        "- **X-C-01**：被害人專用問題文字。\n"
        "## 涉嫌人端\n"
        "### 核心問句\n"
        "- **X-N-01**：涉嫌人專用問題文字。\n"
        "## 補強問句\n"
        "- **X-R-01**：所有角色共同補強問題。\n",
        encoding="utf-8",
    )

    sections = read_section_questions(question_file)
    victim_core = {item["id"] for item in sections["victim"]["core"]}
    suspect_core = {item["id"] for item in sections["suspect"]["core"]}
    transfer_core = {item["id"] for item in sections["transfer"]["core"]}
    assert victim_core == {"X-C-01"}
    assert suspect_core == {"X-N-01"}
    assert transfer_core == {"X-N-01"}
    assert {item["id"] for item in sections["victim"]["reinforce"]} == {"X-R-01"}
    assert sections["suspect"]["reinforce"] == []
    assert sections["transfer"]["reinforce"] == []


def test_markdown_parser_keeps_witness_review_only(tmp_path):
    question_file = tmp_path / "witness.md"
    question_file.write_text(
        "# 測試題庫\n## 證人端\n### 核心問句\n"
        "- **X-W-01**：請說明你親自看到的事情。\n",
        encoding="utf-8",
    )
    sections = read_section_questions(question_file)
    assert {item["id"] for item in sections["witness_review_only"]["core"]} == {"X-W-01"}
    for role in ("victim", "suspect", "transfer"):
        assert sections[role]["core"] == []


def test_markdown_parser_unscoped_ids_do_not_cross_contaminate_roles(tmp_path):
    question_file = tmp_path / "compact.md"
    question_file.write_text(
        "# 小罪章\n"
        "- **X-C-01**：請說明事件涉及的物品。\n"
        "- **X-N-01**：請說明你與該物品的關係。\n"
        "- **X-W-01**：請說明你親自看到的事情。\n",
        encoding="utf-8",
    )
    sections = read_section_questions(question_file)
    assert {item["id"] for item in sections["victim"]["core"]} == {"X-C-01"}
    assert {item["id"] for item in sections["suspect"]["core"]} == {"X-N-01"}
    assert {item["id"] for item in sections["transfer"]["core"]} == {"X-N-01"}
    assert {item["id"] for item in sections["witness_review_only"]["core"]} == {"X-W-01"}


def test_runtime_bank_excludes_witness_and_keeps_transfer_on_suspect_semantics():
    for offense in BANK["offenses"]:
        runtime_ids = {
            item["id"]
            for role in ("victim", "suspect", "transfer")
            for item in offense.get("role_questions", {}).get(role, [])
        }
        witness_ids = {
            item["id"]
            for items in offense.get("section_questions", {}).get("witness_review_only", {}).values()
            for item in items
        }
        assert runtime_ids.isdisjoint(witness_ids), offense["id"]
        suspect_ids = {
            item["id"] for item in offense.get("role_questions", {}).get("suspect", [])
        }
        transfer_ids = {
            item["id"] for item in offense.get("role_questions", {}).get("transfer", [])
        }
        assert transfer_ids == suspect_ids, offense["id"]


def test_public_danger_runtime_is_scoped_to_drink_driving_questions():
    offense = next(item for item in BANK["offenses"] if item["id"] == "public_danger")
    assert offense["question_source"] == "drink-driving.md"
    ids = {
        item["id"]
        for role in ("victim", "suspect", "transfer")
        for item in offense["role_questions"][role]
    }
    assert any(qid.startswith("J-") for qid in ids)
    assert not any(qid.startswith("PD-") for qid in ids)


def _sample_case() -> dict:
    return {
        "selected_offenses": ["theft"],
        "questions": [
            {"id": "V-theft-prop", "text": "核心題", "answer": "測試回答"},
            {"id": "V-COM-000", "text": "公司題", "answer": ""},
        ],
        "gate1": {"facts": [{"fact_id": "FACT-001", "fact_status": "PARTY_STATEMENT"}]},
        "candidates": [{"offense_id": "theft", "unknown_elements": ["財物及持有狀態"]}],
    }


def test_enrich_question_metadata_adds_fields():
    gate1 = {"facts": []}
    candidates = [{"offense_id": "theft", "unknown_elements": ["取走行為"]}]
    enriched = enrich_question_metadata(_sample_questions(), gate1, candidates)
    for q in enriched:
        assert "meta" in q
        meta = q["meta"]
        for key in ("target_fact_ids", "target_elements", "purpose", "trigger_condition", "expected_distinction", "evidence_to_verify"):
            assert key in meta
    # 區分題的 purpose 應是區分競爭假設
    dist = [q for q in enriched if q["kind"] == "distinguishing"][0]
    assert dist["meta"]["purpose"] == "區分競爭假設"
    # 核心題 purpose 應是確認構成要件
    core = [q for q in enriched if q["kind"] == "core"][0]
    assert core["meta"]["purpose"] == "確認構成要件"
    assert core["meta"]["target_elements"] == []
    # md 題（無 JSON element）→ fact_target 以問句 ID 標記、element_mapping_status=MD_SOURCE
    assert core["meta"]["element_mapping_status"] == "MD_SOURCE"
    assert core["meta"]["fact_target"] == core["id"]
    assert core["meta"]["fact_target_text"] == core["text"]
    # 補充/補強 purpose 應是補齊事實
    supp = [q for q in enriched if q["kind"] == "supplemental"][0]
    assert supp["meta"]["purpose"] == "補齊事實"


def test_enrich_question_metadata_uses_only_exact_question_element():
    questions = [{
        "id": "V-theft-taking",
        "text": "請說明取得經過。",
        "kind": "core",
        "offense_id": "theft",
        "element_id": "taking",
    }]
    enriched = enrich_question_metadata(
        questions,
        {},
        [{"id": "theft", "unknown_elements": ["取走行為", "同意狀態"]}],
    )
    assert enriched[0]["meta"]["target_elements"] == ["taking"]
    assert enriched[0]["meta"]["element_mapping_status"] == "EXACT"


def test_unknown_activation_condition_fails_closed():
    questions = [{
        "id": "Q-UNKNOWN",
        "text": "未核准條件題",
        "kind": "supplemental",
        "meta": {"trigger_condition": "unsupported:condition"},
    }]
    assert filter_active_questions(questions, _sample_case()) == []


def test_apply_question_budget_protects_core_and_company():
    # 造 40 個 aggravating + 1 core + 1 company
    #（見 docs/QUESTION_DESIGN_AND_USE.md §6：core 佔額度）
    questions = [
        {"id": f"V-X-{i}", "text": f"題 {i}", "kind": "aggravating", "priority": 1}
        for i in range(40)
    ]
    questions.insert(0, {"id": "V-COM-000", "text": "公司題", "kind": "company", "priority": 1})
    questions.insert(1, {"id": "V-theft-prop", "text": "核心題", "kind": "core", "priority": 1})
    pruned = apply_question_budget(questions, max_offense_questions=30)
    # offense 題（非 company/common）總數 = 30（core 1 + aggravating 29）
    offense_questions = [q for q in pruned if q["kind"] not in {"company", "common"}]
    assert len(offense_questions) == 30
    # core 題被保留
    assert any(q["kind"] == "core" for q in pruned)
    # company 題被保留
    assert any(q["kind"] == "company" for q in pruned)


def test_budget_fails_closed_when_required_questions_exceed_limit():
    """必要 core／company_offense 超額時必須縮小路由，不得裁核心。"""
    questions = []
    for oid in ("A", "B", "C", "D", "E", "F"):
        for i in range(4):  # 每罪章 4 core
            questions.append({"id": f"c-{oid}-{i}", "kind": "core", "offense_id": oid, "text": f"c{oid}{i}"})
        for i in range(8):  # 每罪章 8 company_offense
            questions.append({"id": f"x-{oid}-{i}", "kind": "company_offense", "offense_id": oid, "text": f"x{oid}{i}"})
    with pytest.raises(QuestionBudgetExceeded, match="禁止裁除必要題"):
        apply_question_budget(questions, max_offense_questions=30)
    assert apply_question_budget.last_prune_info["status"] == "BUDGET_EXCEEDED"


def test_budget_pruning_is_transparent():
    """docs/QUESTION_DESIGN_AND_USE.md §6：裁切須留下統計資訊。"""
    questions = [{"id": f"V-X-{i}", "text": f"題 {i}", "kind": "aggravating"} for i in range(40)]
    apply_question_budget(questions, max_offense_questions=10)
    assert apply_question_budget.last_prune_info["total_pruned"] > 0


def test_filter_active_questions_always_and_conditional():
    case = _sample_case()
    questions = _sample_questions()
    enriched = enrich_question_metadata(questions, case["gate1"], case["candidates"])
    active = filter_active_questions(enriched, case)
    active_ids = {q["id"] for q in active}
    # 區分題 trigger: candidate:theft:present → theft 已選中 → 顯示
    assert "V-theft-D-1" in active_ids
    # 公司題/通用題/核心題/補充題/補強題 trigger: always → 顯示
    for qid in ("V-COM-000", "V-COM-001", "V-theft-prop", "V-theft-S-1", "V-theft-R-1"):
        assert qid in active_ids
    # 未選中的候選對應區分題不顯示
    case2 = _sample_case()
    case2["selected_offenses"] = []  # 未選罪章
    enriched2 = enrich_question_metadata(questions, case2["gate1"], case2["candidates"])
    active2 = filter_active_questions(enriched2, case2)
    active2_ids = {q["id"] for q in active2}
    assert "V-theft-D-1" not in active2_ids


def test_filter_active_questions_by_answer_and_fact():
    case = _sample_case()
    questions = [
        {"id": "Q-A", "text": "依答案觸發", "kind": "supplemental"},
        {"id": "Q-F", "text": "依事實觸發", "kind": "supplemental"},
    ]
    # 手動設 trigger_condition（模擬）
    enriched = enrich_question_metadata(questions, case["gate1"], case["candidates"])
    # 讓 Q-A 的 trigger 綁到一個已作答的題目
    enriched[0]["meta"]["trigger_condition"] = "answer:V-theft-prop:測試回答"
    enriched[1]["meta"]["trigger_condition"] = "fact:FACT-001:PARTY_STATEMENT"
    active = filter_active_questions(enriched, case)
    active_ids = {q["id"] for q in active}
    assert "Q-A" in active_ids
    assert "Q-F" in active_ids
    # 改變條件不應觸發
    enriched[1]["meta"]["trigger_condition"] = "fact:FACT-001:CONTRADICTED"
    active2 = filter_active_questions(enriched, case)
    assert "Q-F" not in {q["id"] for q in active2}


def test_deduplicate_and_sort_questions():
    questions = _sample_questions()
    dup = questions + [{"id": "DUP", "text": "公司題", "kind": "company"}]
    unique = deduplicate_questions(dup)
    assert len(unique) == len(questions)
    sorted_q = sort_questions_by_priority(unique)
    kinds = [q["kind"] for q in sorted_q]
    # company 在最前
    assert kinds[0] == "company"


def test_reevaluate_candidates_returns_existing():
    case = _sample_case()
    case["questions"] = []  # 無核心題作答
    result = reevaluate_candidates_from_answers(case, BANK)
    assert result["updated"] is False
    assert result["contradictions"] == []
    assert result["candidates"] == case["candidates"]


def test_classify_answer_categories():
    from app.questions import classify_answer
    assert classify_answer("有，我有看到他拿走") == "affirmative"
    assert classify_answer("沒有") == "negative"
    assert classify_answer("不知道") == "unknown"  # 不得視為否認
    assert classify_answer("不記得") == "unknown"
    assert classify_answer("不適用") == "not_applicable"
    assert classify_answer("") == "other"
    assert classify_answer("這是普通敘述") == "other"


def test_reevaluate_affirmative_shrinks_unknown_elements():
    from app.questions import reevaluate_candidates_from_answers
    case = {
        "candidates": [{
            "id": "theft", "name": "竊盜",
            "unknown_elements": ["取走行為", "同意狀態"],
        }],
        "questions": [
            {"id": "V-theft-taking", "kind": "core", "offense_id": "theft",
             "element_label": "取走行為", "answer": "有，我看到他拿走物品"},
            {"id": "V-theft-consent", "kind": "core", "offense_id": "theft",
             "element_label": "同意狀態", "answer": "不知道"},
        ],
    }
    result = reevaluate_candidates_from_answers(case, BANK)
    candidate = result["candidates"][0]
    # affirmative → 從 unknown 移除，加入 supported
    assert "取走行為" not in candidate["unknown_elements"]
    assert "取走行為" in candidate["supported_elements"]
    # unknown（不知道）→ 不得從 unknown_elements 移除（不知道 ≠ 否認）
    assert "同意狀態" in candidate["unknown_elements"]
    assert result["updated"] is True


def test_reevaluate_detects_contradiction():
    from app.questions import reevaluate_candidates_from_answers
    case = {
        "candidates": [{"id": "theft", "name": "竊盜", "unknown_elements": []}],
        "questions": [
            {"id": "V-theft-taking", "kind": "core", "offense_id": "theft",
             "element_label": "取走行為", "answer": "有看到他拿走"},
            {"id": "S-theft-taking", "kind": "core", "offense_id": "theft",
             "element_label": "取走行為", "answer": "沒有拿走任何東西"},
        ],
    }
    result = reevaluate_candidates_from_answers(case, BANK)
    assert len(result["contradictions"]) == 1
    assert result["contradictions"][0]["element"] == "取走行為"


def test_reevaluate_records_negative_answers():
    from app.questions import reevaluate_candidates_from_answers
    case = {
        "candidates": [{"id": "theft", "name": "竊盜", "unknown_elements": []}],
        "questions": [
            {"id": "S-theft-consent", "kind": "core", "offense_id": "theft",
             "element_label": "同意狀態", "answer": "沒有得到同意"},
        ],
    }
    result = reevaluate_candidates_from_answers(case, BANK)
    candidate = result["candidates"][0]
    assert candidate["contradictory_answers"] == [
        {"element": "同意狀態", "question_id": "S-theft-consent"}
    ]

def test_validate_generated_questions_clean_output():
    """問句設計規範：正常生成輸出應通過 Q1-Q10（僅可能 Q6/Q7 warnings）。"""
    from app.questions import validate_generated_questions, enrich_question_metadata
    from tests.helpers import BANK, intake
    from app.rules import build_questions
    from app.workflow import create_case
    case = create_case(intake(), BANK)
    qs = build_questions(BANK, "victim", ["theft"])
    qs = enrich_question_metadata(qs, case.get("gate1", {}), case.get("candidates", []))
    result = validate_generated_questions(qs, "victim")
    assert result["problems"] == [], f"品質檢核失敗：{result['problems'][:5]}"


def test_validate_detects_leading_question():
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    qs.append({"id": "BAD-1", "text": "是不是你偷的？", "kind": "core", "meta": {"purpose": "x", "trigger_condition": "always"}})
    result = validate_generated_questions(qs, "victim")
    assert any("Q2" in p for p in result["problems"])


def test_validate_detects_conclusion_language():
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    qs.append({"id": "BAD-2", "text": "你承認犯罪成立嗎？", "kind": "core", "meta": {"purpose": "x", "trigger_condition": "always"}})
    result = validate_generated_questions(qs, "victim")
    assert any("Q3" in p for p in result["problems"])


def test_validate_detects_duplicate():
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    dup = dict(qs[0])
    qs.append(dup)
    result = validate_generated_questions(qs, "victim")
    assert any("Q5" in p for p in result["problems"])


def test_validate_detects_missing_purpose():
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    for q in qs:
        if q.get("kind") == "core":
            q.pop("meta", None)
            break
    result = validate_generated_questions(qs, "victim")
    assert any("Q9" in p for p in result["problems"])


def test_validate_company_verbatim():
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    # 改寫公司題文字 → Q4 應偵測
    for q in qs:
        if q.get("kind") == "company":
            q["text"] = q["text"].replace("是否", "是不是")  # 實質改寫
            break
    result = validate_generated_questions(qs, "victim")
    assert any("Q4" in p for p in result["problems"]), f"Q4 未觸發：{result['problems'][:3]}"

def test_q1_multiple_question_marks_go_to_manual_review():
    """問句設計規範：多重問號 = warning（主題單一性由人工審核判定）。"""
    from app.questions import validate_generated_questions
    from tests.helpers import BANK
    from app.rules import build_questions
    qs = build_questions(BANK, "victim", ["theft"])
    qs.append({"id": "BAD-MT", "kind": "core", "meta": {"purpose": "x", "trigger_condition": "always"},
               "text": "物品在哪裡？你當時人在哪裡？"})
    result = validate_generated_questions(qs, "victim")
    assert any("Q1 多重問號" in w and "BAD-MT" in w for w in result["warnings"])
    # 不得列入 problems（避免誤殺同一主題的多子問）

def test_rcq_compilation_quality_gates():
    """docs/QUESTION_DESIGN_AND_USE.md：RCQ 審核稿通過 Q1/Q2/Q3。
    防將來接線時品質退化（檔案在 docs/，runtime_enabled: false）。"""
    import re
    from pathlib import Path
    rcq_path = Path(__file__).resolve().parents[1] / "docs" / "CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md"
    if not rcq_path.exists():
        pytest.skip("RCQ 文件不存在")
    content = rcq_path.read_text(encoding="utf-8")
    questions = []
    for line in content.split("\n"):
        m = re.match(r"-\s+\*\*(RCQ-[A-Z0-9-]+)\*\*(.*)", line)
        if not m:
            continue
        rest = m.group(2)
        text = rest.split("：", 1)[-1].strip() if "：" in rest else rest.strip()
        questions.append((m.group(1), text))
    assert len(questions) >= 400, f"RCQ 題目數異常：{len(questions)}"
    ids = [q for q, _ in questions]
    assert len(ids) == len(set(ids)), "RCQ ID 重複"
    leading = ("是不是你", "是不是有", "對不對", "難道你", "你承認", "你否認")
    conclusion = ("犯罪成立", "構成犯罪", "你犯了", "明知故犯")
    for qid, text in questions:
        for p in leading:
            assert p not in text, f"Q2 誘導語句 {qid}: {p}"
        for p in conclusion:
            assert p not in text, f"Q3 定性語句 {qid}: {p}"

def test_bidirectional_convergence_fact_and_legal_targets():
    """Round 22 雙向收斂：每個問句必須有 fact_target（中性事實）與 legal_targets（法律路由）雙鏈結。"""
    from tests.helpers import BANK, intake
    from app.workflow import create_case, apply_action
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft", "embezzlement"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    for q in case["questions"]:
        meta = q["meta"]
        # 雙鏈結齊備
        assert "fact_target" in meta and meta["fact_target"], f"{q['id']} 缺 fact_target"
        assert isinstance(meta.get("legal_targets"), list), f"{q['id']} 缺 legal_targets"
        assert meta["legal_targets"], f"{q['id']} legal_targets 不可為空"
        # core 題：legal_targets 至少含本罪章
        if q["kind"] == "core":
            assert q["offense_id"] in meta["legal_targets"]
        # distinguishing 題：legal_targets 必須跨候選（本罪章 + 其他）
        if q["kind"] == "distinguishing":
            assert len(meta["legal_targets"]) >= 2, f"{q['id']} 區分題應跨候選：{meta['legal_targets']}"
            assert set(meta["legal_targets"]) <= {"theft", "embezzlement", "robbery"}
            assert "civil_possession_dispute" not in meta["legal_targets"]
            assert meta.get("mapping_version") == "property-taking-v1"
            assert meta.get("answer_map") == {"YES": "YES", "NO": "NO", "UNKNOWN": "UNKNOWN"}


def test_bidirectional_convergence_unknown_fact_neutral():
    """「不知道」回答不得收縮 unknown_elements（事實保持 UNKNOWN，spec §7.4）。"""
    from tests.helpers import BANK, intake
    from app.workflow import create_case, apply_action
    from app.questions import reevaluate_candidates_from_answers
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_profile", {"profile": {"name": "測試", "national_id": "A123456789", "sex": "男", "education": "大學"}, "session": {"start_time": "2026-10-11T14:00", "end_time": "2026-10-11T15:00", "location": "測試所"}}, BANK)
    answers = {}
    for q in case["questions"]:
        if q["kind"] == "core":
            answers[q["id"]] = "不知道"  # 全部不知道
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    res = reevaluate_candidates_from_answers(case, BANK)
    cand = res["candidates"][0]
    # unknown_elements 完整保留（不知道 ≠ 否認；不得為選出罪名而硬套罪章）
    assert cand["unknown_elements"], "不知道回答不得清空 unknown_elements"
    assert not cand.get("supported_elements"), "不知道回答不得產生 supported_elements"


def test_bidirectional_convergence_uses_explicit_answer_codes():
    """自由文字只保存；封閉 answer_code 才更新中性事實與候選狀態。"""
    from tests.helpers import BANK, intake
    from app.workflow import create_case, apply_action
    case = create_case(intake(), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["embezzlement"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_profile", {"profile": {"name": "測試", "national_id": "A123456789", "sex": "男", "education": "大學"}, "session": {"start_time": "2026-10-11T14:00", "end_time": "2026-10-11T15:00", "location": "測試所"}}, BANK)
    answers = {q["id"]: "受詢問人的具體陳述" for q in case["questions"]}
    answer_codes = {
        q["id"]: "UNKNOWN" for q in case["questions"] if q.get("meta", {}).get("answer_map")
    }
    prior = next(q for q in case["questions"] if q.get("meta", {}).get("fact_target") == "prior_lawful_possession")
    answer_codes[prior["id"]] = "YES"
    case = apply_action(case, "save_answers", {"answers": answers, "answer_codes": answer_codes}, BANK)
    assert case["fact_overlay"]["prior_lawful_possession"] == "YES"
    cand = next(x for x in case["candidates"] if x["id"] == "embezzlement")
    assert cand["candidate_state"] == "ACTIVE"
    assert all(item.get("candidate_state") != "EXCLUDED" for item in case["candidates"])


def test_property_questions_are_role_specific_with_stable_fact_targets():
    from tests.helpers import intake
    from app.rules import build_questions
    from app.workflow import create_case

    base = create_case(intake(summary="他把我的手機拿走了。"), BANK)
    by_role = {}
    for role in ("victim", "suspect", "transfer"):
        questions = build_questions(
            BANK, role, ["theft"], gate1=base["gate1"], candidates=base["candidates"]
        )
        focused = [q for q in questions if q.get("meta", {}).get("mapping_version") == "property-taking-v1"]
        by_role[role] = focused
        assert {q["meta"]["fact_target"] for q in focused} == {
            "original_possession", "consent", "prior_lawful_possession", "force_or_threat",
            "return_agreement", "stated_use_or_return_plan", "evidence",
        }
        assert all(q["meta"]["legal_targets"] for q in focused)
        assert all(
            "civil_possession_dispute" not in q["meta"]["legal_targets"]
            for q in focused
        )
        assert all(q["meta"]["answer_map"] for q in focused)
    assert [q["text"] for q in by_role["victim"]] != [q["text"] for q in by_role["suspect"]]
    assert [q["text"] for q in by_role["suspect"]] != [q["text"] for q in by_role["transfer"]]


def test_property_question_alternatives_are_non_executable_review_topics():
    from tests.helpers import intake
    from app.rules import build_questions
    from app.workflow import create_case

    base = create_case(intake(summary="他把我的手機拿走了。"), BANK)
    questions = build_questions(
        BANK,
        "victim",
        ["theft", "embezzlement"],
        gate1=base["gate1"],
        candidates=base["candidates"],
    )
    focused = [
        q for q in questions
        if q.get("meta", {}).get("mapping_version") == "property-taking-v1"
    ]
    alternatives = [
        detail
        for question in focused
        for detail in question["meta"].get("alternative_target_details", [])
    ]

    assert alternatives
    assert {item["route_id"] for item in alternatives} == {"civil_possession_dispute"}
    for item in alternatives:
        assert set(item["effects"].values()) == {"NEED_REVIEW"}
        assert item["candidate_eligible"] is False
        assert item["routing_eligible"] is False
        assert item["question_generation_eligible"] is False
        assert item["template_activation_eligible"] is False
        assert item["effect_executable"] is False
        assert item["exclusion_safe"] is False
        assert item["human_review_required"] is True


def test_conflicting_role_answer_codes_remain_need_review():
    case = {
        "question_role": "suspect",
        "candidates": [{"id": "theft", "unknown_elements": []}],
        "fact_updates": [{
            "fact_key": "consent", "value": "YES", "question_id": "V-FACT-consent",
            "source_role": "victim", "answer_code": "YES", "provenance": "interview.answer_code",
        }],
        "questions": [{
            "id": "S-FACT-consent", "kind": "distinguishing", "role": "suspect",
            "answer": "沒有同意", "answer_code": "NO",
            "meta": {
                "fact_target": "consent", "mapping_version": "property-taking-v1",
                "legal_target_details": [{
                    "route_id": "theft", "effects": {"YES": "LOWERED", "NO": "ACTIVE"},
                    "exclusion_safe": False,
                }],
            },
        }],
    }
    result = reevaluate_candidates_from_answers(case, BANK)
    assert result["fact_overlay"]["consent"] == "CONFLICT"
    assert result["candidates"][0]["candidate_state"] == "NEED_REVIEW"


def test_property_free_text_does_not_override_unknown_answer_code():
    case = {
        "question_role": "victim",
        "candidates": [{"id": "theft", "unknown_elements": ["同意範圍"]}],
        "fact_updates": [],
        "questions": [{
            "id": "V-FACT-consent", "kind": "core", "role": "victim",
            "offense_id": "theft", "element_label": "同意範圍",
            "answer": "有，我同意他拿走", "answer_code": "UNKNOWN",
            "meta": {
                "fact_target": "consent", "mapping_version": "property-taking-v1",
                "legal_target_details": [{
                    "route_id": "theft", "effects": {"YES": "LOWERED", "NO": "ACTIVE"},
                    "exclusion_safe": False,
                }],
            },
        }],
    }
    result = reevaluate_candidates_from_answers(case, BANK)
    assert result["fact_overlay"]["consent"] == "UNKNOWN"
    assert result["candidates"][0]["unknown_elements"] == ["同意範圍"]
    assert result["candidates"][0]["candidate_state"] == "NEED_REVIEW"


def test_exact_theft_route_materializes_approved_pack_and_only_replaces_allowlist():
    from app.rules import build_questions
    from app.workflow import create_case
    from tests.helpers import intake

    base = create_case(intake(), BANK)
    questions = build_questions(
        BANK,
        "victim",
        ["theft"],
        gate1=base["gate1"],
        candidates=base["candidates"],
        legal_route_ids=["theft_320_1_movable"],
        materialized_at="2026-10-14T00:00:00+00:00",
    )
    exact = [q for q in questions if q.get("meta", {}).get("pack_version") == THEFT_320_1_MOVABLE_PACK_VERSION]
    assert {q["meta"]["question_concept_id"] for q in exact} == set(THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS)
    assert all(q["id"].endswith("-V") for q in exact)
    legacy = {
        q["meta"]["fact_target"] for q in questions
        if q.get("meta", {}).get("mapping_version") == "property-taking-v1"
    }
    assert legacy == {
        "prior_lawful_possession", "return_agreement",
        "stated_use_or_return_plan", "evidence",
    }
    assert {q["kind"] for q in questions if q["kind"] in {"company", "common"}} == {"company", "common"}
    coverage = build_questions.question_coverage_by_route["routes"]["theft_320_1_movable"]
    assert coverage["materialization_status"] == "COMPLETE"
    assert coverage["missing_concept_ids"] == []
    assert coverage["pruned_concept_ids"] == []


def test_exact_pack_budget_pruning_downgrades_route_coverage(monkeypatch):
    import app.rules as rules
    from app.workflow import create_case
    from tests.helpers import intake

    base = create_case(intake(), BANK)
    monkeypatch.setattr(rules, "MAX_OFFENSE_QUESTIONS", 16)
    rules.build_questions(
        BANK,
        "victim",
        ["theft"],
        gate1=base["gate1"],
        candidates=base["candidates"],
        legal_route_ids=["theft_320_1_movable"],
        materialized_at="2026-10-14T00:00:00+00:00",
    )
    coverage = rules.build_questions.question_coverage_by_route["routes"]["theft_320_1_movable"]
    assert coverage["materialization_status"] == "PARTIAL"
    assert coverage["coverage_claim"] == "NONE"
    assert coverage["missing_concept_ids"]
    assert coverage["pruned_concept_ids"]


def test_route_reducer_keeps_cross_role_provenance_and_conflict():
    from app.rules import build_questions
    from app.workflow import create_case
    from tests.helpers import intake

    base = create_case(intake(), BANK)
    victim_questions = build_questions(
        BANK, "victim", ["theft"], gate1=base["gate1"], candidates=base["candidates"],
        legal_route_ids=["theft_320_1_movable"], materialized_at="v",
    )
    suspect_questions = build_questions(
        BANK, "suspect", ["theft"], gate1=base["gate1"], candidates=base["candidates"],
        legal_route_ids=["theft_320_1_movable"], materialized_at="s",
    )
    next(q for q in victim_questions if q["meta"].get("question_concept_id") == "THF3201MOV-C02")["answer_code"] = "OTHER_PERSON_CONTROL"
    next(q for q in suspect_questions if q["meta"].get("question_concept_id") == "THF3201MOV-C02")["answer_code"] = "SUSPECT_PREEXISTING_CONTROL"
    case = {
        "question_role": "suspect",
        "selected_legal_routes": [{"route_id": "theft_320_1_movable"}],
        "questions": suspect_questions,
        "interviews": {"victim:default": {"role": "victim", "questions": victim_questions}},
    }
    result = reevaluate_legal_routes_from_answers(case)
    overlay = result["route_fact_overlay"]["theft_320_1_movable"]["possession_before_taking"]
    assert overlay["status"] == "CONFLICT"
    assert set(overlay["observation_question_ids"]) == {"THF3201MOV-C02-V", "THF3201MOV-C02-S"}
    observations = result["route_fact_observations"]["theft_320_1_movable"]["possession_before_taking"]
    assert {item["role"] for item in observations} == {"victim", "suspect"}
    assert result["selected_legal_route_states"]["theft_320_1_movable"]["state"] == "NEED_REVIEW"
