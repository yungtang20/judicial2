from __future__ import annotations

from copy import deepcopy

import pytest

from app.v3_contracts import (
    ContractContext,
    ContractValidationError,
    MAX_STAGE_ATTEMPTS,
    SCHEMA_VERSION,
    STAGE_CANDIDATE_ANALYSIS,
    STAGE_ROUTE_ELEMENT_ANALYSIS,
    STAGE_STATEMENT_ASSEMBLY,
    build_request_envelope,
    canonical_sha256,
    validate_candidate_analysis_response,
    validate_route_element_analysis_response,
    validate_statement_assembly,
)


CASE_TEXT = "甲趁乙不在場，將乙停放的機車騎走，機車目前尚未尋獲。"
QUOTE = "將乙停放的機車騎走"
QUOTE_START = CASE_TEXT.index(QUOTE)
SOURCE_HASHES = {
    "question_bank": canonical_sha256({"version": "test"}),
    "law:criminal-code-320": canonical_sha256({"article": "320"}),
}
INPUT_HASH = canonical_sha256({"case_text": CASE_TEXT})


def context() -> ContractContext:
    return ContractContext(
        request_id="req-test-001",
        case_revision=7,
        input_hash=INPUT_HASH,
        source_snapshot_hashes=SOURCE_HASHES,
        case_text=CASE_TEXT,
        allowed_offense_ids=frozenset({"theft", "robbery"}),
        route_parent_by_id={"theft_320_1_movable": "theft"},
        element_ids_by_route={
            "theft_320_1_movable": frozenset({"taking", "intent"})
        },
        prosecution_by_route={"theft_320_1_movable": "待確認"},
        allowed_template_fields={
            "suspect_with_victim": frozenset({"case_reason", "case_summary"})
        },
    )


def envelope(stage: str, payload: dict, *, attempt: int = 1) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "request_id": "req-test-001",
        "case_revision": 7,
        "attempt": attempt,
        "input_hash": INPUT_HASH,
        "source_snapshot_hashes": SOURCE_HASHES,
        "response_payload": payload,
    }


def candidate_response() -> dict:
    return envelope(
        STAGE_CANDIDATE_ANALYSIS,
        {
            "candidates": [
                {
                    "offense_id": "theft",
                    "reason": "案情記載行為人將乙的機車騎走，可能涉及本候選方向。",
                    "basis_quote": QUOTE,
                    "basis_start": QUOTE_START,
                    "basis_end": QUOTE_START + len(QUOTE),
                    "missing": ["不法所有意圖待確認", "贓物流向待查"],
                }
            ],
            "status": {
                "subject_identified": "true",
                "has_victim": "true",
                "is_solved": "true",
            },
        },
    )


def element_response() -> dict:
    return envelope(
        STAGE_ROUTE_ELEMENT_ANALYSIS,
        {
            "summary": "案情記載甲將乙停放的機車騎走，其他主觀事實仍待確認。",
            "per_offence": [
                {
                    "offense_id": "theft",
                    "route_id": "theft_320_1_movable",
                    "elements": [
                        {
                            "element_id": "taking",
                            "status": "EVIDENCED",
                            "basis_quote": QUOTE,
                            "basis_start": QUOTE_START,
                            "basis_end": QUOTE_START + len(QUOTE),
                        },
                        {
                            "element_id": "intent",
                            "status": "NEEDS_CONFIRMATION",
                            "basis_quote": "案情未述",
                            "basis_start": None,
                            "basis_end": None,
                        },
                    ],
                    "prosecution": "待確認",
                    "evidence_hints": ["確認機車後續流向及使用情形"],
                }
            ],
            "conclusion": "目前資料僅供候選方向與補證規劃。僅供參考，須人工審核。",
        },
    )


def assert_code(exc: pytest.ExceptionInfo[ContractValidationError], code: str) -> None:
    assert exc.value.code == code
    assert exc.value.as_error()["error"]["code"] == code


def test_build_request_envelope_is_versioned_and_hashes_input():
    request = build_request_envelope(
        stage=STAGE_CANDIDATE_ANALYSIS,
        request_id="req-1",
        case_revision=0,
        attempt=1,
        input_payload={"case_text": CASE_TEXT},
        source_snapshot_hashes=SOURCE_HASHES,
    )
    assert request["schema_version"] == SCHEMA_VERSION
    assert request["input_hash"] == canonical_sha256({"case_text": CASE_TEXT})
    assert request["source_snapshot_hashes"] == SOURCE_HASHES


def test_candidate_contract_accepts_zero_to_three_allowlisted_candidates():
    validated = validate_candidate_analysis_response(candidate_response(), context())
    assert validated["response_payload"]["candidates"][0]["offense_id"] == "theft"
    empty = candidate_response()
    empty["response_payload"]["candidates"] = []
    assert validate_candidate_analysis_response(empty, context())["response_payload"]["candidates"] == []


