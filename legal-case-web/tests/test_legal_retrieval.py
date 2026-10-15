import copy

import pytest

from app.legal_retrieval import (
    DisabledExternalAdapter,
    ExternalRetrievalNotAuthorized,
    LegalRetrievalAdapter,
    OfflineLinkageAdapter,
    RetrievalQueryError,
    build_deidentified_query,
    validate_deidentified_query,
)


def test_query_is_deidentified_by_construction():
    query = build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {
            "prior_lawful_custody": "UNKNOWN",
            "post_acquisition_conduct": "OBSERVED",
        },
    )
    assert query["contains_case_text"] is False
    assert query["privacy_status"] == "DEIDENTIFIED_BY_CONSTRUCTION"
    assert query["runtime_enabled"] is False
    assert query["legal_conclusion"] is False
    assert "刑法第320條" in query["query_text"]
    assert "刑法第335條" in query["query_text"]
    assert validate_deidentified_query(query) == []


@pytest.mark.parametrize(
    ("observations", "match"),
    [
        ({"姓名": "OBSERVED"}, "不接受任意欄位"),
        ({"possession_before_taking": "王小明住臺北市"}, "不支援的觀察狀態"),
        ({"證明單案號": "OBSERVED"}, "不接受任意欄位"),
    ],
)
def test_query_rejects_pii_and_arbitrary_case_text(observations, match):
    with pytest.raises(RetrievalQueryError, match=match):
        build_deidentified_query(["theft_320_1_movable"], observations)


@pytest.mark.parametrize(
    ("route_ids", "observations", "sentinel", "error_code"),
    [
        (
            ["PRIVATE_ROUTE_王小明"],
            {},
            "PRIVATE_ROUTE_王小明",
            "RETRIEVAL_QUERY_ROUTE_NOT_ALLOWED",
        ),
        (
            ["theft_320_1_movable"],
            {"PRIVATE_FIELD_王小明": "OBSERVED"},
            "PRIVATE_FIELD_王小明",
            "RETRIEVAL_QUERY_FACT_TARGET_NOT_ALLOWED",
        ),
        (
            ["theft_320_1_movable"],
            {"possession_before_taking": "PRIVATE_VALUE_王小明住臺北市"},
            "PRIVATE_VALUE_王小明住臺北市",
            "RETRIEVAL_QUERY_STATUS_NOT_ALLOWED",
        ),
    ],
)
def test_query_validation_errors_use_stable_codes_without_echoing_values(
    route_ids, observations, sentinel, error_code
):
    with pytest.raises(RetrievalQueryError) as exc_info:
        build_deidentified_query(route_ids, observations)
    message = str(exc_info.value)
    assert error_code in message
    assert sentinel not in message


def test_query_rejects_unknown_or_duplicate_routes():
    with pytest.raises(RetrievalQueryError, match="未核准"):
        build_deidentified_query(["fraud_339_1_general"], {})
    with pytest.raises(RetrievalQueryError, match="不得為空或重複"):
        build_deidentified_query(
            ["theft_320_1_movable", "theft_320_1_movable"], {}
        )


def test_query_tampering_is_rejected():
    query = build_deidentified_query(
        ["theft_320_1_movable"], {"possession_before_taking": "UNKNOWN"}
    )
    tampered = copy.deepcopy(query)
    tampered["query_text"] += " 王小明"
    assert validate_deidentified_query(tampered) == [
        "查詢內容與固定去識別產生器不一致"
    ]


def test_offline_adapter_implements_contract_without_network_or_conclusion():
    adapter = OfflineLinkageAdapter()
    assert isinstance(adapter, LegalRetrievalAdapter)
    query = build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )
    result = adapter.search(query)
    assert result["external_network"] is False
    assert result["legal_conclusion"] is False
    assert result["review_status"] == "HUMAN_REVIEW_REQUIRED"
    source_ids = {hit["source_id"] for hit in result["hits"]}
    assert {
        "LAW-CRIMINAL-CODE-320",
        "LAW-CRIMINAL-CODE-335",
        "JUDG-KSDM-100-JIAN-5635",
    } <= source_ids
    assert "GUIDE-PSUE-PUBLIC-DOCUMENTS" not in source_ids
    assert all(hit["legal_conclusion"] is False for hit in result["hits"])


def test_offline_adapter_rejects_tampered_query():
    query = build_deidentified_query(["theft_320_1_movable"], {})
    query["query_terms"].append("任意案情")
    with pytest.raises(RetrievalQueryError, match="固定去識別產生器不一致"):
        OfflineLinkageAdapter().search(query)


def test_external_adapter_fails_closed_before_any_network_call():
    adapter = DisabledExternalAdapter()
    assert isinstance(adapter, LegalRetrievalAdapter)
    query = build_deidentified_query(["theft_320_1_movable"], {})
    with pytest.raises(ExternalRetrievalNotAuthorized, match="Human Gate"):
        adapter.search(query)
