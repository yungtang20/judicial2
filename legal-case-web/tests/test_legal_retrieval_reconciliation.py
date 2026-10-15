import hashlib
import json

import pytest

from app.legal_provider_fixtures import (
    JudicialOpenDataFixtureAdapter,
    SourceRemovalRequired,
    TaiwanLegalDbFixtureAdapter,
)
from app.legal_retrieval import OfflineLinkageAdapter, build_deidentified_query
from app.legal_retrieval_cache import (
    RetrievalCacheIntegrityError,
    RetrievalMetadataCache,
    normalize_adapter_response,
)
from app.legal_retrieval_reconciliation import (
    RemovalReconciliationError,
    reconcile_source_removal,
)


JID = "KSDM,100,簡,5635,20111130,1"
OBSERVED_AT = "2026-10-15T12:00:00Z"


def query():
    return build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )


def normalized_provider_response():
    fixture = {"success": True, "results": [{"jid": JID}]}
    result = TaiwanLegalDbFixtureAdapter(fixture).search(query())
    return normalize_adapter_response(query(), result)


def removal_event(locator=JID, provider_id="fixture-judicial-open-data-jdoc-v1"):
    return SourceRemovalRequired(provider_id, locator)


def test_reconciliation_removes_registered_source_and_persists_hashed_tombstone(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    response = normalized_provider_response()
    cache.store(response)

    event = reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    payload = cache.load()
    assert event["status"] == "REMOVED"
    assert event["removed_record_count"] == 1
    assert event["source_locator_sha256"] == hashlib.sha256(JID.encode()).hexdigest()
    assert all(
        record["source_id"] != "JUDG-KSDM-100-JIAN-5635"
        for entry in payload["entries"].values()
        for record in entry["records"]
    )
    saved = cache.path.read_text(encoding="utf-8")
    assert JID not in saved
    assert payload["removal_audit"] == [event]


def test_reconciliation_preserves_unrelated_records_in_same_cached_response(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    mixed = normalize_adapter_response(query(), OfflineLinkageAdapter().search(query()))
    cache.store(mixed)
    reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    remaining = next(iter(cache.load()["entries"].values()))["records"]
    assert {record["source_id"] for record in remaining} == {
        "LAW-CRIMINAL-CODE-320",
        "LAW-CRIMINAL-CODE-335",
    }


def test_reconciliation_is_idempotent_for_same_observation(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    first = reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    second = reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    assert first == second
    assert first["status"] == "TOMBSTONED_NOT_PRESENT"
    assert len(cache.load()["removal_audit"]) == 1


def test_tombstone_blocks_stale_source_from_being_written_back(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    response = normalized_provider_response()
    reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    with pytest.raises(RetrievalCacheIntegrityError, match="已移除來源"):
        cache.store(response)


def test_unknown_locator_or_provider_fails_closed_without_cache_change(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    cache.store(normalized_provider_response())
    before = cache.path.read_bytes()
    with pytest.raises(RemovalReconciliationError, match="精確映射一筆"):
        reconcile_source_removal(cache, removal_event("UNKNOWN"), observed_at=OBSERVED_AT)
    with pytest.raises(RemovalReconciliationError, match="不支援"):
        reconcile_source_removal(
            cache,
            removal_event(provider_id="unknown-provider"),
            observed_at=OBSERVED_AT,
        )
    assert cache.path.read_bytes() == before


def test_atomic_replace_failure_leaves_original_cache_unchanged(tmp_path, monkeypatch):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    cache.store(normalized_provider_response())
    before = cache.path.read_bytes()

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("app.legal_retrieval_cache.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    assert cache.path.read_bytes() == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_tampered_removal_audit_is_rejected(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    reconcile_source_removal(cache, removal_event(), observed_at=OBSERVED_AT)
    payload = json.loads(cache.path.read_text(encoding="utf-8"))
    payload["removal_audit"][0]["source_id"] = "TAMPERED"
    cache.path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RetrievalCacheIntegrityError, match="removal audit integrity"):
        cache.load()


def test_jdoc_error_can_be_reconciled_without_parsing_untrusted_error_text(tmp_path):
    adapter = JudicialOpenDataFixtureAdapter(
        {"error": "任意錯誤說明不得進入 cache"}, requested_jid=JID
    )
    with pytest.raises(SourceRemovalRequired) as exc:
        adapter.search(query())
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    event = reconcile_source_removal(cache, exc.value, observed_at=OBSERVED_AT)
    assert event["status"] == "TOMBSTONED_NOT_PRESENT"
    assert "任意錯誤說明" not in cache.path.read_text(encoding="utf-8")