def test_candidate_contract_can_bind_response_to_current_attempt():
    value = candidate_response()
    value["attempt"] = 2
    bound_context = ContractContext(
        **{**context().__dict__, "expected_attempt": 1}
    )
    with pytest.raises(ContractValidationError) as exc:
        validate_candidate_analysis_response(value, bound_context)
    assert_code(exc, "ATTEMPT_MISMATCH")


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.update({"unexpected": True}), "UNKNOWN_FIELD"),
        (
            lambda value: value["response_payload"]["candidates"][0].update(
                {"offense_id": "unknown"}
            ),
            "UNKNOWN_OFFENSE_ID",
        ),
        (
                lambda value: value["response_payload"]["candidates"].extend(
                    [deepcopy(value["response_payload"]["candidates"][0]) for _ in range(4)]
                ),
            "TOO_MANY_CANDIDATES",
        ),
        (
            lambda value: value["response_payload"]["candidates"][0].update(
                {"basis_start": 0}
            ),
            "BASIS_QUOTE_MISMATCH",
        ),
        (
            lambda value: value["response_payload"]["candidates"][0].update(
                {"reason": "本案已構成竊盜"}
            ),
            "FORBIDDEN_CONCLUSION",
        ),
        (lambda value: value.update({"attempt": MAX_STAGE_ATTEMPTS + 1}), "ATTEMPT_LIMIT_EXCEEDED"),
        (lambda value: value.update({"case_revision": 6}), "STALE_CASE_REVISION"),
        (lambda value: value.update({"input_hash": "0" * 64}), "INPUT_HASH_MISMATCH"),
    ],
)
def test_candidate_contract_rejects_invalid_outputs(mutate, code):
    value = candidate_response()
    mutate(value)
    with pytest.raises(ContractValidationError) as exc:
        validate_candidate_analysis_response(value, context())
    assert_code(exc, code)


def test_element_contract_accepts_exact_case_quote_and_pending_marker():
    validated = validate_route_element_analysis_response(element_response(), context())
    elements = validated["response_payload"]["per_offence"][0]["elements"]
    assert elements[0]["basis_quote"] == QUOTE
    assert elements[1]["basis_quote"] == "案情未述"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda value: value["response_payload"]["per_offence"][0].update(
                {"route_id": "robbery_328"}
            ),
            "ROUTE_PARENT_MISMATCH",
        ),
        (
            lambda value: value["response_payload"]["per_offence"][0]["elements"][0].update(
                {"element_id": "unknown"}
            ),
            "UNKNOWN_ELEMENT_ID",
        ),
        (
            lambda value: value["response_payload"]["per_offence"][0]["elements"][0].update(
                {"status": "已具備"}
            ),
            "INVALID_ELEMENT_STATUS",
        ),
        (
            lambda value: value["response_payload"].update(
                {"conclusion": "目前僅供候選方向。"}
            ),
            "MISSING_REVIEW_NOTICE",
        ),
        (
            lambda value: value["response_payload"]["per_offence"][0].update(
                {"prosecution": "告訴乃論"}
            ),
            "PROSECUTION_SOURCE_MISMATCH",
        ),
        (
            lambda value: value["response_payload"].update(
                {"summary": "第一句。第二句。第三句。"}
            ),
            "TOO_MANY_SENTENCES",
        ),
        (
            lambda value: value["response_payload"]["per_offence"][0]["elements"][1].update(
                {"basis_quote": "可能沒有意圖"}
            ),
            "UNSUPPORTED_BASIS_FOR_PENDING",
        ),
    ],
)
def test_element_contract_rejects_untraceable_or_unapproved_analysis(mutate, code):
    value = element_response()
    mutate(value)
    with pytest.raises(ContractValidationError) as exc:
        validate_route_element_analysis_response(value, context())
    assert_code(exc, code)


def test_statement_assembly_is_code_owned_and_normalizes_empty_fields():
    value = envelope(
        STAGE_STATEMENT_ASSEMBLY,
        {
            "template_id": "suspect_with_victim",
            "fields": {"case_reason": "持有他人機車（候選）", "case_summary": ""},
            "notice": "本條陳為模擬填充，未敘明欄位均待補，不構成正式文書。",
        },
    )
    validated = validate_statement_assembly(value, context())
    assert validated["response_payload"]["fields"]["case_summary"] == "（待補）"


def test_statement_assembly_rejects_unknown_template_or_field():
    value = envelope(
        STAGE_STATEMENT_ASSEMBLY,
        {
            "template_id": "unknown",
            "fields": {"case_reason": "候選"},
            "notice": "不構成正式文書。",
        },
    )
    with pytest.raises(ContractValidationError) as exc:
        validate_statement_assembly(value, context())
    assert_code(exc, "UNKNOWN_TEMPLATE_ID")

    value["response_payload"]["template_id"] = "suspect_with_victim"
    value["response_payload"]["fields"] = {
        "case_reason": "持有他人機車（候選）",
        "case_summary": "案情摘要",
        "extra": "不得存在",
    }
    with pytest.raises(ContractValidationError) as exc:
        validate_statement_assembly(value, context())
    assert_code(exc, "UNKNOWN_FIELD")
