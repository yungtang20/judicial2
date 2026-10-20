from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.markdown_questions import CATALOG
from app.rules import (
    MAX_SELECTED_OFFENSES,
    analyze_gate1,
    alternative_legal_routes,
    build_questions,
    candidate_offenses,
    concise_summary,
    is_victim_code,
    mark_known_questions,
    required_case_numbers,
)
from tests.helpers import BANK, completed_case


def test_candidate_engine_is_deterministic_and_can_return_zero():
    assert candidate_offenses("沒有任何可辨識內容", BANK) == []
    first = candidate_offenses("對方以假客服名義要求匯款，疑似詐騙", BANK)
    assert first == candidate_offenses("對方以假客服名義要求匯款，疑似詐騙", BANK)
    assert first[0]["id"] == "fraud"
    assert first[0]["status"] == "NEED_LEGAL_ROUTE_MAPPING"
    assert first[0]["unknown_elements"]
    theft = candidate_offenses("有人偷走物品", BANK)
    # D1（人工核定 B 修正版，2026-10-20）：財物三路區辨——普通竊盜句不再
    # 自動帶出侵占／強盜 related（真實書類竊盜案典型只連 §320／§47）。
    assert {item["id"] for item in theft} == {"theft"}


def test_hyphenated_women_child_victim_code_is_recognized():
    assert is_victim_code("AW000-A113415") is True


def test_candidate_uses_route_element_matrix_with_traceable_gate1_facts():
    summary = (
        "黃思維意圖為自己不法所有，於民國114年1月23日0時18分許，"
        "在臺北市某夜店內，徒手竊取李○○放在吧臺上的包包及現金1,500元得手。"
    )
    gate1 = analyze_gate1({"summary": summary, "event_time": "", "location": ""}, use_ai=False)
    candidate = next(item for item in candidate_offenses(summary, BANK, gate1) if item["id"] == "theft")
    assert candidate["suggested_legal_route_ids"] == ["theft_320_1_movable"]
    matrix = candidate["route_element_matrix"][0]
    assert matrix["route_id"] == "theft_320_1_movable"
    assert matrix["supported_count"] >= 3
    assert candidate["supporting_fact_refs"]
    assert all(row["status"] in {"SOURCE_SUPPORTED", "ABSENT", "NOT_CHECKABLE"} for row in matrix["elements"])


def test_incapacity_indecency_route_is_ranked_from_direct_source_evidence():
    summary = (
        "A女飲酒後已呈現嘔吐、全身癱軟無力，趙子興乘A女不能抗拒之際，"
        "親吻A女嘴部並伸入內衣撫摸胸部而猥褻得逞。"
    )
    gate1 = analyze_gate1({"summary": summary, "event_time": "", "location": ""}, use_ai=False)
    candidate = next(item for item in candidate_offenses(summary, BANK, gate1) if item["id"] == "sexual")
    assert candidate["suggested_legal_route_ids"] == ["sexual_225_incapacity"]
    route = candidate["route_element_matrix"][0]
    assert route["supported_count"] >= 4
    assert any(
        row["element"] == "不能或不知抗拒狀態" and row["source_excerpts"]
        for row in route["elements"]
    )


def test_general_fraud_and_sexual_image_distribution_routes_are_ranked_by_source_facts():
    fraud_summary = "行為人冒充銀行客服，使被害人陷於錯誤而依指示匯款新臺幣10萬元。"
    fraud_gate1 = analyze_gate1({"summary": fraud_summary, "event_time": "", "location": ""}, use_ai=False)
    fraud = next(item for item in candidate_offenses(fraud_summary, BANK, fraud_gate1) if item["id"] == "fraud")
    assert fraud["suggested_legal_route_ids"] == ["fraud_339_general"]

    privacy_summary = "行為人未經同意將被害人的性影像上傳網路供人觀看。"
    privacy_gate1 = analyze_gate1({"summary": privacy_summary, "event_time": "", "location": ""}, use_ai=False)
    privacy = next(item for item in candidate_offenses(privacy_summary, BANK, privacy_gate1) if item["id"] == "privacy")
    assert privacy["suggested_legal_route_ids"] == ["privacy_319_3_sexual_image_distribution"]


def test_combined_time_and_place_question_is_known_only_when_both_are_present():
    question = {"text": "請說明事件發生的時間與地點。", "kind": "core", "meta": {}}
    mark_known_questions([question], {"times": ["民國114年1月1日"], "places": ["UNKNOWN"]})
    assert "known_from_summary" not in question["meta"]

    mark_known_questions([question], {"times": ["民國114年1月1日"], "places": ["臺北市"]})
    assert question["meta"]["known_from_summary"] is True


