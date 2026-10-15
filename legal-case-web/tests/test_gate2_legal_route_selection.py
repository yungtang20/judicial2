from __future__ import annotations

from copy import deepcopy

import pytest

from app.workflow import WorkflowError, apply_action, create_case, public_case
from tests.helpers import BANK, intake


THEFT_ROUTE = "theft_320_1_movable"
EMBEZZLEMENT_ROUTE = "embezzlement_335_general"


def gate2_case(summary: str = "有人未經同意拿走店內物品。") -> dict:
    case = create_case(intake(summary=summary), BANK)
    return apply_action(case, "approve_gate1", {"confirmed": True}, BANK)


def select(case: dict, offenses: list[str], routes: list[str]) -> dict:
    return apply_action(case, "set_offenses", {
        "offense_ids": offenses,
        "legal_route_ids": routes,
        "route_review_confirmed": True,
        "role": "victim",
    }, BANK)


def test_set_offenses_atomically_saves_separate_route_snapshot():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    assert case["selected_offenses"] == ["theft"]
    assert case["route_selection_status"] == "SELECTED"
    assert case["legal_route_review"]["crosswalk_version"] == BANK["legal_route_crosswalk_version"]
    assert case["selected_legal_routes"] == [{
        "route_id": THEFT_ROUTE,
        "parent_offense_id": "theft",
        "route_kind": "offense",
        "name": "竊取他人動產",
        "crosswalk_version": BANK["legal_route_crosswalk_version"],
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }]
    for question in case["questions"]:
        assert question["meta"]["route_context_ids"] == [THEFT_ROUTE]
    coverage = case["question_coverage_by_route"]["routes"][THEFT_ROUTE]
    assert coverage["pack_scope"] == "EXACT_CHILD_PACK"
    assert coverage["materialization_status"] == "COMPLETE"
    assert coverage["coverage_claim"] == "BOUNDED_TO_APPROVED_WORK_ITEM"
    assert coverage["human_review_required"] is True
    assert coverage["legal_conclusion"] is False


def test_route_review_must_be_explicit_but_optional_policy_allows_none():
    case = gate2_case()
    with pytest.raises(WorkflowError, match="法律路由"):
        apply_action(case, "set_offenses", {
            "offense_ids": ["theft"], "legal_route_ids": [], "role": "victim",
        }, BANK)
    reviewed = select(case, ["theft"], [])
    assert reviewed["selected_legal_routes"] == []
    assert reviewed["route_selection_status"] == "REVIEWED_NONE_SELECTED"


@pytest.mark.parametrize("route_id", ["unknown_route", "theft_322_deleted", EMBEZZLEMENT_ROUTE])
def test_unknown_or_cross_parent_route_is_rejected_atomically(route_id):
    case = gate2_case()
    before = deepcopy(case)
    with pytest.raises(WorkflowError, match="路由"):
        select(case, ["theft"], [route_id])
    assert case == before


def test_duplicate_route_is_rejected_atomically():
    case = gate2_case()
    before = deepcopy(case)
    with pytest.raises(WorkflowError, match="重複"):
        select(case, ["theft"], [THEFT_ROUTE, THEFT_ROUTE])
    assert case == before


def test_selection_policy_controls_required_and_not_applicable_routes():
    required_bank = deepcopy(BANK)
    next(item for item in required_bank["offenses"] if item["id"] == "theft")["selection_policy"] = "REQUIRED"
    case = gate2_case()
    with pytest.raises(WorkflowError, match="必須選擇"):
        apply_action(case, "set_offenses", {
            "offense_ids": ["theft"], "legal_route_ids": [],
            "route_review_confirmed": True, "role": "victim",
        }, required_bank)

    not_applicable_bank = deepcopy(BANK)
    next(item for item in not_applicable_bank["offenses"] if item["id"] == "theft")["selection_policy"] = "NOT_APPLICABLE"
    with pytest.raises(WorkflowError, match="不適用"):
        apply_action(gate2_case(), "set_offenses", {
            "offense_ids": ["theft"], "legal_route_ids": [THEFT_ROUTE],
            "route_review_confirmed": True, "role": "victim",
        }, not_applicable_bank)


def test_multiple_offenses_keep_parent_route_relationships():
    case = select(
        gate2_case(),
        ["theft", "embezzlement"],
        [THEFT_ROUTE, EMBEZZLEMENT_ROUTE],
    )
    assert {
        (item["parent_offense_id"], item["route_id"])
        for item in case["selected_legal_routes"]
    } == {("theft", THEFT_ROUTE), ("embezzlement", EMBEZZLEMENT_ROUTE)}
    coverage = case["question_coverage_by_route"]["routes"]
    assert coverage[THEFT_ROUTE]["coverage_claim"] == "BOUNDED_TO_APPROVED_WORK_ITEM"
    assert coverage[EMBEZZLEMENT_ROUTE]["pack_scope"] == "LEGACY_PARENT_PACK"
    assert coverage[EMBEZZLEMENT_ROUTE]["coverage_claim"] == "NONE"


