"""官方來源移除事件與本機 metadata cache 的離線 reconciliation。"""

from __future__ import annotations

import hashlib
from typing import Any

from .legal_provider_fixtures import SourceRemovalRequired
from .legal_retrieval import load_pack
from .legal_retrieval_cache import RetrievalMetadataCache
from .offense_linkage import validate_pack


PROVIDER_LOCATOR_KEYS = {
    "fixture-judicial-open-data-jdoc-v1": "judicial_jid",
}


class RemovalReconciliationError(RuntimeError):
    pass


def resolve_source_removal(
    removal: SourceRemovalRequired,
    *,
    pack: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """將 provider locator 精確映射為 source_id 與去識別 locator hash。"""
    active_pack = pack if pack is not None else load_pack()
    errors = validate_pack(active_pack)
    if errors:
        raise RemovalReconciliationError(f"offense linkage pack 無效：{errors}")
    locator_key = PROVIDER_LOCATOR_KEYS.get(removal.provider_id)
    if locator_key is None:
        raise RemovalReconciliationError(f"不支援的來源移除 provider：{removal.provider_id}")
    matches = [
        source
        for source in active_pack.get("sources", [])
        if source.get("provider_locators", {}).get(locator_key) == removal.source_locator
    ]
    if len(matches) != 1:
        raise RemovalReconciliationError(
            f"來源 locator 必須精確映射一筆 registry source；實際為 {len(matches)} 筆"
        )
    locator_hash = hashlib.sha256(removal.source_locator.encode("utf-8")).hexdigest()
    return matches[0]["source_id"], locator_hash


def preview_source_removal(
    cache: RetrievalMetadataCache,
    removal: SourceRemovalRequired,
    *,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """建立不寫檔的去識別移除計畫。"""
    source_id, locator_hash = resolve_source_removal(removal, pack=pack)
    payload = cache.load()
    affected_keys: list[str] = []
    removed_count = 0
    for key, response in payload["entries"].items():
        count = sum(record["source_id"] == source_id for record in response["records"])
        if count:
            affected_keys.append(key)
            removed_count += count
    return {
        "provider_id": removal.provider_id,
        "source_id": source_id,
        "source_locator_sha256": locator_hash,
        "affected_cache_keys": sorted(affected_keys),
        "removed_record_count": removed_count,
        "projected_status": "REMOVED" if removed_count else "TOMBSTONED_NOT_PRESENT",
    }


def reconcile_source_removal(
    cache: RetrievalMetadataCache,
    removal: SourceRemovalRequired,
    *,
    observed_at: str,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """以 registry 精確映射 locator，原子移除 cache metadata 並留下 tombstone。"""
    source_id, locator_hash = resolve_source_removal(removal, pack=pack)
    return cache.evict_source(
        source_id=source_id,
        provider_id=removal.provider_id,
        source_locator_sha256=locator_hash,
        observed_at=observed_at,
    )
