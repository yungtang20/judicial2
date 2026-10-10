from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.markdown_questions import CATALOG
from app.rules import build_questions, candidate_offenses, concise_summary, is_victim_code, required_case_numbers
from tests.helpers import BANK, completed_case


def test_candidate_engine_is_deterministic_and_can_return_zero():
    assert candidate_offenses("沒有任何可辨識內容", BANK) == []
    first = candidate_offenses("對方以假客服名義要求匯款，疑似詐騙", BANK)
    assert first == candidate_offenses("對方以假客服名義要求匯款，疑似詐騙", BANK)
    assert first[0]["id"] == "fraud"
    assert first[0]["status"] == "NEED_REVIEW"
    assert first[0]["unknown_elements"]
    theft = candidate_offenses("有人偷走物品", BANK)
    assert {item["id"] for item in theft} >= {"theft", "embezzlement", "aggravated_theft"}


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


def test_question_budget_caps_offense_questions_for_eight_page_guard():
    selected = [item["id"] for item in BANK["offenses"]]
    questions = build_questions(BANK, "victim", selected)
    offense_questions = [item for item in questions if item["kind"] not in {"common", "company"}]
    assert len(offense_questions) <= 30
    # 核心題優先於區分與加重題；公司必問完整保留
    kinds = [item["kind"] for item in offense_questions]
    first_distinguishing = kinds.index("distinguishing") if "distinguishing" in kinds else len(kinds)
    assert kinds[:first_distinguishing].count("core") > 0
    company_count = sum(item["kind"] == "company" for item in questions)
    assert company_count == 7  # victim 公司必問 7 題逐字保留
    # 單一罪章時也維持公司必問與預算
    single = build_questions(BANK, "victim", ["theft"])
    assert sum(item["kind"] in {"common", "company"} for item in single) == 12 + 7
    assert sum(item["kind"] not in {"common", "company"} for item in single) <= 30


def test_case_number_rules_cover_fraud_and_alias():
    case = completed_case(offense="fraud")
    assert required_case_numbers(case) == ["proof", "case_165"]
    case["intake"]["victim_identifier"] = "AW001001523"
    assert required_case_numbers(case) == ["proof", "case_165", "women_child"]
    assert is_victim_code("aw001001523")


def test_summary_is_at_most_100_unicode_characters():
    result = concise_summary("字" * 130)
    assert len(result) == 100
    assert result.endswith("…")


def test_original_template_sources_match_recorded_hashes():
    manifest_path = Path(__file__).resolve().parents[1] / "data" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        path = (manifest_path.parent / source["path"]).resolve()
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == source["sha256"]
