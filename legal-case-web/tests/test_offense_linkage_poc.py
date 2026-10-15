import json
from pathlib import Path

import pytest

from app.offense_linkage import build_review_matrix, load_pack, validate_pack


ROOT = Path(__file__).resolve().parents[1]


def test_poc_pack_schema_and_provenance_are_valid():
    pack = load_pack()
    assert validate_pack(pack) == []


def test_poc_is_not_connected_to_runtime_or_prosecution_documents():
    pack = load_pack()
    assert pack["runtime_enabled"] is False
    assert pack["legal_conclusion"] is False
    assert pack["ingestion_status"]["prosecution_documents"] == "NOT_INGESTED"
    assert "prosecution_document" not in {
        source["source_type"] for source in pack["sources"]
    }


def test_poc_routes_exist_in_current_crosswalk():
    crosswalk = json.loads(
        (ROOT / "data" / "legal_route_crosswalk.json").read_text(encoding="utf-8")
    )
    route_ids = {
        child["id"]
        for parent in crosswalk["routes"]
        for child in parent.get("child_routes", [])
    }
    assert {profile["route_id"] for profile in load_pack()["route_profiles"]} <= route_ids


def test_poc_reuses_current_theft_work_item_axis_instead_of_replacing_it():
    work_item = (ROOT / "docs" / "QUESTION_WORK_ITEM.md").read_text(encoding="utf-8")
    axis = next(
        item for item in load_pack()["question_axes"]
        if item["axis_id"] == "AXIS-PRIOR-POSSESSION"
    )
    assert axis["existing_question_concept_refs"] == ["THF3201MOV-C02"]
    assert "THF3201MOV-C02" in work_item
    assert "prior_lawful_custody" in work_item


def test_review_matrix_preserves_unknown_and_never_returns_legal_conclusion():
    matrix = build_review_matrix(
        load_pack(),
        {
            "object_status": "OBSERVED",
            "prior_lawful_custody": "CONFLICT",
        },
    )
    assert matrix["legal_conclusion"] is False
    assert matrix["review_status"] == "HUMAN_REVIEW_REQUIRED"
    for route in matrix["routes"]:
        assert route["legal_conclusion"] is False
        assert route["review_status"] == "HUMAN_REVIEW_REQUIRED"
    embezzlement = next(
        route for route in matrix["routes"]
        if route["route_id"] == "embezzlement_335_general"
    )
    assert "prior_lawful_custody" in embezzlement["missing_fact_targets"]
    theft = next(
        route for route in matrix["routes"]
        if route["route_id"] == "theft_320_1_movable"
    )
    statuses = {item["fact_target"]: item["status"] for item in theft["elements"]}
    assert statuses["object_status"] == "OBSERVED"
    assert statuses["possession_before_taking"] == "UNKNOWN"


def test_review_matrix_rejects_invented_fact_status():
    with pytest.raises(ValueError, match="不支援的觀察狀態"):
        build_review_matrix(load_pack(), {"prior_lawful_custody": "PROVEN_GUILTY"})
