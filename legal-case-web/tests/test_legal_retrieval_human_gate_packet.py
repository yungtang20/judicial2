import hashlib
import json
from pathlib import Path

from app.legal_retrieval_replay import load_replay_corpus, run_replay_suite


ROOT = Path(__file__).parents[1]
PACKET_PATH = ROOT / "docs" / "evidence" / "legal_retrieval_human_gate_packet.json"
CORPUS_PATH = ROOT / "tests" / "fixtures" / "legal_retrieval_replay.json"
FORBIDDEN_RUNTIME_TOKENS = (
    "offense_linkage",
    "legal_retrieval",
    "legal_provider_fixtures",
)
EXPECTED_PACKET_KEYS = {
    "schema_version",
    "packet_id",
    "created_on",
    "decision_status",
    "scope",
    "execution_mode",
    "agent_mode",
    "boundaries",
    "frozen_files",
    "runtime_surfaces",
    "replay_evidence",
    "verification",
    "approvals_required",
    "unknowns",
    "claims_not_made",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_packet():
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def test_packet_schema_boundaries_and_all_approvals_remain_pending():
    packet = load_packet()
    assert set(packet) == EXPECTED_PACKET_KEYS
    assert packet["schema_version"] == "legal-retrieval-human-gate-packet-v1"
    assert packet["decision_status"] == "PENDING_HUMAN_APPROVAL"
    assert packet["scope"] == "OFFLINE_LEGAL_RETRIEVAL_POC_ONLY"
    assert packet["boundaries"] == {
        "runtime_enabled": False,
        "external_network_enabled": False,
        "gate2_connected": False,
        "default_cache_path": None,
        "contains_case_data": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    assert len(packet["approvals_required"]) == 5
    assert all(item["status"] == "PENDING" for item in packet["approvals_required"])
    assert packet["unknowns"]
    assert "LEGAL_CORRECTNESS_APPROVED" in packet["claims_not_made"]


def test_all_frozen_file_hashes_match_current_checkout():
    packet = load_packet()
    expected_paths = {
        "app/offense_linkage.py",
        "data/offense_linkage_poc.json",
        "app/legal_retrieval.py",
        "app/legal_retrieval_cache.py",
        "app/legal_provider_fixtures.py",
        "app/legal_retrieval_reconciliation.py",
        "app/legal_retrieval_sync.py",
        "app/legal_retrieval_batch.py",
        "app/legal_retrieval_replay.py",
        "tests/fixtures/legal_retrieval_replay.json",
        "app/legal_provider_tlr_pack.py",
        "app/provider_endpoint_policy.py",
        "deploy/providers/taiwan_law_mcp.json",
    }
    assert {item["path"] for item in packet["frozen_files"]} == expected_paths
    for item in packet["frozen_files"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]


def test_runtime_surfaces_are_hash_stable_and_unreachable():
    packet = load_packet()
    for surface in packet["runtime_surfaces"]:
        path = ROOT / surface["path"]
        assert sha256(path) == surface["sha256"]
        text = path.read_text(encoding="utf-8")
        references = sum(text.count(token) for token in FORBIDDEN_RUNTIME_TOKENS)
        assert references == surface["expected_references"] == 0


def test_replay_evidence_matches_frozen_packet(tmp_path):
    packet = load_packet()
    corpus = load_replay_corpus(CORPUS_PATH)
    report = run_replay_suite(corpus, tmp_path / "replay")
    evidence = packet["replay_evidence"]
    assert evidence["corpus_file_sha256"] == sha256(CORPUS_PATH)
    assert evidence["corpus_canonical_sha256"] == report["corpus_sha256"]
    assert evidence["suite_evidence_sha256"] == report["suite_evidence_sha256"]
    assert evidence["scenario_count"] == report["scenario_count"] == 4
    assert evidence["passed_count"] == report["passed_count"] == 4
    assert evidence["failed_count"] == report["failed_count"] == 0


def test_packet_does_not_claim_runtime_or_legal_approval():
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    packet = load_packet()
    assert '"decision_status": "APPROVED"' not in packet_text
    assert packet["boundaries"]["legal_conclusion"] is False
    assert packet["boundaries"]["review_status"] == "HUMAN_REVIEW_REQUIRED"
    assert all(item["status"] != "APPROVED" for item in packet["approvals_required"])


def test_packet_records_current_bounded_verification_without_approving_gate():
    packet = load_packet()
    verification = {item["id"]: item for item in packet["verification"]}
    assert set(verification) == {"V01", "V02", "V03", "V04", "V05"}
    assert all(item["status"] == "PASS" for item in verification.values())
    assert verification["V01"]["passed"] == 563
    assert verification["V04"]["passed"] == 29
    assert packet["decision_status"] == "PENDING_HUMAN_APPROVAL"
