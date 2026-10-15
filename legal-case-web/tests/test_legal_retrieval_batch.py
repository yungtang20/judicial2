import copy
import json

import pytest

from app.legal_provider_fixtures import (
    JudicialOpenDataFixtureAdapter,
    TaiwanLegalDbFixtureAdapter,
)
from app.legal_retrieval import OfflineLinkageAdapter, build_deidentified_query
from app.legal_retrieval_batch import (
    OfflineBatchError,
    build_offline_batch_manifest,
    run_offline_batch,
    validate_offline_batch_manifest,
)
from app.legal_retrieval_cache import (
    RetrievalCacheIntegrityError,
    RetrievalMetadataCache,
    normalize_adapter_response,
)


JID = "KSDM,100,簡,5635,20111130,1"
OBSERVED_AT = "2026-10-15T12:00:00Z"
SEARCH_ID = "fixture-mcp-taiwan-legal-db-v1"
REMOVAL_ID = "fixture-judicial-open-data-jdoc-v1"


def query():
    return build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )


def search_adapter():
    return TaiwanLegalDbFixtureAdapter(
        {"success": True, "results": [{"jid": JID, "summary": "不得外洩"}]}
    )


def removal_adapter():
    return JudicialOpenDataFixtureAdapter({"error": "不得外洩"}, requested_jid=JID)


def test_manifest_is_deterministic_and_rejects_tampering():
    manifest = build_offline_batch_manifest([(SEARCH_ID, query())])
    assert validate_offline_batch_manifest(manifest) == []
    assert manifest == build_offline_batch_manifest([(SEARCH_ID, query())])
    tampered = copy.deepcopy(manifest)
    tampered["items"][0]["query"]["query_text"] += " 任意文字"
    assert validate_offline_batch_manifest(tampered)


def test_manifest_rejects_empty_or_duplicate_requests():
    with pytest.raises(OfflineBatchError, match="不得為空"):
        build_offline_batch_manifest([])
    with pytest.raises(OfflineBatchError, match="重複"):
        build_offline_batch_manifest([(SEARCH_ID, query()), (SEARCH_ID, query())])


def test_batch_dry_run_simulates_order_without_creating_cache(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    manifest = build_offline_batch_manifest(
        [(SEARCH_ID, query()), (REMOVAL_ID, query())]
    )
    report = run_offline_batch(
        manifest,
        {SEARCH_ID: search_adapter(), REMOVAL_ID: removal_adapter()},
        cache,
        observed_at=OBSERVED_AT,
    )
    assert report["status"] == "DRY_RUN"
    assert report["cache_mutated"] is False
    assert [item["operation"] for item in report["items"]] == [
        "STORE_METADATA",
        "REMOVE_METADATA",
    ]
    assert all(item["would_mutate"] for item in report["items"])
    assert not cache.path.exists()
    serialized = json.dumps(report, ensure_ascii=False)
    assert JID not in serialized
    assert "不得外洩" not in serialized
    assert query()["query_text"] not in serialized


def test_batch_commit_applies_all_items_with_one_final_cache_state(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    manifest = build_offline_batch_manifest(
        [(SEARCH_ID, query()), (REMOVAL_ID, query())]
    )
    report = run_offline_batch(
        manifest,
        {SEARCH_ID: search_adapter(), REMOVAL_ID: removal_adapter()},
        cache,
        commit=True,
        observed_at=OBSERVED_AT,
    )
    assert report["status"] == "COMMITTED"
    assert report["cache_mutated"] is True
    payload = cache.load()
    assert len(payload["entries"]) == 1
    assert next(iter(payload["entries"].values()))["records"] == []
    assert len(payload["removal_audit"]) == 1


class InvalidSecondAdapter:
    adapter_id = "invalid-second-v1"
    external_network = False

    def search(self, query_value):
        return {
            "adapter_id": "spoofed-v1",
            "external_network": False,
            "query_id": query_value["query_id"],
            "hits": [],
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }


def test_late_item_failure_leaves_original_cache_unchanged(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    invalid_id = InvalidSecondAdapter.adapter_id
    manifest = build_offline_batch_manifest(
        [(SEARCH_ID, query()), (invalid_id, query())]
    )
    with pytest.raises(RuntimeError, match="adapter_id 不一致"):
        run_offline_batch(
            manifest,
            {SEARCH_ID: search_adapter(), invalid_id: InvalidSecondAdapter()},
            cache,
            commit=True,
            observed_at=OBSERVED_AT,
        )
    assert not cache.path.exists()


def test_removal_then_stale_store_fails_entire_batch(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    manifest = build_offline_batch_manifest(
        [(REMOVAL_ID, query()), (SEARCH_ID, query())]
    )
    with pytest.raises(RetrievalCacheIntegrityError, match="已移除來源"):
        run_offline_batch(
            manifest,
            {SEARCH_ID: search_adapter(), REMOVAL_ID: removal_adapter()},
            cache,
            commit=True,
            observed_at=OBSERVED_AT,
        )
    assert not cache.path.exists()


class ConcurrentMutationAdapter:
    adapter_id = "concurrent-mutation-v1"
    external_network = False

    def __init__(self, cache):
        self.cache = cache

    def search(self, query_value):
        result = search_adapter().search(query_value)
        result["adapter_id"] = self.adapter_id
        from app.legal_retrieval_cache import normalize_adapter_response

        self.cache.store(normalize_adapter_response(query_value, result))
        return result


def test_concurrent_cache_drift_blocks_batch_commit(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    adapter = ConcurrentMutationAdapter(cache)
    manifest = build_offline_batch_manifest([(adapter.adapter_id, query())])
    with pytest.raises(RetrievalCacheIntegrityError, match="transaction 期間已變更"):
        run_offline_batch(
            manifest,
            {adapter.adapter_id: adapter},
            cache,
            commit=True,
            observed_at=OBSERVED_AT,
        )
    assert len(cache.load()["entries"]) == 1


def test_adapter_mapping_must_exactly_match_manifest(tmp_path):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    manifest = build_offline_batch_manifest([(SEARCH_ID, query())])
    with pytest.raises(OfflineBatchError, match="完全一致"):
        run_offline_batch(manifest, {}, cache)


def test_final_atomic_replace_failure_preserves_original_cache(tmp_path, monkeypatch):
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    offline_result = OfflineLinkageAdapter().search(query())
    cache.store(normalize_adapter_response(query(), offline_result))
    before = cache.path.read_bytes()
    manifest = build_offline_batch_manifest([(SEARCH_ID, query())])

    def fail_replace(_source, _target):
        raise OSError("simulated batch replace failure")

    monkeypatch.setattr("app.legal_retrieval_cache.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated batch"):
        run_offline_batch(
            manifest,
            {SEARCH_ID: search_adapter()},
            cache,
            commit=True,
            observed_at=OBSERVED_AT,
        )
    assert cache.path.read_bytes() == before
    assert list(tmp_path.glob("*.tmp")) == []