def test_common_caseword_variants_still_surface_the_correct_candidate_route():
    summary = "某人冒充銀行客服，要求被害人提供驗證碼並轉帳。"
    candidates = candidate_offenses(summary, BANK)
    assert candidates
    assert candidates[0]["id"] == "fraud"
    assert candidates[0]["candidate_state"] == "NEED_REVIEW"


def test_computer_candidate_requires_specific_conduct():
    assert not any(
        item["id"] == "computer"
        for item in candidate_offenses("醫院電腦辦公區，沒有未授權操作或破壞", BANK)
    )
    assert any(
        item["id"] == "computer"
        for item in candidate_offenses("帳號遭盜用，密碼被他人變更", BANK)
    )


def test_phone_taken_extracts_neutral_facts_without_legal_conclusion():
    raw = {
        "event_time": "2026-10-10T10:30",
        "location": "測試地點",
        "summary": "他把我的手機拿走了。",
    }
    gate1 = analyze_gate1(raw, use_ai=False)
    facts = {item["fact_key"]: item for item in gate1["facts"]}
    assert facts["actor"]["value"] == "他"
    assert facts["action"]["value"] == "取走物品"
    assert facts["object"]["value"] == "手機"
    for key in (
        "original_possession", "consent", "prior_lawful_possession",
        "force_or_threat", "return_agreement", "intent",
    ):
        assert facts[key]["value"] == "UNKNOWN"
    assert not any("犯罪成立" in item["normalized_text"] for item in gate1["facts"])


def test_phone_taken_keeps_competing_routes_and_separate_civil_alternative():
    raw = {
        "event_time": "2026-10-10T10:30",
        "location": "測試地點",
        "summary": "他把我的手機拿走了。",
    }
    gate1 = analyze_gate1(raw, use_ai=False)
    candidates = candidate_offenses(raw["summary"], BANK, gate1)
    # D1（人工核定 B 修正版，2026-10-20）：「把我的手機拿走了」缺受託持有
    # 與強暴脅迫區辨事實，不再自動帶出侵占／強盜 related。
    assert {item["id"] for item in candidates} == {"theft"}
    assert all(item["candidate_state"] == "NEED_REVIEW" for item in candidates)
    alternatives = alternative_legal_routes(gate1)
    assert [item["route_id"] for item in alternatives] == ["civil_possession_dispute"]
    assert alternatives[0]["selectable_as_offense"] is False

def test_candidate_schema_contains_required_fields():
    c = candidate_offenses("對方以假客服名義要求匯款，疑似詐騙", BANK)
    assert len(c) == 1
    item = c[0]
    # New schema fields per spec §5.2
    assert item["candidate_id"] == "candidate:fraud"
    assert item["inclusion_reason"] and "關鍵詞" in item["inclusion_reason"]
    assert item["reservation_reason"] and "結構化事實" in item["reservation_reason"]
    assert item["distinguishing_question_ids"]
    assert item["required_evidence_question_ids"]
    assert item["competition_analysis"] == "NOT_ASSESSED"
    assert item["prohibited_conclusions"] == ["犯罪成立", "故意成立", "因果關係成立", "競合成立"]
    assert item["version"] == "VERIFIED_CURRENT"
    # 法源核實欄位（spec §5.5）
    assert item["source"]["status"] == "VERIFIED_CURRENT"
    assert item["source"]["law_url"].startswith("http")
    assert item["source"]["dataset_version"]


def test_all_runtime_routes_have_explicit_crosswalk_status():
    offenses = {item["id"]: item for item in BANK["offenses"]}
    assert len(offenses) == 44
    assert BANK["legal_route_crosswalk_version"] == "1.1"
    allowed_types = {"substantive", "mixed", "procedural", "protective"}
    allowed_statuses = {
        "PARTIAL_SCOPE", "SPLIT_REQUIRED", "PROCEDURAL_ONLY", "PROTECTIVE_UMBRELLA"
    }
    for offense in offenses.values():
        assert offense["route_type"] in allowed_types
        assert offense["crosswalk_status"] in allowed_statuses
        assert offense["content_review_status"] == "HUMAN_REVIEW_REQUIRED"


def test_opium_route_uses_criminal_code_chapter_twenty_source():
    offense = next(item for item in BANK["offenses"] if item["id"] == "opium")
    source = offense["source"]
    assert source["law_name"] == "中華民國刑法"
    assert source["article_no"] == "第256條至第265條"
    assert "C0000001" in source["law_url"]
    assert offense["crosswalk_status"] == "SPLIT_REQUIRED"
    assert [item["article_no"] for item in offense["legal_routes"]] == [
        "第256條", "第257條", "第258條", "第259條", "第260條",
        "第261條", "第262條", "第263條", "第264條", "第265條",
    ]