def test_answer_codes_are_validated_against_frozen_question_snapshot():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    question = next(
        item for item in case["questions"]
        if item.get("meta", {}).get("question_concept_id") == "THF3201MOV-C02"
    )
    with pytest.raises(WorkflowError, match="題目快照"):
        apply_action(case, "save_answers", {
            "answers": {question["id"]: "具體陳述"},
            "answer_codes": {question["id"]: "YES"},
        }, BANK)

    question["meta"]["answer_map"] = {"LEGACY_CODE": "LEGACY_CODE", "UNKNOWN": "UNKNOWN"}
    updated = apply_action(case, "save_answers", {
        "answers": {question["id"]: "既有案件的受控代碼"},
        "answer_codes": {question["id"]: "LEGACY_CODE"},
    }, BANK)
    saved = next(item for item in updated["questions"] if item["id"] == question["id"])
    assert saved["answer_code"] == "LEGACY_CODE"


def test_exact_enum_answer_updates_only_child_route_observation():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    question = next(
        item for item in case["questions"]
        if item.get("meta", {}).get("question_concept_id") == "THF3201MOV-C02"
    )
    updated = apply_action(case, "save_answers", {
        "answers": {question["id"]: "物品原由店員保管。"},
        "answer_codes": {question["id"]: "OTHER_PERSON_CONTROL"},
    }, BANK)
    overlay = updated["route_fact_overlay"][THEFT_ROUTE]["possession_before_taking"]
    assert overlay["status"] == "KNOWN"
    assert overlay["value"] == "OTHER_PERSON_CONTROL"
    assert updated["selected_legal_route_states"][THEFT_ROUTE]["state"] == "NEED_REVIEW"
    assert updated["selected_legal_route_states"][THEFT_ROUTE]["legal_conclusion"] is False


def test_question_materialization_failure_is_atomic(monkeypatch):
    case = gate2_case()
    before = deepcopy(case)

    def fail_build(*args, **kwargs):
        raise RuntimeError("materialization failed")

    monkeypatch.setattr("app.workflow.build_questions", fail_build)
    with pytest.raises(RuntimeError, match="materialization failed"):
        select(case, ["theft"], [THEFT_ROUTE])
    assert case == before


def test_route_change_invalidates_existing_answers():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    first_id = case["questions"][0]["id"]
    case = apply_action(case, "save_answers", {"answers": {first_id: "既有回答"}}, BANK)
    assert any(item.get("answer") == "既有回答" for item in case["questions"])

    changed = select(case, ["theft"], ["theft_320_2_real_estate"])
    assert all(not item.get("answer") for item in changed["questions"])
    assert changed["question_coverage_by_route"]["route_context_ids"] == ["theft_320_2_real_estate"]
    assert changed["question_coverage_by_route"]["routes"]["theft_320_2_real_estate"]["coverage_claim"] == "NONE"
    assert changed["route_fact_observations"] == {"theft_320_2_real_estate": {}}
    assert THEFT_ROUTE not in changed["selected_legal_route_states"]


def test_gate2_approval_rechecks_route_contract_and_snapshots_interview():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    answers = {question["id"]: "UNKNOWN" for question in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    stale = deepcopy(case)
    stale["legal_route_review"]["crosswalk_version"] = "stale-version"
    with pytest.raises(WorkflowError, match="版本"):
        apply_action(stale, "approve_gate2", {"confirmed": True}, BANK)

    approved = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    interview = approved["interviews"]["victim:default"]
    assert interview["selected_legal_routes"][0]["route_id"] == THEFT_ROUTE
    assert interview["route_selection_status"] == "SELECTED"
    assert interview["question_coverage_by_route"]["routes"][THEFT_ROUTE]["coverage_claim"] == "BOUNDED_TO_APPROVED_WORK_ITEM"
    assert interview["selected_legal_route_states"][THEFT_ROUTE]["legal_conclusion"] is False

def test_gate1_change_invalidates_route_selection():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    updated = apply_action(case, "update_gate1", {"gate1": {"events": ["修正後事件。"]}}, BANK)
    assert updated["selected_legal_routes"] == []
    assert updated["route_selection_status"] == "PENDING"
    assert updated["legal_route_review"] is None


def test_legacy_case_is_readable_but_cannot_approve_without_route_review():
    case = select(gate2_case(), ["theft"], [THEFT_ROUTE])
    answers = {question["id"]: "UNKNOWN" for question in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    case.pop("selected_legal_routes")
    case.pop("legal_route_review")
    case.pop("route_selection_status")
    assert public_case(case)["route_selection_status"] == "LEGACY_MISSING"
    with pytest.raises(WorkflowError, match="法律路由"):
        apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
