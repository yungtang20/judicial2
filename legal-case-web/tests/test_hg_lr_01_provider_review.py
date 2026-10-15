import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parents[1]
REVIEW_PATH = ROOT / "docs" / "evidence" / "hg_lr_01_provider_contract_review.json"
PACKET_PATH = ROOT / "docs" / "evidence" / "legal_retrieval_human_gate_packet.json"
RUNTIME_SURFACES = (
    ROOT / "app" / "server.py",
    ROOT / "app" / "workflow.py",
    ROOT / "app" / "rules.py",
    ROOT / "app" / "static" / "app.js",
)
FORBIDDEN_RUNTIME_TOKENS = (
    "hg_lr_01_provider_contract_review",
    "taiwan_law_mcp_hosted",
    "tlr_hosted",
    "judicial_jdoc_official",
    "psue_public_documents",
    "mcp_taiwan_legal_db_local",
)
EXPECTED_PROVIDERS = {
    "judicial_jdoc_official",
    "psue_public_documents",
    "taiwan_law_mcp_hosted",
    "tlr_hosted",
    "mcp_taiwan_legal_db_local",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_review_is_evidence_only_and_does_not_approve_human_gate():
    review = load_json(REVIEW_PATH)
    assert review["schema_version"] == "hg-lr-01-provider-contract-review-v1"
    assert review["decision_status"] == "PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED"
    assert review["human_gate_id"] == "HG-LR-01"
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
    assert "HG_LR_01_APPROVED" in review["claims_not_made"]
    assert "RUNTIME_CONNECTION_AUTHORIZED" in review["claims_not_made"]


def test_review_is_bound_to_the_frozen_packet_and_gate_stays_pending():
    review = load_json(REVIEW_PATH)
    packet = load_json(PACKET_PATH)
    assert review["packet_id"] == packet["packet_id"]
    assert review["packet_sha256"] == sha256(PACKET_PATH)
    approval = next(
        item for item in packet["approvals_required"] if item["id"] == "HG-LR-01"
    )
    assert approval["status"] == review["human_gate_status"] == "PENDING"
    assert packet["decision_status"] == "PENDING_HUMAN_APPROVAL"


def test_expected_providers_have_evidence_and_blocking_unknowns():
    review = load_json(REVIEW_PATH)
    providers = {item["provider_id"]: item for item in review["providers"]}
    assert set(providers) == EXPECTED_PROVIDERS
    for provider in providers.values():
        assert provider["candidate_disposition"] not in {
            "APPROVED",
            "PRODUCTION_READY",
            "RUNTIME_ENABLED",
        }
        assert provider["blocking_unknowns"]
        assert provider["evidence_urls"]
        for url in provider["evidence_urls"]:
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert parsed.netloc


def test_contract_classification_preserves_source_specific_limits():
    review = load_json(REVIEW_PATH)
    providers = {item["provider_id"]: item for item in review["providers"]}
    assert providers["judicial_jdoc_official"]["service_kind"] == "official_rest_api"
    assert (
        providers["psue_public_documents"]["response_contract_status"]
        == "NO_PUBLIC_MACHINE_API_CONTRACT_FOUND"
    )
    assert providers["taiwan_law_mcp_hosted"]["endpoint_status"] == "DOCUMENTED_PUBLIC_BETA"
    assert "allowed_citations" in providers["tlr_hosted"]["response_contract"]
    assert providers["mcp_taiwan_legal_db_local"]["endpoint"] is None


def test_review_requires_privacy_gate_and_never_claims_legal_completeness():
    review = load_json(REVIEW_PATH)
    conditions = "\n".join(review["minimum_conditions_before_approval"])
    findings = {item["label"] for item in review["review_findings"]}
    assert findings == {"FACT", "INFERENCE", "UNKNOWN"}
    assert "HG-LR-02" in conditions
    assert "HUMAN_REVIEW_REQUIRED" in conditions
    assert "LEGAL_COMPLETENESS_APPROVED" in review["claims_not_made"]


def test_review_is_not_referenced_by_runtime_surfaces():
    for path in RUNTIME_SURFACES:
        text = path.read_text(encoding="utf-8")
        assert all(token not in text for token in FORBIDDEN_RUNTIME_TOKENS)
