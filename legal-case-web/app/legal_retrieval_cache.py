"""法律檢索回應正規化與本機 metadata 快取。

快取只保存公開來源 metadata、來源指紋、關聯 ID 與審查狀態。全文、節錄、
案件 payload 及個資欄位一律拒絕；本模組不提供網路連線，也未接入 Gate 2。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .legal_retrieval import validate_deidentified_query


LEGACY_CACHE_SCHEMA_VERSION = "legal-retrieval-metadata-cache-v1"
CACHE_SCHEMA_VERSION = "legal-retrieval-metadata-cache-v2"
NORMALIZED_RESPONSE_VERSION = "legal-retrieval-normalized-response-v1"
ALLOWED_HASH_SCOPES = {
    "FULL_PUBLIC_DOCUMENT",
    "REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT",
}
ALLOWED_OFFICIAL_HOSTS = {
    "law.moj.gov.tw",
    "judgment.judicial.gov.tw",
    "lawsearch.judicial.gov.tw",
    "psue.moj.gov.tw",
    "www.tph.moj.gov.tw",
}
FORBIDDEN_HIT_KEYS = {
    "content",
    "content_text",
    "excerpt",
    "raw_document",
    "case_payload",
    "personal_data",
    "name",
    "address",
    "case_number",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_RECORD_KEYS = {
    "source_id",
    "source_type",
    "authority",
    "title",
    "canonical_url",
    "document_date",
    "source_fingerprint_sha256",
    "hash_scope",
    "relation_ids",
    "content_stored",
    "legal_conclusion",
    "review_status",
    "record_integrity_sha256",
}
EXPECTED_RESPONSE_KEYS = {
    "schema_version",
    "adapter_id",
    "external_network",
    "query_id",
    "query_sha256",
    "records",
    "content_stored",
    "legal_conclusion",
    "review_status",
    "response_integrity_sha256",
}
EXPECTED_REMOVAL_AUDIT_KEYS = {
    "event_id",
    "provider_id",
    "source_id",
    "source_locator_sha256",
    "observed_at",
    "status",
    "affected_cache_keys",
    "removed_record_count",
    "before_entries_sha256",
    "after_entries_sha256",
    "content_stored",
    "legal_conclusion",
    "review_status",
    "event_integrity_sha256",
}


class RetrievalNormalizationError(ValueError):
    pass


class RetrievalCacheIntegrityError(RuntimeError):
    pass


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.isoformat().endswith("+00:00")


def normalize_adapter_response(
    query: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    """將 adapter 結果縮減為可快取 metadata；禁止全文與案件資料。"""
    query_errors = validate_deidentified_query(query)
    if query_errors:
        raise RetrievalNormalizationError(f"去識別查詢無效：{query_errors}")
    if result.get("query_id") != query["query_id"]:
        raise RetrievalNormalizationError("adapter 回應的 query_id 不一致")
    if result.get("legal_conclusion") is not False:
        raise RetrievalNormalizationError("adapter 回應不得包含法律結論")
    if result.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise RetrievalNormalizationError("adapter 回應必須保留人工審查")
    adapter_id = result.get("adapter_id")
    if not isinstance(adapter_id, str) or not adapter_id.strip():
        raise RetrievalNormalizationError("adapter_id 缺漏")
    if not isinstance(result.get("external_network"), bool):
        raise RetrievalNormalizationError("external_network 必須為布林值")

    allowed_types = set(query["allowed_source_types"])
    raw_hits = result.get("hits", [])
    if not isinstance(raw_hits, list) or any(not isinstance(hit, dict) for hit in raw_hits):
        raise RetrievalNormalizationError("adapter hits 格式錯誤")
    records: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for hit in raw_hits:
        forbidden = set(hit) & FORBIDDEN_HIT_KEYS
        if forbidden:
            raise RetrievalNormalizationError(
                f"來源回應含禁止快取欄位：{sorted(forbidden)}"
            )
        source_id = hit.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in source_ids:
            raise RetrievalNormalizationError(f"來源 ID 缺漏或重複：{source_id!r}")
        source_ids.add(source_id)
        source_type = hit.get("source_type")
        if source_type not in allowed_types:
            raise RetrievalNormalizationError(f"{source_id}: source_type 未經查詢允許")
        canonical_url = hit.get("canonical_url")
        parsed = urlparse(canonical_url if isinstance(canonical_url, str) else "")
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_OFFICIAL_HOSTS:
            raise RetrievalNormalizationError(f"{source_id}: canonical_url 不是核准官方來源")
        if not _is_iso_date(hit.get("document_date")):
            raise RetrievalNormalizationError(f"{source_id}: document_date 必須為 ISO 日期")
        content_hash = hit.get("content_sha256")
        if not isinstance(content_hash, str) or not SHA256_PATTERN.fullmatch(content_hash):
            raise RetrievalNormalizationError(f"{source_id}: content_sha256 格式錯誤")
        hash_scope = hit.get("hash_scope")
        if hash_scope not in ALLOWED_HASH_SCOPES:
            raise RetrievalNormalizationError(f"{source_id}: hash_scope 缺漏或不支援")
        if hit.get("legal_conclusion") is not False:
            raise RetrievalNormalizationError(f"{source_id}: 不得包含法律結論")
        if hit.get("review_status") != "HUMAN_REVIEW_REQUIRED":
            raise RetrievalNormalizationError(f"{source_id}: 必須保留人工審查")
        relation_ids = hit.get("relation_ids")
        if (
            not isinstance(relation_ids, list)
            or not relation_ids
            or any(not isinstance(item, str) or not item for item in relation_ids)
        ):
            raise RetrievalNormalizationError(f"{source_id}: relation_ids 缺漏")

        record = {
            "source_id": source_id,
            "source_type": source_type,
            "authority": str(hit.get("authority", "")).strip(),
            "title": str(hit.get("title", "")).strip(),
            "canonical_url": canonical_url,
            "document_date": hit["document_date"],
            "source_fingerprint_sha256": content_hash,
            "hash_scope": hash_scope,
            "relation_ids": sorted(set(relation_ids)),
            "content_stored": False,
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }
        if not record["authority"] or not record["title"]:
            raise RetrievalNormalizationError(f"{source_id}: authority 或 title 缺漏")
        record["record_integrity_sha256"] = _canonical_hash(record)
        records.append(record)

    records.sort(key=lambda item: item["source_id"])
    core = {
        "schema_version": NORMALIZED_RESPONSE_VERSION,
        "adapter_id": adapter_id,
        "external_network": result["external_network"],
        "query_id": query["query_id"],
        "query_sha256": query["query_sha256"],
        "records": records,
        "content_stored": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    return {**core, "response_integrity_sha256": _canonical_hash(core)}


def validate_normalized_response(response: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(response) != EXPECTED_RESPONSE_KEYS:
        errors.append("normalized response 欄位集合不符")
    if response.get("schema_version") != NORMALIZED_RESPONSE_VERSION:
        errors.append("normalized response schema 不符")
    if not isinstance(response.get("adapter_id"), str) or not response.get("adapter_id"):
        errors.append("normalized response adapter_id 缺漏")
    if not isinstance(response.get("external_network"), bool):
        errors.append("normalized response external_network 格式錯誤")
    if not isinstance(response.get("query_id"), str) or not response.get("query_id", "").startswith("query:"):
        errors.append("normalized response query_id 格式錯誤")
    if not isinstance(response.get("query_sha256"), str) or not SHA256_PATTERN.fullmatch(response.get("query_sha256", "")):
        errors.append("normalized response query_sha256 格式錯誤")
    if response.get("content_stored") is not False:
        errors.append("normalized response 不得保存全文")
    if response.get("legal_conclusion") is not False:
        errors.append("normalized response 不得包含法律結論")
    if response.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        errors.append("normalized response 必須保留人工審查")

    records = response.get("records")
    if not isinstance(records, list):
        errors.append("records 格式錯誤")
        records = []
    source_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("record 格式錯誤")
            continue
        if set(record) != EXPECTED_RECORD_KEYS:
            errors.append(f"{record.get('source_id', '')}: record 欄位集合不符")
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in source_ids:
            errors.append(f"來源 ID 缺漏或重複：{source_id!r}")
        else:
            source_ids.add(source_id)
        if record.get("source_type") not in {"statute", "judgment"}:
            errors.append(f"{source_id}: source_type 不支援")
        parsed = urlparse(str(record.get("canonical_url", "")))
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_OFFICIAL_HOSTS:
            errors.append(f"{source_id}: canonical_url 不是核准官方來源")
        if not _is_iso_date(record.get("document_date")):
            errors.append(f"{source_id}: document_date 格式錯誤")
        if not isinstance(record.get("source_fingerprint_sha256"), str) or not SHA256_PATTERN.fullmatch(record.get("source_fingerprint_sha256", "")):
            errors.append(f"{source_id}: source fingerprint 格式錯誤")
        if record.get("hash_scope") not in ALLOWED_HASH_SCOPES:
            errors.append(f"{source_id}: hash_scope 不支援")
        relation_ids = record.get("relation_ids")
        if not isinstance(relation_ids, list) or not relation_ids or any(not isinstance(item, str) or not item for item in relation_ids):
            errors.append(f"{source_id}: relation_ids 格式錯誤")
        if record.get("review_status") != "HUMAN_REVIEW_REQUIRED":
            errors.append(f"{source_id}: 必須保留人工審查")
        integrity = record.get("record_integrity_sha256")
        core = {key: value for key, value in record.items() if key != "record_integrity_sha256"}
        if integrity != _canonical_hash(core):
            errors.append(f"{record.get('source_id', '')}: record integrity 不符")
        if record.get("content_stored") is not False:
            errors.append(f"{record.get('source_id', '')}: 不得保存全文")
        if record.get("legal_conclusion") is not False:
            errors.append(f"{record.get('source_id', '')}: 不得包含法律結論")

    response_hash = response.get("response_integrity_sha256")
    core = {
        key: value
        for key, value in response.items()
        if key != "response_integrity_sha256"
    }
    if response_hash != _canonical_hash(core):
        errors.append("response integrity 不符")
    return errors


def validate_removal_audit_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(event) != EXPECTED_REMOVAL_AUDIT_KEYS:
        errors.append("removal audit 欄位集合不符")
    if not isinstance(event.get("event_id"), str) or not event.get("event_id", "").startswith("removal:"):
        errors.append("removal audit event_id 格式錯誤")
    for key in ("provider_id", "source_id"):
        if not isinstance(event.get(key), str) or not event.get(key):
            errors.append(f"removal audit {key} 缺漏")
    for key in (
        "source_locator_sha256",
        "before_entries_sha256",
        "after_entries_sha256",
    ):
        if not isinstance(event.get(key), str) or not SHA256_PATTERN.fullmatch(event.get(key, "")):
            errors.append(f"removal audit {key} 格式錯誤")
    if not _is_utc_timestamp(event.get("observed_at")):
        errors.append("removal audit observed_at 必須為 UTC ISO timestamp")
    if event.get("status") not in {"REMOVED", "TOMBSTONED_NOT_PRESENT"}:
        errors.append("removal audit status 不支援")
    affected = event.get("affected_cache_keys")
    if (
        not isinstance(affected, list)
        or any(not isinstance(item, str) or not item for item in affected)
        or affected != sorted(set(affected))
    ):
        errors.append("removal audit affected_cache_keys 格式錯誤")
    if not isinstance(event.get("removed_record_count"), int) or event.get("removed_record_count", -1) < 0:
        errors.append("removal audit removed_record_count 格式錯誤")
    if event.get("content_stored") is not False:
        errors.append("removal audit 不得保存全文")
    if event.get("legal_conclusion") is not False:
        errors.append("removal audit 不得包含法律結論")
    if event.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        errors.append("removal audit 必須保留人工審查")
    integrity = event.get("event_integrity_sha256")
    core = {key: value for key, value in event.items() if key != "event_integrity_sha256"}
    if integrity != _canonical_hash(core):
        errors.append("removal audit integrity 不符")
    return errors


class RetrievalMetadataCache:
    """需明示路徑的原子 JSON cache；不提供預設正式資料位置。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "entries": {},
            "removal_audit": [],
        }

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RetrievalCacheIntegrityError("無法讀取法律檢索 metadata cache") from exc
        schema_version = payload.get("schema_version")
        if schema_version not in {CACHE_SCHEMA_VERSION, LEGACY_CACHE_SCHEMA_VERSION}:
            raise RetrievalCacheIntegrityError("法律檢索 metadata cache schema 不符")
        expected_keys = {"schema_version", "entries"}
        if schema_version == CACHE_SCHEMA_VERSION:
            expected_keys.add("removal_audit")
        if set(payload) != expected_keys:
            raise RetrievalCacheIntegrityError("法律檢索 metadata cache 欄位集合不符")
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            raise RetrievalCacheIntegrityError("法律檢索 metadata cache entries 格式錯誤")
        for key, response in entries.items():
            if key != self.cache_key(response):
                raise RetrievalCacheIntegrityError(f"cache key 不符：{key}")
            errors = validate_normalized_response(response)
            if errors:
                raise RetrievalCacheIntegrityError(f"cache integrity 不符：{errors}")
        if schema_version == LEGACY_CACHE_SCHEMA_VERSION:
            return {
                "schema_version": CACHE_SCHEMA_VERSION,
                "entries": entries,
                "removal_audit": [],
            }
        removal_audit = payload.get("removal_audit")
        if not isinstance(removal_audit, list):
            raise RetrievalCacheIntegrityError("法律檢索 removal_audit 格式錯誤")
        event_ids: set[str] = set()
        for event in removal_audit:
            if not isinstance(event, dict):
                raise RetrievalCacheIntegrityError("法律檢索 removal audit event 格式錯誤")
            errors = validate_removal_audit_event(event)
            if errors:
                raise RetrievalCacheIntegrityError(f"removal audit integrity 不符：{errors}")
            event_id = event["event_id"]
            if event_id in event_ids:
                raise RetrievalCacheIntegrityError(f"removal audit event_id 重複：{event_id}")
            event_ids.add(event_id)
        return payload

    @staticmethod
    def cache_key(response: dict[str, Any]) -> str:
        return f"{response.get('adapter_id', '')}:{response.get('query_sha256', '')}"

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        except Exception:
            try:
                Path(temp_name).unlink(missing_ok=True)
            finally:
                raise

    @classmethod
    def _stage_store(
        cls, payload: dict[str, Any], response: dict[str, Any]
    ) -> tuple[str, bool]:
        errors = validate_normalized_response(response)
        if errors:
            raise RetrievalCacheIntegrityError(f"拒絕寫入無效 response：{errors}")
        tombstoned_source_ids = {
            event["source_id"] for event in payload["removal_audit"]
        }
        blocked = sorted(
            record["source_id"]
            for record in response["records"]
            if record["source_id"] in tombstoned_source_ids
        )
        if blocked:
            raise RetrievalCacheIntegrityError(f"拒絕寫回已移除來源：{blocked}")
        key = cls.cache_key(response)
        changed = payload["entries"].get(key) != response
        payload["entries"][key] = copy.deepcopy(response)
        return key, changed

    @staticmethod
    def _stage_evict_source(
        payload: dict[str, Any],
        *,
        source_id: str,
        provider_id: str,
        source_locator_sha256: str,
        observed_at: str,
    ) -> tuple[dict[str, Any], bool]:
        if not source_id or not provider_id:
            raise RetrievalCacheIntegrityError("source_id 與 provider_id 不得為空")
        if not SHA256_PATTERN.fullmatch(source_locator_sha256):
            raise RetrievalCacheIntegrityError("source locator hash 格式錯誤")
        if not _is_utc_timestamp(observed_at):
            raise RetrievalCacheIntegrityError("observed_at 必須為 UTC ISO timestamp")
        event_id = "removal:" + _canonical_hash(
            {
                "provider_id": provider_id,
                "source_locator_sha256": source_locator_sha256,
                "observed_at": observed_at,
            }
        )
        existing = next(
            (event for event in payload["removal_audit"] if event["event_id"] == event_id),
            None,
        )
        if existing is not None:
            return existing, False

        entries = copy.deepcopy(payload["entries"])
        before_hash = _canonical_hash(entries)
        affected_keys: list[str] = []
        removed_count = 0
        for key, response in entries.items():
            kept_records = [
                record for record in response["records"] if record["source_id"] != source_id
            ]
            removed_here = len(response["records"]) - len(kept_records)
            if not removed_here:
                continue
            affected_keys.append(key)
            removed_count += removed_here
            response["records"] = kept_records
            core = {
                field: value
                for field, value in response.items()
                if field != "response_integrity_sha256"
            }
            response["response_integrity_sha256"] = _canonical_hash(core)

        affected_keys.sort()
        event_core = {
            "event_id": event_id,
            "provider_id": provider_id,
            "source_id": source_id,
            "source_locator_sha256": source_locator_sha256,
            "observed_at": observed_at,
            "status": "REMOVED" if removed_count else "TOMBSTONED_NOT_PRESENT",
            "affected_cache_keys": affected_keys,
            "removed_record_count": removed_count,
            "before_entries_sha256": before_hash,
            "after_entries_sha256": _canonical_hash(entries),
            "content_stored": False,
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }
        event = {**event_core, "event_integrity_sha256": _canonical_hash(event_core)}
        errors = validate_removal_audit_event(event)
        if errors:
            raise RetrievalCacheIntegrityError(f"拒絕寫入無效 removal audit：{errors}")
        payload["entries"] = entries
        payload["removal_audit"].append(event)
        return event, True

    def transaction(self) -> "RetrievalMetadataCacheTransaction":
        return RetrievalMetadataCacheTransaction(self)

    def store(self, response: dict[str, Any]) -> str:
        payload = self.load()
        key, _changed = self._stage_store(payload, response)
        self._atomic_write(payload)
        return key

    def get(self, adapter_id: str, query_sha256: str) -> dict[str, Any] | None:
        return self.load()["entries"].get(f"{adapter_id}:{query_sha256}")

    def evict_source(
        self,
        *,
        source_id: str,
        provider_id: str,
        source_locator_sha256: str,
        observed_at: str,
    ) -> dict[str, Any]:
        """原子移除來源 metadata，並在同一 cache 寫入不可回填的 tombstone。"""
        payload = self.load()
        event, changed = self._stage_evict_source(
            payload,
            source_id=source_id,
            provider_id=provider_id,
            source_locator_sha256=source_locator_sha256,
            observed_at=observed_at,
        )
        if not changed:
            return event
        self._atomic_write(payload)
        return event


