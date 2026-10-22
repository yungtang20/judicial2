"""TLR ``pack`` 契約層的鎖定測試（2026-10-22 新增）。

驗證四件事：
1. bundle 契約（schema、allowed_citations、JID／日期一致性、驗證指示）。
2. bundle 必須綁定本次去識別查詢，否則拒絕。
3. 只有「已登錄 JID ＋ 未截斷 ＋ 有 relation 覆蓋」的判決能成為 hit，
   且判決文字不得離開模組。
4. live 呼叫受 Human Gate 封包約束；目前封包為 PENDING，建構即失敗。
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app import legal_provider_tlr_pack as tlr
from app.legal_retrieval import build_deidentified_query
from app.offense_linkage import load_pack

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tlr_pack_bundle_v1.json"
QUERY = build_deidentified_query(["theft_320_1_movable"], {})


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_satisfies_the_frozen_pack_contract() -> None:
    assert tlr.validate_pack_bundle(_fixture(), query=QUERY) == []


def test_bundle_must_bind_to_the_deidentified_query() -> None:
    bundle = _fixture()
    bundle["query"] = "完全不同的查詢字串"
    with pytest.raises(tlr.TlrBundleQueryMismatch):
        tlr.validate_pack_bundle(bundle, query=QUERY)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda b: b.update(retrieval_only=False), "retrieval_only"),
        (lambda b: b["verification_instructions"].update(required=False), "required"),
        (lambda b: b["verification_instructions"].update(rules=[]), "rules"),
        (lambda b: b["judgments"][0].update(citation_id="J9"), "allowed_citations"),
        (lambda b: b["judgments"][0].update(jdate="2011-12-01"), "jdate"),
        (lambda b: b["judgments"][0].update(case_category="民事"), "case_category"),
        (lambda b: b["allowed_citations"].append("J1"), "重複"),
        (lambda b: b.update(schema="twlegalrag.bundle/v0"), "schema"),
    ],
)
def test_contract_rejects_inconsistent_bundles(mutate, expected: str) -> None:
    bundle = _fixture()
    mutate(bundle)
    errors = tlr.validate_pack_bundle(bundle, query=QUERY)
    assert any(expected in error for error in errors), errors


def test_summary_contains_no_excerpt_text() -> None:
    summary = tlr.summarize_pack_bundle(_fixture(), query=QUERY)
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "SYNTHETIC-FIXTURE" not in serialized
    assert summary["contains_excerpt_text"] is False
    assert summary["bundle_sha256"]
    assert summary["judgment_count"] == 3


def test_adapter_maps_only_registered_untruncated_judgments() -> None:
    adapter = tlr.build_fixture_adapter(FIXTURE_PATH)
    result = adapter.search(QUERY)
    assert [hit["source_id"] for hit in result["hits"]] == ["JUDG-KSDM-100-JIAN-5635"]
    hit = result["hits"][0]
    assert hit["citation_id"] == "J1"
    assert hit["judicial_jid"] == "KSDM,100,簡,5635,20111130,1"
    assert hit["hash_scope"] == "RETRIEVED_EXCERPT_SHA256_NOT_FULL_DOCUMENT"
    assert hit["legal_conclusion"] is False
    assert hit["review_status"] == "HUMAN_REVIEW_REQUIRED"
    assert result["skipped"] == [
        {"citation_id": "J2", "reason": "UNREGISTERED_JID"},
        {"citation_id": "J3", "reason": "TRUNCATED_FULLTEXT"},
    ]


def test_adapter_never_emits_judgment_text() -> None:
    result = tlr.build_fixture_adapter(FIXTURE_PATH).search(QUERY)
    serialized = json.dumps(result, ensure_ascii=False)
    for marker in ("SYNTHETIC-FIXTURE-FULLTEXT", "SYNTHETIC-FIXTURE-HIT", "SYNTHETIC-FIXTURE-LISTING"):
        assert marker not in serialized
    for field in tlr.PACK_TEXT_FIELDS:
        assert field not in result["hits"][0]
    expected = hashlib.sha256(
        _fixture()["judgments"][0]["fulltext_excerpt"].encode("utf-8")
    ).hexdigest()
    assert result["hits"][0]["content_sha256"] == expected


def test_adapter_query_tampering_is_rejected() -> None:
    tampered = deepcopy(QUERY)
    tampered["query_text"] = tampered["query_text"] + " 甲在夜間侵入住宅"
    with pytest.raises(Exception):
        tlr.build_fixture_adapter(FIXTURE_PATH).search(tampered)


def test_live_call_is_blocked_while_human_gate_pending() -> None:
    authorized, reason = tlr.live_call_authorization()
    assert authorized is False
    assert "HG-LR-01" in reason and "HG-LR-02" in reason
    with pytest.raises(tlr.TlrPackNotAuthorized):
        tlr.TlrPackCliClient()
    with pytest.raises(tlr.TlrPackNotAuthorized):
        tlr.TlrPackCliClient(packet={"decision_status": "PENDING_HUMAN_APPROVAL"})


def test_approved_packet_only_enables_argv_dry_run() -> None:
    """以合成的核准封包證明 live 路徑的送出名稱受限，且不執行外部程式。"""

    client = tlr.TlrPackCliClient(packet={"decision_status": "APPROVED"})
    argv = client.dry_run(QUERY, limit=3)
    assert argv[:2] == ["twlegalrag", "pack"]
    assert argv[2] == QUERY["query_text"]
    assert argv[3:] == ["--n", "3"]
    # 送出的字串只能是固定詞彙：不得含案情代稱或自由文字。
    for forbidden in ("甲", "乙", "被害人", "被告"):
        assert forbidden not in argv[2]


def test_dry_run_rejects_free_text_query() -> None:
    client = tlr.TlrPackCliClient(packet={"decision_status": "APPROVED"})
    tampered = deepcopy(QUERY)
    tampered["query_text"] = "甲於夜間侵入乙住宅"
    with pytest.raises(Exception):
        client.dry_run(tampered)


def test_registry_pack_is_valid_for_the_adapter() -> None:
    assert load_pack()["runtime_enabled"] is False
