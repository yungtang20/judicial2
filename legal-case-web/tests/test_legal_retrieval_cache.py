import copy
import hashlib
import json

import pytest

from app.legal_retrieval import OfflineLinkageAdapter, build_deidentified_query
from app.legal_retrieval_cache import (
    CACHE_SCHEMA_VERSION,
    LEGACY_CACHE_SCHEMA_VERSION,
    RetrievalCacheIntegrityError,
    RetrievalMetadataCache,
    RetrievalNormalizationError,
    normalize_adapter_response,
    validate_normalized_response,
)


def sample_query_and_result():
    query = build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )
    return query, OfflineLinkageAdapter().search(query)


def canonical_hash(value):
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_normalization_keeps_metadata_and_hash_scope_but_not_content():
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    assert validate_normalized_response(normalized) == []
    assert normalized["content_stored"] is False
    assert normalized["legal_conclusion"] is False
    assert normalized["records"]
    serialized = json.dumps(normalized, ensure_ascii=False)
    assert "fingerprinted_text" not in serialized
    assert "content_text" not in serialized
    assert all(record["content_stored"] is False for record in normalized["records"])
    assert {
        record["hash_scope"] for record in normalized["records"]
    } == {"REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT"}


@pytest.mark.parametrize("forbidden_key", ["content", "excerpt", "case_payload", "personal_data", "address"])
def test_normalization_rejects_raw_content_and_case_fields(forbidden_key):
    query, result = sample_query_and_result()
    result["hits"][0][forbidden_key] = "不得寫入快取的案件資料"
    with pytest.raises(RetrievalNormalizationError, match="禁止快取欄位"):
        normalize_adapter_response(query, result)


def test_normalization_rejects_non_official_url_and_hash_overclaim():
    query, result = sample_query_and_result()
    result["hits"][0]["canonical_url"] = "https://example.com/not-official"
    with pytest.raises(RetrievalNormalizationError, match="核准官方來源"):
        normalize_adapter_response(query, result)

    query, result = sample_query_and_result()
    result["hits"][0]["hash_scope"] = "FULL_DOCUMENT_VERIFIED"
    with pytest.raises(RetrievalNormalizationError, match="hash_scope"):
        normalize_adapter_response(query, result)


def test_normalization_rejects_query_mismatch_and_legal_conclusion():
    query, result = sample_query_and_result()
    result["query_id"] = "query:other"
    with pytest.raises(RetrievalNormalizationError, match="query_id"):
        normalize_adapter_response(query, result)

    query, result = sample_query_and_result()
    result["legal_conclusion"] = True
    with pytest.raises(RetrievalNormalizationError, match="不得包含法律結論"):
        normalize_adapter_response(query, result)


def test_metadata_cache_round_trip_is_idempotent_and_contains_no_case_text(tmp_path):
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    cache_path = tmp_path / "retrieval-metadata.json"
    cache = RetrievalMetadataCache(cache_path)
    key1 = cache.store(normalized)
    key2 = cache.store(normalized)
    assert key1 == key2
    assert len(cache.load()["entries"]) == 1
    assert cache.get(result["adapter_id"], query["query_sha256"]) == normalized
    saved = cache_path.read_text(encoding="utf-8")
    assert query["query_text"] not in saved
    assert "content_text" not in saved
    assert "case_payload" not in saved


def test_metadata_cache_detects_record_tampering(tmp_path):
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    cache_path = tmp_path / "retrieval-metadata.json"
    cache = RetrievalMetadataCache(cache_path)
    key = cache.store(normalized)
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["entries"][key]["records"][0]["title"] = "遭竄改"
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RetrievalCacheIntegrityError, match="integrity"):
        cache.load()


def test_metadata_cache_rejects_tampered_response_before_write(tmp_path):
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    tampered = copy.deepcopy(normalized)
    tampered["records"][0]["source_id"] = "TAMPERED"
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(RetrievalCacheIntegrityError, match="拒絕寫入"):
        cache.store(tampered)
    assert not cache.path.exists()


def test_recomputed_hash_cannot_bypass_strict_normalized_schema(tmp_path):
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    record = normalized["records"][0]
    record["content_text"] = "即使重算 hash 也不得寫入"
    record["record_integrity_sha256"] = canonical_hash(
        {key: value for key, value in record.items() if key != "record_integrity_sha256"}
    )
    normalized["response_integrity_sha256"] = canonical_hash(
        {
            key: value
            for key, value in normalized.items()
            if key != "response_integrity_sha256"
        }
    )
    # 即使攻擊者重算兩層 hash，嚴格欄位集合仍須拒絕全文欄位。
    errors = validate_normalized_response(normalized)
    assert any("欄位集合不符" in error for error in errors)
    cache = RetrievalMetadataCache(tmp_path / "retrieval-metadata.json")
    with pytest.raises(RetrievalCacheIntegrityError, match="拒絕寫入"):
        cache.store(normalized)


def test_legacy_v1_cache_loads_in_memory_and_migrates_on_next_store(tmp_path):
    query, result = sample_query_and_result()
    normalized = normalize_adapter_response(query, result)
    cache_path = tmp_path / "retrieval-metadata.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": LEGACY_CACHE_SCHEMA_VERSION,
                "entries": {RetrievalMetadataCache.cache_key(normalized): normalized},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cache = RetrievalMetadataCache(cache_path)
    assert cache.load()["schema_version"] == CACHE_SCHEMA_VERSION
    cache.store(normalized)
    persisted = json.loads(cache_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == CACHE_SCHEMA_VERSION
    assert persisted["removal_audit"] == []