# E3→E4 輪（人工複審 2026-10-20）：關鍵字回顯豁免已依人工裁定撤除，
# 單一關鍵字不再保證建立候選。佈線測試的探針改為「關鍵字＋最小事實
# 敘述」，滿足各錨點章「行為與錨點同句」要求；未列出的章不受閘門影響。
_PROBE_NARRATIVE_SUFFIX = {
    "stalking": "，被害人心生畏怖並已明確拒絕。",
    "obstruction": "，公務員執行職務時遭攔阻。",
    "robbery": "，行為人強行把被害人的錢包搶走。",
    "embezzlement": "，將代管物品拒不返還。",
}


def _kw_probe(offense: dict) -> str:
    return offense["keywords"][0] + _PROBE_NARRATIVE_SUFFIX.get(offense["id"], "")


def test_first_child_route_batch_has_reviewable_fact_models():
    expected_counts = {
        "opium": 10,
        "fraud": 10,
        "injury": 10,
        "intimidation": 2,
        "defamation": 6,
        "forgery": 11,
        "computer": 6,
        "sexual_harassment": 5,
        "drugs": 8,
        "state_security": 21,
        "duty": 15,
        "judicial_integrity": 3,
        "voting": 7,
        "disorder": 12,
        "escape": 5,
        "evidence": 3,
        "accusation": 5,
        "currency": 6,
        "securities": 6,
        "weights_measures": 4,
        "graves_religion": 5,
        "theft": 4,
        "aggravated_theft": 1,
        "embezzlement": 5,
        "damage": 6,
        "stalking": 5,
        "public_danger": 2,
        "gambling": 4,
        "homicide": 7,
        "abortion": 5,
        "abandonment": 4,
        "obstruction": 7,
        "sexual": 12,
        "obscenity": 3,
        "marriage": 8,
        "agriculture_commerce": 5,
        "liberty": 15,
        "privacy": 16,
        "robbery": 8,
        "trafficking": 13,
        "juvenile": 4,
        "domestic_violence": 5,
        "child_protection": 5,
        "gender_equality": 6,
    }
    offenses = {item["id"]: item for item in BANK["offenses"]}
    for offense_id, count in expected_counts.items():
        routes = offenses[offense_id]["legal_routes"]
        assert len(routes) == count
        assert len({item["id"] for item in routes}) == count
        assert all(item["fact_elements"] for item in routes)
        assert all(item["review_status"] == "HUMAN_REVIEW_REQUIRED" for item in routes)
        candidate = next(
            item for item in candidate_offenses(_kw_probe(offenses[offense_id]), BANK)
            if item["id"] == offense_id
        )
        assert candidate["legal_routes"] == routes
        assert candidate["legal_route_selection_status"] == "OPTIONAL"
        if offenses[offense_id]["route_type"] in {"procedural", "protective"}:
            expected_status = "PROCEDURAL_FACT_MODEL_REQUIRED"
        elif offenses[offense_id]["crosswalk_status"] == "SPLIT_REQUIRED":
            expected_status = "NEED_LEGAL_ROUTE_MAPPING"
        else:
            expected_status = "NEED_REVIEW"
        assert candidate["status"] == expected_status

    assert sum(len(item.get("legal_routes", [])) for item in offenses.values()) == 310
    assert {
        item["id"] for item in offenses.values() if not item.get("legal_routes")
    } == set()


def test_sexual_harassment_and_sexual_privacy_are_separate_routes():
    offenses = {item["id"]: item for item in BANK["offenses"]}
    harassment = offenses["sexual_harassment"]
    privacy = offenses["privacy"]

    assert harassment["name"] == "性騷擾"
    assert harassment["source"]["law_name"] == "性騷擾防治法"
    assert harassment["source"]["article_no"] == "第2條、第25條"
    assert "D0050074" in harassment["source"]["law_url"]
    assert not ({"性影像", "偷拍", "側錄", "私密影像", "私密照片"} & set(harassment["keywords"]))
    assert {"性影像", "偷拍", "側錄", "私密影像", "私密照片"} <= set(privacy["keywords"])

    candidate_ids = {item["id"] for item in candidate_offenses("有人偷拍性影像", BANK)}
    assert "privacy" in candidate_ids
    assert "sexual_harassment" not in candidate_ids


def test_obstruction_excludes_invalidated_routes_and_narrows_article_140():
    offense = next(item for item in BANK["offenses"] if item["id"] == "obstruction")
    active_ids = {item["id"] for item in offense["legal_routes"]}
    excluded = {item["id"]: item for item in offense["excluded_legal_routes"]}
    assert "obstruction_141_1_false_statement" not in active_ids
    assert excluded["obstruction_141_1_false_statement"]["status"] == "UNCONSTITUTIONAL_INVALIDATED"
    assert excluded["obstruction_140_insult_duty"]["status"] == "UNCONSTITUTIONAL_INVALIDATED"
    article_140 = next(item for item in offense["legal_routes"] if item["article_no"] == "第140條")
    assert article_140["constitutional_status"] == "CONSTITUTIONALLY_NARROWED"
    assert "妨害公務之主觀目的" in article_140["fact_elements"]
    assert "足以影響公務員執行公務" in article_140["fact_elements"]