class RetrievalMetadataCacheTransaction:
    """記憶體內 cache transaction；全部成功後才以一次原子替換提交。"""

    def __init__(self, cache: RetrievalMetadataCache) -> None:
        self._cache = cache
        self._payload = copy.deepcopy(cache.load())
        self._base_integrity = _canonical_hash(self._payload)
        self._dirty = False
        self._closed = False

    @staticmethod
    def cache_key(response: dict[str, Any]) -> str:
        return RetrievalMetadataCache.cache_key(response)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _ensure_open(self) -> None:
        if self._closed:
            raise RetrievalCacheIntegrityError("cache transaction 已關閉")

    def load(self) -> dict[str, Any]:
        self._ensure_open()
        return copy.deepcopy(self._payload)

    def store(self, response: dict[str, Any]) -> str:
        self._ensure_open()
        key, changed = self._cache._stage_store(self._payload, response)
        self._dirty = self._dirty or changed
        return key

    def evict_source(
        self,
        *,
        source_id: str,
        provider_id: str,
        source_locator_sha256: str,
        observed_at: str,
    ) -> dict[str, Any]:
        self._ensure_open()
        event, changed = self._cache._stage_evict_source(
            self._payload,
            source_id=source_id,
            provider_id=provider_id,
            source_locator_sha256=source_locator_sha256,
            observed_at=observed_at,
        )
        self._dirty = self._dirty or changed
        return event

    def commit(self) -> bool:
        self._ensure_open()
        if not self._dirty:
            self._closed = True
            return False
        current = self._cache.load()
        if _canonical_hash(current) != self._base_integrity:
            raise RetrievalCacheIntegrityError(
                "cache 在 batch transaction 期間已變更；拒絕覆寫"
            )
        self._cache._atomic_write(self._payload)
        self._closed = True
        return True

    def discard(self) -> None:
        self._closed = True
