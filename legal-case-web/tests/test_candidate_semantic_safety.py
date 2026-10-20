from __future__ import annotations

import pytest

from app.rules import analyze_gate1, candidate_offenses
from app.workflow import WorkflowError, apply_action, create_case
from tests.helpers import BANK


def _candidates(summary: str) -> list[dict]:
    gate1 = analyze_gate1({"summary": summary, "event_time": "", "location": ""}, use_ai=False)
    return candidate_offenses(summary, BANK, gate1)


def _candidate(summary: str, offense_id: str) -> dict:
    return next(item for item in _candidates(summary) if item["id"] == offense_id)


def _supported_excerpts(candidate: dict) -> list[str]:
    return [
        excerpt
        for route in candidate.get("route_element_matrix", [])
        for element in route.get("elements", [])
        if element.get("status") == "SOURCE_SUPPORTED"
        for excerpt in element.get("source_excerpts", [])
    ]


def test_nonsexual_incapacity_does_not_create_or_auto_select_sexual_candidate():
    summary = "乙因重病全身癱軟不能抗拒，甲趁機拿走乙的錢包。"
    candidates = _candidates(summary)

    assert "sexual" not in {item["id"] for item in candidates}

    case = create_case({"summary": summary, "has_victim": True}, BANK)
    with pytest.raises(WorkflowError, match="目前摘要不足"):
        apply_action(case, "auto_prepare", {}, BANK)
    assert case["state"] == "GATE1_REVIEW"
    assert case["selected_offenses"] == []
    assert case["selected_legal_routes"] == []
    assert case["questions"] == []


def test_incapacity_sexual_positive_still_selects_reviewed_route():
    summary = "甲趁乙昏睡不能抗拒之際猥褻乙胸部。"
    sexual = _candidate(summary, "sexual")

    assert sexual["suggested_legal_route_ids"] == ["sexual_225_incapacity"]
    prepared = apply_action(
        create_case({"summary": summary, "has_victim": True}, BANK),
        "auto_prepare",
        {},
        BANK,
    )
    assert "sexual" in prepared["selected_offenses"]
    assert "sexual_225_incapacity" in {
        route["route_id"] for route in prepared["selected_legal_routes"]
    }


@pytest.mark.parametrize("force", ["推打", "推擠", "扯住"])
def test_physical_force_against_on_duty_officer_creates_obstruction_candidate(force: str):
    summary = f"甲{force}正在執勤的員警，阻止員警繼續執法。"

    obstruction = _candidate(summary, "obstruction")
    assert obstruction["suggested_legal_route_ids"] == ["obstruction_135_violence_threat"]
    prepared = apply_action(
        create_case({"summary": summary, "has_victim": True}, BANK),
        "auto_prepare",
        {},
        BANK,
    )
    assert "obstruction" in prepared["selected_offenses"]
    assert "obstruction_135_violence_threat" in {
        route["route_id"] for route in prepared["selected_legal_routes"]
    }


@pytest.mark.parametrize(
    ("summary", "offense_id", "negated_excerpt"),
    [
        ("甲從未毆打乙。另丙毆打丁，致丁頭部受傷。", "injury", "甲從未毆打乙。"),
        ("甲從未恐嚇乙。另丙揚言要殺害丁，致丁心生畏懼。", "intimidation", "甲從未恐嚇乙。"),
        (
            "甲從未脅迫乙，也沒有取得乙的財物。另丙持刀脅迫丁，致丁不能抗拒而交付現金。",
            "robbery",
            "甲從未脅迫乙，也沒有取得乙的財物。",
        ),
    ],
)
def test_negated_event_is_never_reported_as_supporting_evidence(
    summary: str, offense_id: str, negated_excerpt: str
):
    candidate = _candidate(summary, offense_id)
    excerpts = _supported_excerpts(candidate)

    assert negated_excerpt not in excerpts
    assert all("從未" not in excerpt for excerpt in excerpts)
    assert all(excerpt in summary for excerpt in excerpts)


def test_cross_event_robbery_does_not_auto_select_sexual_route():
    summary = "甲從未脅迫乙，也沒有取得乙的財物。另丙持刀脅迫丁，致丁不能抗拒而交付現金。"
    case = create_case({"summary": summary, "has_victim": True}, BANK)

    assert "sexual" not in {item["id"] for item in case["candidates"]}

    prepared = apply_action(case, "auto_prepare", {}, BANK)
    assert "sexual" not in prepared["selected_offenses"]
    assert "robbery" in prepared["selected_offenses"]
    assert "robbery_328_robbery" in {
        route["route_id"] for route in prepared["selected_legal_routes"]
    }


def test_attempted_property_threat_without_transfer_fails_closed():
    summary = "甲持刀威脅乙交出錢包，乙立即逃離，甲沒有取得任何財物。"
    case = create_case({"summary": summary, "has_victim": True}, BANK)

    with pytest.raises(WorkflowError, match="目前摘要不足"):
        apply_action(case, "auto_prepare", {}, BANK)

    assert case["state"] == "GATE1_REVIEW"
    assert case["selected_offenses"] == []
    assert case["selected_legal_routes"] == []
    assert case["questions"] == []