def test_empty_or_split_routes_fail_closed_in_candidate_metadata():
    for offense in BANK["offenses"]:
        if not offense.get("elements") or offense["crosswalk_status"] == "SPLIT_REQUIRED":
            candidate = next(
                item for item in candidate_offenses(_kw_probe(offense), BANK)
                if item["id"] == offense["id"]
            )
            expected = (
                "PROCEDURAL_FACT_MODEL_REQUIRED"
                if offense["route_type"] in {"procedural", "protective"}
                else "NEED_LEGAL_ROUTE_MAPPING"
            )
            assert candidate["status"] == expected
            assert candidate["element_model_status"] == "UNMAPPED"


def test_procedural_and_protective_umbrellas_do_not_fake_criminal_elements():
    cases = {
        "juvenile": ("procedural", "PROCEDURAL_ONLY"),
        "domestic_violence": ("protective", "PROTECTIVE_UMBRELLA"),
        "child_protection": ("protective", "PROTECTIVE_UMBRELLA"),
        "gender_equality": ("procedural", "PROCEDURAL_ONLY"),
    }
    by_id = {item["id"]: item for item in BANK["offenses"]}
    for offense_id, expected in cases.items():
        offense = by_id[offense_id]
        assert (offense["route_type"], offense["crosswalk_status"]) == expected
        candidate = next(
            item for item in candidate_offenses(offense["keywords"][0], BANK)
            if item["id"] == offense_id
        )
        assert candidate["status"] == "PROCEDURAL_FACT_MODEL_REQUIRED"
        assert candidate["unknown_elements"] == ["PROCEDURAL_FACT_MODEL_REQUIRED"]




def test_analyze_gate1_schema_and_provenance():
    intake = {
        "summary": "測試案件：有人在店內拿取貨物未結帳。",
        "event_time": "2026-10-10T10:30",
        "location": "測試地點",
        "has_victim": True,
    }
    g1 = analyze_gate1(intake)
    # Must contain facts list with required fields
    assert "facts" in g1
    facts = g1["facts"]
    assert len(facts) >= 5  # event + 4 unknowns
    for f in facts:
        assert "fact_id" in f
        assert f["source_ref"] == "intake.summary"
        assert "source_excerpt" in f
        assert "normalized_text" in f
        assert "fact_status" in f
        assert f["fact_status"] in ("當事人陳述", "未知", "客觀觀察")
        assert "review_status" in f
        assert f["review_status"] == "HUMAN_REVIEW_REQUIRED"
    # Backward-compatible string arrays must exist
    for key in ("people", "events", "times", "places", "objects", "behaviors", "unknowns"):
        assert key in g1
        assert isinstance(g1[key], list)
    # causation is a string
    assert "causation" in g1
    assert isinstance(g1["causation"], str)
    # times must be ROC era format
    assert g1["times"][0].startswith("115年10月10日") and "時30分" in g1["times"][0]
    assert g1["review_status"] == "HUMAN_REVIEW_REQUIRED"


def test_gate1_decomposes_assault_narrative_into_eight_fact_categories():
    summary = (
        "曹富生、顏大鈞前與羅世亮在法務部矯正署新店戒治所中因抽煙問題生有嫌隙，"
        "竟共同基於傷害他人身體之犯意聯絡，於民國114年4月14日14時5分許，"
        "在新店戒治所靜舍前廣場上，共同徒手毆打羅世亮，致羅世亮因而受有"
        "上唇瘀腫、下唇撕裂傷及門牙折斷等傷害。"
    )
    gate1 = analyze_gate1({"summary": summary, "event_time": "UNKNOWN", "location": "UNKNOWN"}, use_ai=False)
    assert gate1["people"] == ["曹富生", "顏大鈞前", "羅世亮"]
    assert gate1["times"] == ["民國114年4月14日14時5分許"]
    assert gate1["places"] == ["法務部矯正署新店戒治所", "新店戒治所靜舍前廣場"]
    assert gate1["objects"] == ["他人身體"]
    assert gate1["behaviors"] == ["共同徒手毆打羅世亮"]
    assert gate1["results"] == ["上唇瘀腫、下唇撕裂傷及門牙折斷"]


