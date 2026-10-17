from __future__ import annotations

import json
from copy import deepcopy
import io
from pathlib import Path

import pytest

from app.acts import extract_acts
from app.documents import DocumentError, checked_interview_docx
from app.rules import RuleError, analyze_gate1, concise_summary
from app.workflow import WorkflowError, apply_action, create_case
from tests.helpers import BANK, completed_case, intake


def test_statement_summary_preserves_500_unicode_characters_without_ellipsis():
    summary = "𠮷" * 500
    assert concise_summary(summary) == summary
    case = create_case(intake(summary=summary), BANK)
    assert case["brief_summary"] == summary
    assert len(case["brief_summary"]) == 500
    assert not case["brief_summary"].endswith("…")


def test_statement_summary_rejects_501_characters_but_initial_case_input_is_unlimited():
    with pytest.raises(RuleError, match="500"):
        concise_summary("字" * 501)
    case = create_case(intake(summary="字" * 501), BANK)
    assert len(case["intake"]["summary"]) == 501
    assert len(case["brief_summary"]) == 500


def test_gate1_rejects_501_character_update_without_partial_mutation():
    case = create_case(intake(summary="原始摘要"), BANK)
    before = deepcopy(case)
    with pytest.raises(RuleError, match="500"):
        apply_action(case, "update_gate1", {"gate1": {"events": ["字" * 501]}}, BANK)
    assert case == before


def test_500_character_summary_is_complete_in_brief_text_and_docx():
    from docx import Document
    from app.documents import brief_docx, brief_text

    summary = "字" * 500
    case = completed_case()
    case["brief_summary"] = summary
    assert f"案情摘要：{summary}" in brief_text(case, "victim")
    document = Document(io.BytesIO(brief_docx(case, "victim")))
    assert summary in "\n".join(paragraph.text for paragraph in document.paragraphs)


def test_company_general_templates_have_company_designated_roles():
    manifest_path = Path(__file__).resolve().parents[1] / "data" / "source_manifest.json"
    sources = json.loads(manifest_path.read_text(encoding="utf-8"))["sources"]
    expected = {
        "general-victim": ("../../通用被害人筆錄.doc", "victim"),
        "general-suspect": ("../../通用涉嫌人筆錄.doc", "suspect"),
        "general-transfer": ("../../通用涉嫌人筆錄（移送）.doc", "transfer"),
    }
    indexed = {item.get("template_id"): item for item in sources if item.get("template_id")}
    assert set(expected) <= set(indexed)
    for template_id, (path, role) in expected.items():
        item = indexed[template_id]
        assert item["path"] == path
        assert item["assigned_role"] == role
        assert item["role_authority"] == "COMPANY_DESIGNATED"
        assert item["source_version"] == "UNKNOWN"
        assert item["extraction_version"]


def test_gate1_rules_split_source_statements_without_inference():
    summary = "甲在商店拿走手機。乙說他沒有看見過程；監視器畫面仍待查。"
    gate1 = analyze_gate1(intake(summary=summary), use_ai=False)
    source_facts = [fact for fact in gate1["facts"] if not fact.get("fact_key")]
    assert [fact["source_excerpt"] for fact in source_facts] == [
        "甲在商店拿走手機。",
        "乙說他沒有看見過程；",
        "監視器畫面仍待查。",
    ]
    assert gate1["events"] == [fact["source_excerpt"] for fact in source_facts]
    assert all(fact["source_excerpt"] in summary for fact in source_facts)
    assert all(fact["machine_status"] == "FACT" for fact in source_facts)
    assert all(fact["review_status"] == "HUMAN_REVIEW_REQUIRED" for fact in source_facts)
    assert all(not fact["knowledge_or_intent"] and not fact["causal_relation"] for fact in source_facts)


def test_property_facts_augment_source_facts_and_unknowns_do_not_create_acts():
    summary = "甲把我的手機拿走。我沒有同意。"
    gate1 = analyze_gate1(intake(summary=summary), use_ai=False)
    assert [fact["source_excerpt"] for fact in gate1["facts"] if not fact.get("fact_key")] == [
        "甲把我的手機拿走。",
        "我沒有同意。",
    ]
    keyed = {fact["fact_key"]: fact for fact in gate1["facts"] if fact.get("fact_key")}
    assert {"actor", "action", "object", "intent"} <= set(keyed)
    assert keyed["intent"]["machine_status"] == "UNKNOWN"
    assert all(act["action"] for act in extract_acts(gate1))
    assert all(
        gate1_fact.get("machine_status") != "UNKNOWN"
        for act in extract_acts(gate1)
        for gate1_fact in gate1["facts"]
        if gate1_fact["fact_id"] in act["related_fact_ids"]
    )


def test_machine_status_enum_is_validated_and_legacy_fact_is_compatible():
    case = create_case(intake(summary="一般陳述。"), BANK)
    with pytest.raises(WorkflowError, match="machine_status"):
        apply_action(case, "update_gate1", {"gate1": {"facts": [{"machine_status": "VERIFIED"}]}}, BANK)

    updated = apply_action(case, "update_gate1", {
        "gate1": {"facts": [{
            "fact_id": "legacy-1",
            "source_excerpt": "一般陳述。",
            "normalized_text": "一般陳述。",
            "fact_status": "當事人陳述",
        }]}
    }, BANK)
    assert updated["gate1"]["facts"][0]["machine_status"] == "FACT"
    assert updated["gate1"]["events"] == ["一般陳述。"]
    assert updated["brief_summary"] == "一般陳述。"


@pytest.mark.parametrize("role", ["victim", "suspect", "transfer"])
def test_each_role_document_has_its_own_eight_page_gate(monkeypatch, role):
    from app import documents

    case = completed_case(role)
    monkeypatch.setattr(documents, "interview_docx", lambda _case, _role: b"PK-role-document")
    monkeypatch.setattr(documents, "verified_page_count", lambda _data: 8)
    assert checked_interview_docx(case, role)[1] == 8

    monkeypatch.setattr(documents, "verified_page_count", lambda _data: 9)
    with pytest.raises(DocumentError, match="超過 8 頁"):
        checked_interview_docx(case, role)
