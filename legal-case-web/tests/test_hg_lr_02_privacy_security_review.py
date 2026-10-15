import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.legal_retrieval import (
    OfflineLinkageAdapter,
    RetrievalQueryError,
    build_deidentified_query,
)
from app.legal_retrieval_cache import (
    RetrievalMetadataCache,
    normalize_adapter_response,
)


ROOT = Path(__file__).parents[1]
REVIEW_PATH = ROOT / "docs" / "evidence" / "hg_lr_02_privacy_security_review.json"
PACKET_PATH = ROOT / "docs" / "evidence" / "legal_retrieval_human_gate_packet.json"
PROVIDER_REVIEW_PATH = ROOT / "docs" / "evidence" / "hg_lr_01_provider_contract_review.json"
RUNTIME_SURFACES = (
    ROOT / "app" / "server.py",
    ROOT / "app" / "workflow.py",
    ROOT / "app" / "rules.py",
    ROOT / "app" / "static" / "app.js",
)
FORBIDDEN_RUNTIME_TOKENS = (
    "hg_lr_02_privacy_security_review",
    "HG-LR-02-REVIEW",
    "P01_PUBLIC_DOCKET_IDENTIFIER_PERSISTED",
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_query():
    return build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )


def finding_ids(review):
    return {item["finding_id"] for item in review["blocking_findings"]}


def remediated_finding_ids(review):
    return {item["finding_id"] for item in review["remediated_findings"]}


def test_review_requires_changes_and_does_not_approve_privacy_gate():
    review = load_json(REVIEW_PATH)
    assert review["schema_version"] == "hg-lr-02-privacy-security-review-v1"
    assert review["decision_status"] == "CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING"
    assert review["human_gate_id"] == "HG-LR-02"
    assert review["human_gate_status"] == "PENDING"
    assert review["scope"] == {
        "evidence_only": True,
        "live_provider_calls_performed": False,
        "credentials_used": False,
        "case_data_sent": False,
        "runtime_enabled": False,
        "gate2_connected": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    assert "HG_LR_02_APPROVED" in review["claims_not_made"]
    assert "ANONYMOUS_DATA" in review["claims_not_made"]


def test_review_is_bound_to_prior_evidence_and_all_human_gates_stay_pending():
    review = load_json(REVIEW_PATH)
    packet = load_json(PACKET_PATH)
    provider_review = load_json(PROVIDER_REVIEW_PATH)
    assert review["packet_id"] == packet["packet_id"]
    assert review["packet_sha256"] == sha256(PACKET_PATH)
    assert review["provider_review_id"] == provider_review["review_id"]
    assert review["provider_review_sha256"] == sha256(PROVIDER_REVIEW_PATH)
    assert all(item["status"] == "PENDING" for item in packet["approvals_required"])
    assert packet["decision_status"] == "PENDING_HUMAN_APPROVAL"


def test_legal_sources_are_traceable_but_legal_applicability_is_not_claimed():
    review = load_json(REVIEW_PATH)
    context = review["legal_source_context"]
    assert context["applicability_status"] == (
        "REQUIRES_ROLE_PURPOSE_AND_EFFECTIVE_VERSION_REVIEW"
    )
    assert context["evidence_urls"]
    for url in context["evidence_urls"]:
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "law.moj.gov.tw"
    assert "LEGAL_COMPLIANCE_CONFIRMED" in review["claims_not_made"]


def test_query_is_minimized_but_review_does_not_mislabel_it_anonymous():
    review = load_json(REVIEW_PATH)
    query = sample_query()
    stage = next(
        item for item in review["data_flow"] if item["stage"] == "DEIDENTIFIED_QUERY_BUILD"
    )
    assert query["contains_case_text"] is False
    assert query["privacy_status"] == "DEIDENTIFIED_BY_CONSTRUCTION"
    assert stage["classification"] == (
        "DATA_MINIMIZED_LEGAL_CASE_METADATA_NOT_PROVEN_ANONYMOUS"
    )
    assert "ANONYMOUS_DATA" in review["claims_not_made"]


def test_review_records_current_public_docket_identifier_persistence(tmp_path):
    review = load_json(REVIEW_PATH)
    query = sample_query()
    normalized = normalize_adapter_response(query, OfflineLinkageAdapter().search(query))
    cache_path = tmp_path / "retrieval-metadata.json"
    RetrievalMetadataCache(cache_path).store(normalized)
    saved = cache_path.read_text(encoding="utf-8")
    assert query["query_text"] not in saved
    assert "KSDM,100,簡,5635,20111130,1" not in saved
    assert "100年度簡字第5635號" in saved
    assert "KSDM%2c100" in saved
    assert "P01_PUBLIC_DOCKET_IDENTIFIER_PERSISTED" in finding_ids(review)


def test_review_records_caller_controlled_invalid_value_echo_as_remediated():
    review = load_json(REVIEW_PATH)
    sensitive_value = "王小明住臺北市"
    with pytest.raises(RetrievalQueryError) as exc_info:
        build_deidentified_query(
            ["theft_320_1_movable"],
            {"possession_before_taking": sensitive_value},
        )
    assert "RETRIEVAL_QUERY_STATUS_NOT_ALLOWED" in str(exc_info.value)
    assert sensitive_value not in str(exc_info.value)
    assert "P02_INVALID_INPUT_ECHO_IN_EXCEPTION" not in finding_ids(review)
    assert "P02_INVALID_INPUT_ECHO_IN_EXCEPTION" in remediated_finding_ids(review)


def test_review_tracks_plaintext_logging_hash_and_ownership_blockers():
    review = load_json(REVIEW_PATH)
    assert {
        "P03_PLAINTEXT_CACHE_WITHOUT_ACCESS_CONTROL_CONTRACT",
        "P04_HOSTED_QUERY_LOGGING",
        "P05_HASH_LINKABILITY_AND_UNKEYED_INTEGRITY",
        "P06_PURPOSE_RETENTION_AND_INCIDENT_OWNERSHIP_UNDEFINED",
    } <= finding_ids(review)
    assert {item["label"] for item in review["blocking_findings"]} == {
        "FACT",
        "INFERENCE",
        "UNKNOWN",
    }
    assert all(item["required_decision"] for item in review["blocking_findings"])


def test_privacy_review_is_not_referenced_by_runtime_surfaces():
    for path in RUNTIME_SURFACES:
        text = path.read_text(encoding="utf-8")
        assert all(token not in text for token in FORBIDDEN_RUNTIME_TOKENS)