def test_gate1_decomposes_detailed_theft_narrative_without_raw_summary_fallback():
    summary = (
        "黃思維意圖為自己不法之所有，基於竊盜之犯意，於民國114年1月23日0時18分許，"
        "在臺北市○○區○○路00號0樓之夜店內，徒手竊取李○○放置於吧臺上之包包，"
        "得手後即攜往男廁所，將包包內現金1,500元取出放於身上口袋，"
        "李○○即上前取回其遭竊之包包，嗣夜店員工鍾○○透過無線電通報，並壓制黃思維。"
    )
    gate1 = analyze_gate1({"summary": summary, "event_time": "", "location": ""}, use_ai=False)

    assert gate1["segmentation_source"] == "rules:narrative"
    assert gate1["people"]
    assert gate1["behaviors"]
    assert gate1["objects"]
    assert gate1["results"]
    assert gate1["evidence"]
    assert gate1["unknowns"] == []
    assert not any(item["source_excerpt"] == summary for item in gate1["facts"])
    assert all(item["source_excerpt"] in summary for item in gate1["facts"] if item["source_excerpt"])


def test_gate1_decomposes_robbery_assault_narrative_with_compatibility_characters():
    summary = (
        "洪丞葦因需錢孔急，竟意圖為自己不法所有，基於搶奪、傷害等犯意，"
        "於民國114年7月14日23時許，前往張○○所經營、位在新北市○○區○○街000號之彩券行內，"
        "持預藏之汽油朝張○○潑灑之後，進入彩券行櫃台內拉開櫃台抽屜，"
        "搶奪抽屜內現金10萬9,000元得手，因防護贓物、脫免逮捕而徒手毆打張○○，"
        "使張○○受有右側眼點狀角膜炎、左側手腕挫傷等傷害，並施以強暴、脅迫後逃離現場。"
    )
    gate1 = analyze_gate1({"summary": summary, "event_time": "", "location": ""}, use_ai=False)

    assert gate1["segmentation_source"] == "rules:narrative"
    assert "洪丞葦" in gate1["people"]
    assert "張○○" in gate1["people"]
    assert any("搶奪" in value for value in gate1["behaviors"])
    assert any("汽油" in value for value in gate1["objects"])
    assert gate1["results"]


def test_injury_questions_include_reviewed_single_assault_supplement():
    gate1 = analyze_gate1({
        "summary": "雙方因抽煙問題爭執，涉嫌人徒手毆打對方，造成上唇撕裂傷。",
        "event_time": "UNKNOWN",
        "location": "UNKNOWN",
    }, use_ai=False)
    bank = __import__("app.rules", fromlist=["load_bank"]).load_bank(
        Path(__file__).resolve().parents[1] / "data" / "question_bank.json"
    )
    questions = build_questions(bank, "suspect", ["injury"], gate1=gate1)
    supplemental = [item for item in questions if item.get("kind") == "supplemental"]
    assert len(supplemental) == 4
    assert all(item["source"]["status"] == "HUMAN_REVIEW_REQUIRED" for item in supplemental)
    assert any("誰先動手" in item["text"] for item in supplemental)


def test_max_selected_offenses_guard():
    """MAX_SELECTED_OFFENSES 為 3（8 頁防線實測容量：97 題/8 頁，每罪章 core+xls 約 24 題）。"""
    assert MAX_SELECTED_OFFENSES == 3
    # 實際防護由 test_e2e_max_selected_offenses_enforced 驗證（4 罪章 → 422）

def test_question_bank_questions_are_single_judgment_questions():
    for group in BANK["common"].values():
        for question in group:
            assert question["text"].count("？") <= 1
    for offense in BANK["offenses"]:
        for element in offense["elements"]:
            assert element["victim"].count("？") <= 1
            assert element["suspect"].count("？") <= 1


def test_all_markdown_catalog_entries_are_available_for_manual_selection():
    available = {item["id"] for item in BANK["offenses"]}
    assert {item["id"] for item in CATALOG} <= available
    for offense in BANK["offenses"]:
        if offense["id"] in {item["id"] for item in CATALOG}:
            assert offense["section_questions"]["victim"] or offense["section_questions"]["suspect"]


def test_suspect_common_questions_do_not_accuse_false_statement():
    texts = [item["text"] for item in BANK["common"]["suspect"]]
    assert all("推卸責任而作不實陳述" not in text for text in texts)


def test_contempt_of_legislature_and_judicial_integrity_routes_are_separate():
    catalog = {item["id"]: item for item in CATALOG}
    assert "藐視國會" not in catalog["obstruction"]["keywords"]
    assert "藐視國會" not in catalog["judicial_integrity"]["keywords"]
    assert catalog["judicial_integrity"]["name"] == "妨害司法公正"

    contempt_ids = {item["id"] for item in candidate_offenses("藐視國會", BANK)}
    integrity_ids = {item["id"] for item in candidate_offenses("妨害司法公正", BANK)}
    assert "obstruction" not in contempt_ids
    assert "judicial_integrity" not in contempt_ids
    assert "judicial_integrity" in integrity_ids
    assert "obstruction" not in integrity_ids

    offenses = {item["id"]: item for item in BANK["offenses"]}
    obstruction_source = offenses["obstruction"]["source"]
    integrity_source = offenses["judicial_integrity"]["source"]
    assert any(item["article_no"] == "第141條之1" for item in obstruction_source["related_articles"])
    assert "第141條之1" not in integrity_source["label"]
    assert integrity_source["article_no"] == "第172條之1至第172條之3"
    assert {item["article_no"] for item in integrity_source["related_articles"]} == {"第172條之2", "第172條之3"}


