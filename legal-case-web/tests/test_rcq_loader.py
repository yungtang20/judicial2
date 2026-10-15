from __future__ import annotations

import re
from pathlib import Path

from app.rcq_loader import (
    RUNTIME_ENABLED,
    check_rcq_quality_gates,
    generate_rcq_review_worksheet,
    parse_rcq_file,
)


def test_rcq_runtime_disabled_by_default():
    """未經人工審核前，RCQ 接線閘門必須為 False。

    治理依據：docs/QUESTION_DESIGN_AND_USE.md §8。
    """
    assert RUNTIME_ENABLED is False


def test_parse_rcq_file_count_and_fields():
    """解析 443 題，欄位完整性。"""
    questions = parse_rcq_file()
    assert len(questions) == 443
    for q in questions:
        assert q["id"].startswith("RCQ-")
        assert q["text"].strip()
        assert q["role"] in {"被害人", "涉嫌人/行為人", "證人/保管人"}
        assert q["chapter"]
        assert q["category"]


def test_rcq_quality_gates_automated_pass():
    """驗證 Q1 誘導式、Q2 預判定性、Q3 雙重問號全數為 0。"""
    questions = parse_rcq_file()
    gates = check_rcq_quality_gates(questions)
    assert gates["passed"] is True
    assert len(gates["q1_leading_hits"]) == 0
    assert len(gates["q2_prejudged_hits"]) == 0
    assert len(gates["q3_multiple_questions_hits"]) == 0


def test_rcq_zero_collision_with_existing_question_files():
    """RCQ ID 與既有 questions/*.md 中 1400+ 道題目零衝突。"""
    questions = parse_rcq_file()
    rcq_ids = {q["id"] for q in questions}

    q_dir = Path(__file__).resolve().parents[2] / "questions"
    existing_ids = set()
    if q_dir.exists():
        for p in q_dir.glob("*.md"):
            for m in re.finditer(r"-\s+\*\*([A-Za-z0-9_-]+)\*\*", p.read_text(encoding="utf-8")):
                existing_ids.add(m.group(1))

    collisions = rcq_ids & existing_ids
    assert len(collisions) == 0, f"衝突 ID: {collisions}"


def test_generate_rcq_review_worksheet(tmp_path):
    """驗證人工審核工作底稿產出與格式。"""
    out = tmp_path / "test_rcq_worksheet.md"
    content = generate_rcq_review_worksheet(out_path=out)
    assert out.exists()
    assert "HUMAN_REVIEW_WORKSHEET" in content
    assert content.count("| RCQ-") == 443
    assert content.count("☐ 同意接線") == 443
    assert "審核簽署" in content
