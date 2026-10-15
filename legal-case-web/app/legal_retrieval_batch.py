"""離線 provider sync 的 deterministic manifest 與全批次原子交易。"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .legal_retrieval import LegalRetrievalAdapter, validate_deidentified_query
from .legal_retrieval_cache import RetrievalMetadataCache
from .legal_retrieval_sync import run_offline_sync


BATCH_MANIFEST_VERSION = "legal-retrieval-offline-batch-manifest-v1"
BATCH_REPORT_VERSION = "legal-retrieval-offline-batch-report-v1"


class OfflineBatchError(RuntimeError):
    pass


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_offline_batch_manifest(
    requests: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """由 adapter ID 與固定去識別 query 建立可重建驗證的 manifest。"""
    if not requests:
        raise OfflineBatchError("batch requests 不得為空")
    items: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, request in enumerate(requests, start=1):
        if not isinstance(request, tuple) or len(request) != 2:
            raise OfflineBatchError("每筆 batch request 必須是 (adapter_id, query)")
        adapter_id, query = request
        if not isinstance(adapter_id, str) or not adapter_id:
            raise OfflineBatchError("batch adapter_id 缺漏")
        if not isinstance(query, dict):
            raise OfflineBatchError("batch query 格式錯誤")
        query_errors = validate_deidentified_query(query)
        if query_errors:
            raise OfflineBatchError(f"batch query 無效：{query_errors}")
        pair = (adapter_id, query["query_sha256"])
        if pair in seen_pairs:
            raise OfflineBatchError(f"batch request 重複：{adapter_id}")
        seen_pairs.add(pair)
        item_seed = _canonical_hash(
            {"position": index, "adapter_id": adapter_id, "query_sha256": query["query_sha256"]}
        )
        items.append(
            {
                "item_id": f"item:{index}:{item_seed[:12]}",
                "adapter_id": adapter_id,
                "query": copy.deepcopy(query),
            }
        )
    core = {
        "schema_version": BATCH_MANIFEST_VERSION,
        "items": items,
        "external_network": False,
        "runtime_enabled": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    manifest_hash = _canonical_hash(core)
    return {
        **core,
        "batch_id": f"batch:{manifest_hash[:16]}",
        "manifest_sha256": manifest_hash,
    }


def validate_offline_batch_manifest(manifest: dict[str, Any]) -> list[str]:
    if not isinstance(manifest, dict):
        return ["batch manifest 格式錯誤"]
    items = manifest.get("items")
    if not isinstance(items, list):
        return ["batch manifest items 格式錯誤"]
    try:
        requests = [
            (item["adapter_id"], item["query"])
            for item in items
            if isinstance(item, dict)
        ]
        if len(requests) != len(items):
            return ["batch manifest item 格式錯誤"]
        expected = build_offline_batch_manifest(requests)
    except (KeyError, TypeError, OfflineBatchError) as exc:
        return [str(exc)]
    return [] if manifest == expected else ["batch manifest 與 deterministic builder 不一致"]


def run_offline_batch(
    manifest: dict[str, Any],
    adapters: dict[str, LegalRetrievalAdapter],
    cache: RetrievalMetadataCache,
    *,
    commit: bool = False,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """依 manifest 順序套用記憶體交易；全數成功後才可一次提交。"""
    errors = validate_offline_batch_manifest(manifest)
    if errors:
        raise OfflineBatchError(f"batch manifest 無效：{errors}")
    required_adapter_ids = {item["adapter_id"] for item in manifest["items"]}
    if set(adapters) != required_adapter_ids:
        raise OfflineBatchError("adapter mapping 必須與 manifest provider 集合完全一致")

    transaction = cache.transaction()
    staged_reports: list[dict[str, Any]] = []
    try:
        for item in manifest["items"]:
            before_hash = _canonical_hash(transaction.load())
            report = run_offline_sync(
                item["query"],
                adapters[item["adapter_id"]],
                transaction,
                commit=True,
                observed_at=observed_at,
            )
            would_mutate = before_hash != _canonical_hash(transaction.load())
            staged_reports.append(
                {
                    "item_id": item["item_id"],
                    **report,
                    "status": "STAGED",
                    "cache_mutated": False,
                    "would_mutate": would_mutate,
                }
            )
        if commit:
            cache_mutated = transaction.commit()
            status = "COMMITTED"
            item_status = "COMMITTED"
        else:
            transaction.discard()
            cache_mutated = False
            status = "DRY_RUN"
            item_status = "DRY_RUN"
    except Exception:
        transaction.discard()
        raise

    item_reports = [
        {**report, "status": item_status}
        for report in staged_reports
    ]
    return {
        "schema_version": BATCH_REPORT_VERSION,
        "batch_id": manifest["batch_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "status": status,
        "item_count": len(item_reports),
        "items": item_reports,
        "atomic_commit": True,
        "external_network": False,
        "cache_mutated": cache_mutated,
        "content_stored": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