def test_invalidated_chapter_five_one_is_not_a_runtime_question_route():
    question_root = Path(__file__).resolve().parents[2] / "questions"
    obstruction = (question_root / "obstruction.md").read_text(encoding="utf-8")
    integrity = (question_root / "judicial-integrity.md").read_text(encoding="utf-8")
    index = (question_root / "index.md").read_text(encoding="utf-8")
    assert "§141-1" in obstruction
    assert "§141-1" not in integrity
    assert "第5章之1藐視國會罪、第10章之1" not in integrity
    assert "§141-1 已違憲失效" in index
    assert "| 10之1 | 妨害司法公正 |" in index


def test_question_budget_caps_offense_questions_for_eight_page_guard():
    # spec §7.5：core/公司罪章題不得裁除；runtime 限 MAX_SELECTED_OFFENSES（6）。
    # 選擇上限內：offense 題 <= 30，core 優先於區分/加重，公司必問逐字保留。
    from app.rules import MAX_SELECTED_OFFENSES
    selected = ["theft", "embezzlement", "fraud"]  # 實測 97 題 = 8 頁極限（3 罪章）
    assert MAX_SELECTED_OFFENSES == 3
    questions = build_questions(BANK, "victim", selected)
    offense_questions = [item for item in questions if item["kind"] not in {"common", "company"}]
    assert len(offense_questions) <= 78  # 8 頁防線：offense 題上限（97 總容量 - 19 company/common）
    kinds = [item["kind"] for item in offense_questions]
    first_distinguishing = kinds.index("distinguishing") if "distinguishing" in kinds else len(kinds)
    assert kinds[:first_distinguishing].count("core") > 0
    company_count = sum(item["kind"] == "company" for item in questions)
    assert company_count == 7  # victim 公司必問 7 題逐字保留
    # 單一罪章時也維持公司必問與預算
    single = build_questions(BANK, "victim", ["theft"])
    assert sum(item["kind"] in {"common", "company"} for item in single) == 12 + 7
    assert sum(item["kind"] not in {"common", "company"} for item in single) <= 78

    # 超過 runtime 選擇上限或 core 總量爆表時 fail closed（spec §7.5 不得靜默裁 core）
    import pytest
    from app.rules import RuleError
    all_ids = [item["id"] for item in BANK["offenses"]]
    with pytest.raises(RuleError):
        build_questions(BANK, "victim", all_ids)


def test_case_number_rules_cover_fraud_and_alias():
    case = completed_case(offense="fraud")
    assert required_case_numbers(case) == ["proof", "case_165"]
    case["intake"]["victim_identifier"] = "AW001001523"
    assert required_case_numbers(case) == ["proof", "case_165", "women_child"]
    assert is_victim_code("aw001001523")


def test_summary_limit_is_500_unicode_characters_without_truncation():
    result = concise_summary("字" * 500)
    assert len(result) == 500
    assert not result.endswith("…")


def test_original_template_sources_match_recorded_hashes():
    manifest_path = Path(__file__).resolve().parents[1] / "data" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        path = (manifest_path.parent / source["path"]).resolve()
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == source["sha256"]

def test_law_reference_builds_verified_source_from_cache(tmp_path, monkeypatch):
    from app import law_reference as lr
    cache = {
        "刑法:320": {
            "law_name": "中華民國刑法", "article_no": "第320條",
            "article_content": "意圖為自己或第三人不法之所有…",
            "law_url": "https://law.moj.gov.tw/LawClass/LawSearchNo.aspx?PCode=C0010001",
            "law_modified_date": "2026-07-22", "dataset_version": "2026-10-02",
            "abolished": False, "verified_at": "2026-10-12T00:00:00+00:00",
        }
    }
    monkeypatch.setattr(lr, "CACHE_PATH", tmp_path / "law_cache.json")
    lr.save_cache(cache)
    source = lr.build_verified_source("刑法", "320")
    assert source["status"] == "VERIFIED_CURRENT"
    assert source["law_name"] == "中華民國刑法"
    assert source["dataset_version"] == "2026-10-02"


def test_law_reference_rejects_abolished_article(tmp_path, monkeypatch):
    from app import law_reference as lr
    cache = {
        "舊法:1": {
            "law_name": "舊法", "article_no": "第1條",
            "article_content": "…", "law_url": "https://example",
            "law_modified_date": "2000-01-01", "dataset_version": "2026-10-02",
            "abolished": True, "verified_at": "2026-10-12T00:00:00+00:00",
        }
    }
    monkeypatch.setattr(lr, "CACHE_PATH", tmp_path / "law_cache.json")
    lr.save_cache(cache)
    import pytest
    with pytest.raises(lr.LawReferenceError, match="已廢止"):
        lr.build_verified_source("舊法", "1")


