"""離線 provider fixture 的受控同步協調器。

預設只產生 dry-run 計畫。只有呼叫端明示 ``commit=True`` 時才寫入指定的
metadata cache；本模組不提供網路連線，也未接入 Gate 2。
"""

from __future__ import annotations

from typing import Any

from .legal_provider_fixtures import SourceRemovalRequired
from .legal_retrieval import LegalRetrievalAdapter, validate_deidentified_query
from .legal_retrieval_cache import RetrievalMetadataCache, normalize_adapter_response
from .legal_retrieval_reconciliation import (
    preview_source_removal,
    reconcile_source_removal,
)


SYNC_REPORT_VERSION = "legal-retrieval-offline-sync-report-v1"


class OfflineSyncError(RuntimeError):
    pass


def _base_report(
    *,
    operation: str,
    status: str,
    adapter_id: str,
    query_id: str,
    cache_mutated: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SYNC_REPORT_VERSION,
        "operation": operation,
        "status": status,
        "adapter_id": adapter_id,
        "query_id": query_id,
        "external_network": False,
        "cache_mutated": cache_mutated,
        "content_stored": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }


def run_offline_sync(
    query: dict[str, Any],
    adapter: LegalRetrievalAdapter,
    cache: RetrievalMetadataCache,
    *,
    commit: bool = False,
    observed_at: str | None = None,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """執行單一離線 fixture sync；預設 dry-run 且不建立 cache。"""
    query_errors = validate_deidentified_query(query, pack=pack)
    if query_errors:
        raise OfflineSyncError(f"去識別查詢無效：{query_errors}")
    adapter_id = getattr(adapter, "adapter_id", None)
    if not isinstance(adapter_id, str) or not adapter_id:
        raise OfflineSyncError("adapter_id 缺漏")
    if getattr(adapter, "external_network", None) is not False:
        raise OfflineSyncError("offline sync 禁止使用外部網路 adapter")

    try:
        result = adapter.search(query)
    except SourceRemovalRequired as removal:
        if removal.provider_id != adapter_id:
            raise OfflineSyncError("來源移除 provider 與 adapter_id 不一致") from removal
        preview = preview_source_removal(cache, removal, pack=pack)
        if commit:
            if observed_at is None:
                raise OfflineSyncError("commit 移除事件必須提供 observed_at") from removal
            known_event_ids = {
                event["event_id"] for event in cache.load()["removal_audit"]
            }
            event = reconcile_source_removal(
                cache,
                removal,
                observed_at=observed_at,
                pack=pack,
            )
            removal_status = event["status"]
            affected_keys = event["affected_cache_keys"]
            removed_count = event["removed_record_count"]
            cache_mutated = event["event_id"] not in known_event_ids
        else:
            removal_status = preview["projected_status"]
            affected_keys = preview["affected_cache_keys"]
            removed_count = preview["removed_record_count"]
            cache_mutated = False
        return {
            **_base_report(
                operation="REMOVE_METADATA",
                status="COMMITTED" if commit else "DRY_RUN",
                adapter_id=adapter_id,
                query_id=query["query_id"],
                cache_mutated=cache_mutated,
            ),
            "source_ids": [preview["source_id"]],
            "affected_cache_keys": affected_keys,
            "record_count": 0,
            "removed_record_count": removed_count,
            "removal_status": removal_status,
        }

    if result.get("adapter_id") != adapter_id:
        raise OfflineSyncError("adapter 回應的 adapter_id 不一致")
    if result.get("external_network") is not False:
        raise OfflineSyncError("offline sync 回應不得標記外部網路")
    normalized = normalize_adapter_response(query, result)
    cache_key = cache.cache_key(normalized)
    if commit:
        cache.store(normalized)
    return {
        **_base_report(
            operation="STORE_METADATA",
            status="COMMITTED" if commit else "DRY_RUN",
            adapter_id=adapter_id,
            query_id=query["query_id"],
            cache_mutated=commit,
        ),
        "source_ids": [record["source_id"] for record in normalized["records"]],
        "affected_cache_keys": [cache_key],
        "record_count": len(normalized["records"]),
        "removed_record_count": 0,
        "removal_status": None,
    }
