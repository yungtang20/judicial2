import json

import pytest

from app.legal_provider_fixtures import (
    JudicialOpenDataFixtureAdapter,
    ProviderContractNotAvailable,
    SourceRemovalRequired,
    TaiwanLegalDbFixtureAdapter,
    psue_discovery_adapter,
)
from app.legal_retrieval import DisabledExternalAdapter, build_deidentified_query
from app.legal_retrieval_cache import RetrievalMetadataCache
from app.legal_retrieval_sync import OfflineSyncError, run_offline_sync


JID = "KSDM,100,簡,5635,20111130,1"
OBSERVED_AT = "2026-10-15T12:00:00Z"


def query():
    return build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )


def search_adapter():
    return TaiwanLegalDbFixtureAdapter(
        {
            "success": True,
            "results": [{"jid": JID, "summary": "fixture 敏感測試字串"}],
        }
    )


def removal_adapter():
    return JudicialOpenDataFixtureAdapter(
        {"error": "fixture 錯誤說明不得進入報告"},
        requested_jid=JID,
    )


def test_store_dry_run_is_default_and_does_not_create_cache(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    report = run_offline_sync(query(), search_adapter(), cache)
    assert report["operation"] == "STORE_METADATA"
    assert report["status"] == "DRY_RUN"
    assert report["cache_mutated"] is False
    assert report["record_count"] == 1
    assert not cache.path.exists()
    serialized = json.dumps(report, ensure_ascii=False)
    assert JID not in serialized
    assert "fixture 敏感測試字串" not in serialized
    assert query()["query_text"] not in serialized


def test_store_commit_writes_only_normalized_metadata(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    report = run_offline_sync(query(), search_adapter(), cache, commit=True)
    assert report["status"] == "COMMITTED"
    assert report["cache_mutated"] is True
    assert len(cache.load()["entries"]) == 1
    saved = cache.path.read_text(encoding="utf-8")
    assert JID not in saved
    assert "fixture 敏感測試字串" not in saved


def test_removal_dry_run_reports_plan_without_creating_cache(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    report = run_offline_sync(query(), removal_adapter(), cache)
    assert report["operation"] == "REMOVE_METADATA"
    assert report["status"] == "DRY_RUN"
    assert report["removal_status"] == "TOMBSTONED_NOT_PRESENT"
    assert not cache.path.exists()
    serialized = json.dumps(report, ensure_ascii=False)
    assert JID not in serialized
    assert "fixture 錯誤說明" not in serialized


def test_removal_commit_purges_cached_source_and_writes_tombstone(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    run_offline_sync(query(), search_adapter(), cache, commit=True)
    report = run_offline_sync(
        query(), removal_adapter(), cache, commit=True, observed_at=OBSERVED_AT
    )
    assert report["status"] == "COMMITTED"
    assert report["removal_status"] == "REMOVED"
    assert report["removed_record_count"] == 1
    payload = cache.load()
    assert len(payload["removal_audit"]) == 1
    assert all(not entry["records"] for entry in payload["entries"].values())


def test_removal_commit_requires_observed_at_before_mutation(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(OfflineSyncError, match="observed_at"):
        run_offline_sync(query(), removal_adapter(), cache, commit=True)
    assert not cache.path.exists()


def test_external_or_discovery_only_adapter_fails_without_cache_write(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(OfflineSyncError, match="禁止使用外部網路"):
        run_offline_sync(query(), DisabledExternalAdapter(), cache)
    with pytest.raises(ProviderContractNotAvailable, match="尚無足夠公開"):
        run_offline_sync(query(), psue_discovery_adapter(), cache)
    assert not cache.path.exists()


class MismatchedResponseAdapter:
    adapter_id = "fixture-mismatch-v1"
    external_network = False

    def search(self, query_value):
        return {
            "adapter_id": "spoofed-provider-v1",
            "external_network": False,
            "query_id": query_value["query_id"],
            "hits": [],
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }


def test_mismatched_adapter_identity_fails_closed(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(OfflineSyncError, match="adapter_id 不一致"):
        run_offline_sync(query(), MismatchedResponseAdapter(), cache, commit=True)
    assert not cache.path.exists()


class SpoofedRemovalAdapter:
    adapter_id = "fixture-mismatch-v1"
    external_network = False

    def search(self, _query_value):
        raise SourceRemovalRequired("fixture-judicial-open-data-jdoc-v1", JID)


def test_mismatched_removal_provider_fails_closed(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(OfflineSyncError, match="provider 與 adapter_id 不一致"):
        run_offline_sync(query(), SpoofedRemovalAdapter(), cache, commit=True)
    assert not cache.path.exists()


def test_repeated_removal_commit_reports_no_second_mutation(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    first = run_offline_sync(
        query(), removal_adapter(), cache, commit=True, observed_at=OBSERVED_AT
    )
    second = run_offline_sync(
        query(), removal_adapter(), cache, commit=True, observed_at=OBSERVED_AT
    )
    assert first["cache_mutated"] is True
    assert second["cache_mutated"] is False
    assert len(cache.load()["removal_audit"]) == 1