def test_bank_sources_are_verified_current():
    for offense in BANK["offenses"]:
        assert offense["source"]["status"] == "VERIFIED_CURRENT", f"{offense['id']} 法源未核實"
        assert offense["source"]["law_url"]
        assert offense["source"]["dataset_version"]


def test_all_related_articles_are_verified_and_in_cache():
    """核對題庫中所有 related_articles 均在離線快照中，非空且未廢止。"""
    from app.law_reference import get_law_article
    checked = 0
    for offense in BANK["offenses"]:
        for rel in offense.get("source", {}).get("related_articles", []):
            entry = get_law_article(rel["law_name"], rel["article_no"], use_cache=True)
            assert entry, f"{offense['id']} 關聯法條 {rel['law_name']} {rel['article_no']} 查無"
            assert not entry["abolished"], f"{offense['id']} 關聯法條已廢止"
            assert entry["article_content"].strip()
            checked += 1
    assert checked >= 6, f"預期至少 6 條關聯法條，實查 {checked} 條"

def test_event_time_before_law_amendment_triggers_warning():
    from app.law_reference import check_event_time_against_law
    w = check_event_time_against_law("2020-01-01T10:00", "2026-07-22")
    assert w is not None
    assert w["level"] == "EVENT_TIME_BEFORE_LAW_AMENDMENT"


def test_event_time_after_law_amendment_no_warning():
    from app.law_reference import check_event_time_against_law
    assert check_event_time_against_law("2026-08-01T10:00", "2026-07-22") is None


def test_event_time_warning_empty_inputs():
    from app.law_reference import check_event_time_against_law
    assert check_event_time_against_law("", "2026-07-22") is None
    assert check_event_time_against_law("2020-01-01T10:00", "") is None


def test_set_offenses_records_temporal_law_warning():
    from app.workflow import create_case, apply_action
    from tests.helpers import intake
    from tests.helpers import BANK as bank
    raw_intake = intake()
    raw_intake["event_time"] = "2020-01-01T10:00"
    case = create_case(raw_intake, bank)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, bank)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, bank)
    # 行為時間 2020 早於刑法 320 修正日 2026-07-22 → 應有警示
    assert case.get("temporal_law_warnings")
    assert case["temporal_law_warnings"][0]["offense_id"] == "theft"

def test_roc_time_boundaries():
    """民國前日期不得輸出誤導性的「0年」（第十輪盤點發現）。"""
    from app.roc_time import format_roc_time, format_roc_date
    # 民國前
    assert format_roc_time("1911-12-31T23:59") == "民國前1年12月31日23時59分"
    assert format_roc_date("1911-06-15T00:00") == "民國前1年6月15日"
    # 民國元年
    assert format_roc_time("1912-01-01T00:00") == "1年1月1日0時00分"
    # 正常
    assert format_roc_time("2026-10-10T10:30") == "115年10月10日10時30分"
    # 空白與垃圾字串保持既有行為
    assert format_roc_time("") == "年月日時分"
    assert format_roc_time("garbage") == "garbage"


def test_constitutional_validity_warning_for_invalidated_article():
    """驗證憲法法庭判決宣告違憲失效條文檢驗（113年憲判字第9號對刑法第141條之1）。"""
    from app.law_reference import check_constitutional_validity
    w = check_constitutional_validity("中華民國刑法", "第141條之1")
    assert w is not None
    assert w["status"] == "UNCONSTITUTIONAL_INVALIDATED"
    assert "113 年憲判字第 9 號" in w["judgment"]
    assert "失其效力" in w["effect"]

    # 模糊別名檢驗
    w_alt = check_constitutional_validity("刑法", "141-1")
    assert w_alt is not None
    assert w_alt["status"] == "UNCONSTITUTIONAL_INVALIDATED"

    # 有效條文無警示
    assert check_constitutional_validity("中華民國刑法", "第320條") is None
    assert check_constitutional_validity("刑法", "339") is None


