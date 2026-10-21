from pathlib import Path

from app.ai import build_lawbank_analysis_prompt, build_analyze_prompt
from app.server import _local_analysis_payload


def test_local_analysis_endpoint_payload_preserves_candidate_status_and_review_notice():
    payload = _local_analysis_payload("有人拿走另一個人的手機，對方報案。")
    assert payload["mode"] == "rules-fallback"
    assert payload["candidate_result"]["candidates"]
    assert payload["analysis"]["conclusion"].endswith("僅供參考，須人工審核。")


def test_prompts_share_four_candidate_and_no_person_force_robbery_rules():
    prompt1 = "\n".join(item["content"] for item in build_analyze_prompt("案情", [{"id": "theft", "name": "竊盜"}]))
    prompt2 = "\n".join(item["content"] for item in build_lawbank_analysis_prompt(
        "案情", {"candidates": [], "status": {}}, "法條原文"
    ))
    assert "1 至 4" in prompt1
    assert "不要優先列強盜" in prompt1
    assert "status" in prompt2 and "practical_risk" in prompt2
    assert "僅供參考，須人工審核" in prompt2


def test_standalone_html_exposes_demo_and_api_modes():
    html = Path(__file__).parents[1].parent / "lawbank-engine.html"
    text = html.read_text(encoding="utf-8")
    assert "示範模式（固定資料）" in text
    assert "真實 API（本機規則流程）" in text
    assert "fetch(endpoint" in text