def test_set_offenses_records_constitutional_warning_for_obstruction():
    """當選中 obstruction（含 §141-1 關聯路由）時，案件必須自動記錄憲法法庭違憲失效警示。"""
    from app.workflow import create_case, apply_action
    from tests.helpers import intake
    from tests.helpers import BANK as bank
    case = create_case(intake(), bank)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, bank)
    case = apply_action(case, "set_offenses", {"offense_ids": ["obstruction"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, bank)
    warnings = case.get("constitutional_warnings", [])
    assert len(warnings) >= 1
    assert any(w["article_no"] == "第141條之1" for w in warnings)
    assert any("113 年憲判字第 9 號" in w["judgment"] for w in warnings)


def test_nonexistent_date_passthrough_is_visible():
    """2026-02-29（不存在）原樣返回西格式——可見但未轉換；
    筆錄中承辦人可察覺（文件其余欄位皆民國格式）。"""
    from app.roc_time import format_roc_time
    assert format_roc_time("2026-02-29T10:00") == "2026-02-29T10:00"


def _synthetic_offense(routes: list[dict]) -> dict:
    return {
        "id": "synthetic",
        "name": "測試罪章",
        "route_type": "substantive",
        "crosswalk_status": "SPLIT_REQUIRED",
        "legal_routes": routes,
    }


def test_candidate_without_supported_elements_names_no_route():
    """全部路線都無可回查原文時，不得指名任何路線（RC-E2）。

    matrix[0] 只是「元素最少」的排序結果，不代表本案方向；照抄會把無關罪名的
    要件寫進候選說明（實例：竊盜案被說明成「電能、熱能或其他能量準動產」）。
    """
    from app.rules import _attach_element_evidence

    offense = _synthetic_offense([
        {"id": "unrelated_a", "name": "甲路線", "fact_elements": ["他人動產及原持有狀態"]},
        {"id": "unrelated_b", "name": "乙路線", "fact_elements": ["本工具無此要件的比對依據"]},
    ])
    candidate = {"matched_terms": ["偷"]}
    _attach_element_evidence(candidate, offense, "本摘要與路線要件毫無交集。", None)
    assert candidate["suggested_legal_route_ids"] == []
    assert "甲路線" not in candidate["inclusion_reason"]
    assert "乙路線" not in candidate["inclusion_reason"]
    assert "路線須由人工判斷" in candidate["inclusion_reason"]
    # 待補問清單仍須保留（不得清空，否則後續補問與收縮失去依據）
    assert candidate["unknown_elements"] == ["他人動產及原持有狀態", "本工具無此要件的比對依據"]
    # 「已比對而原文未見」與「本工具沒有比對依據」必須分開，不得同標 UNKNOWN
    assert {
        row["element"]: row["status"]
        for route in candidate["route_element_matrix"]
        for row in route["elements"]
    } == {
        "他人動產及原持有狀態": "ABSENT",
        "本工具無此要件的比對依據": "NOT_CHECKABLE",
    }


def test_unmapped_element_is_not_checkable_even_when_quoted_verbatim():
    """沒有受審查比對依據的要件標為 NOT_CHECKABLE；不得以「要件字面出現在摘要」充當比對。"""
    from app.rules import _attach_element_evidence

    element = "本工具無此要件的比對依據"
    offense = _synthetic_offense([
        {"id": "unmapped", "name": "未建表路線", "fact_elements": [element]},
    ])
    candidate = {"matched_terms": ["偷"]}
    # 摘要逐字寫出要件字面（就像判決引用法條），仍不得算作有原文支持
    _attach_element_evidence(candidate, offense, f"判決理由逐字引用：{element}。", None)
    route = candidate["route_element_matrix"][0]
    assert route["elements"][0]["status"] == "NOT_CHECKABLE"
    assert route["supported_count"] == 0
    assert route["not_checkable_count"] == 1


def test_route_suggestion_requires_the_shared_minimum_support():
    """只有 1 個要件可回查原文時不得建議該路線；建議與合格候選共用門檻 2（RC-E3）。"""
    from app.rules import _attach_element_evidence, ROUTE_MIN_SUPPORTED_ELEMENTS

    offense = _synthetic_offense([
        {
            "id": "half_supported",
            "name": "半支持路線",
            "fact_elements": ["他人動產及原持有狀態", "未經同意竊取並破壞原持有"],
        },
    ])
    candidate = {"matched_terms": ["偷"]}
    _attach_element_evidence(candidate, offense, "摘要只記載包包。", None)
    assert candidate["suggested_legal_route_ids"] == []
    assert "半支持路線" in candidate["inclusion_reason"]  # 有支持才說明該路線的支持程度
    assert "1/2" in candidate["inclusion_reason"]
    assert ROUTE_MIN_SUPPORTED_ELEMENTS == 2


def test_route_suggestion_and_state_share_one_threshold():
    """被建議的路線，其候選狀態必為合格——建議與狀態不得各自設門檻。"""
    summaries = (
        "有人偷走物品",
        "對方以假客服名義要求匯款，疑似詐騙",
        "甲持刀砍傷乙，乙受有手臂撕裂傷。",
        "甲在停車場破壞乙的車窗玻璃，並取走車內物品。",
    )
    for summary in summaries:
        for item in candidate_offenses(summary, BANK):
            states = item.get("legal_route_states")
            if states is None:
                continue
            for route_id in item.get("suggested_legal_route_ids", []):
                assert states.get(route_id) == "ELIGIBLE_CANDIDATE", (summary, route_id, states)
