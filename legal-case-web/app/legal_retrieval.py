"""去識別法律檢索查詢與 review-only adapter。

本模組刻意不接受案情全文或任意查詢字串。查詢只能由既定 child route、
``fact_target`` 與有限狀態產生，因此案件姓名、地址、案號及自由文字沒有輸入
通道。離線 adapter 只讀 ``offense_linkage_poc.json``；外部 adapter 預設拒絕執行。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol, runtime_checkable

from .offense_linkage import (
    ALLOWED_OBSERVATION_STATUSES,
    load_pack,
    validate_pack,
)


QUERY_SCHEMA_VERSION = "legal-retrieval-query-v1"

ROUTE_SEARCH_TERMS = {
    "theft_320_1_movable": ("刑法第320條", "動產竊盜", "取得前持有狀態"),
    "aggravated_theft_321": ("刑法第321條", "加重竊盜", "法定加重事由"),
    "embezzlement_335_general": ("刑法第335條", "普通侵占", "原先持有關係"),
}

FACT_SEARCH_TERMS = {
    "object_status": "財物性質",
    "possession_before_taking": "取得前實際持有控制",
    "authorization_scope_status": "同意授權範圍",
    "post_acquisition_conduct": "取得後處理經過",
    "completed_or_attempted": "既遂未遂事實",
    "base_theft_facts": "基礎取得行為",
    "aggravation_presence": "法定加重事由",
    "aggravation_awareness": "對加重事由的認識",
    "prior_lawful_custody": "交付保管借用合法持有",
    "unlawful_possession_intent": "取得理由返還表示處分行為",
}

STATUS_SEARCH_TERMS = {
    "OBSERVED": "已有中性事實",
    "UNKNOWN": "事實不明",
    "CONFLICT": "陳述衝突",
    "NOT_FOUND": "尚未取得資料",
}


class RetrievalQueryError(ValueError):
    pass


class ExternalRetrievalNotAuthorized(RuntimeError):
    pass


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _allowed_fact_targets(pack: dict[str, Any], route_ids: set[str]) -> set[str]:
    return {
        fact_target
        for profile in pack.get("route_profiles", [])
        if profile.get("route_id") in route_ids
        for fact_target in profile.get("required_fact_targets", [])
    }


def build_deidentified_query(
    route_ids: list[str],
    observations: dict[str, str],
    *,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """以固定詞彙產生查詢；不接受或轉送任何案件自由文字。"""
    source_pack = pack if pack is not None else load_pack()
    errors = validate_pack(source_pack)
    if errors:
        raise RetrievalQueryError(f"offense linkage pack 無效：{errors}")

    if not isinstance(route_ids, list) or any(
        not isinstance(route_id, str) or not route_id for route_id in route_ids
    ):
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_ROUTE_FORMAT_INVALID：route_ids 格式錯誤"
        )
    if not isinstance(observations, dict) or any(
        not isinstance(fact_target, str) or not fact_target
        for fact_target in observations
    ):
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_FACT_TARGET_FORMAT_INVALID：fact_observations 格式錯誤"
        )

    selected_routes = sorted(set(route_ids))
    if not selected_routes or len(selected_routes) != len(route_ids):
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_ROUTE_CARDINALITY_INVALID：route_ids 不得為空或重複"
        )
    unsupported_routes = set(selected_routes) - set(ROUTE_SEARCH_TERMS)
    if unsupported_routes:
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_ROUTE_NOT_ALLOWED：含未核准的 route_ids"
        )

    allowed_targets = _allowed_fact_targets(source_pack, set(selected_routes))
    unknown_targets = set(observations) - allowed_targets
    if unknown_targets:
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_FACT_TARGET_NOT_ALLOWED：查詢不接受任意欄位或自由文字"
        )
    if any(status not in ALLOWED_OBSERVATION_STATUSES for status in observations.values()):
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_STATUS_NOT_ALLOWED：不支援的觀察狀態"
        )
    missing_term_mapping = set(observations) - set(FACT_SEARCH_TERMS)
    if missing_term_mapping:
        raise RetrievalQueryError(
            "RETRIEVAL_QUERY_SAFE_TERM_MAPPING_MISSING：fact_target 尚未建立安全詞彙映射"
        )

    terms: list[str] = []
    for route_id in selected_routes:
        terms.extend(ROUTE_SEARCH_TERMS[route_id])
    for fact_target, status in sorted(observations.items()):
        terms.extend((FACT_SEARCH_TERMS[fact_target], STATUS_SEARCH_TERMS[status]))
    terms = list(dict.fromkeys(terms))

    core = {
        "schema_version": QUERY_SCHEMA_VERSION,
        "route_ids": selected_routes,
        "fact_observations": dict(sorted(observations.items())),
        "query_terms": terms,
        "query_text": " ".join(terms),
        "allowed_source_types": ["statute", "judgment"],
        "contains_case_text": False,
        "privacy_status": "DEIDENTIFIED_BY_CONSTRUCTION",
        "runtime_enabled": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    query_hash = _canonical_hash(core)
    return {
        **core,
        "query_id": f"query:{query_hash[:16]}",
        "query_sha256": query_hash,
    }


def validate_deidentified_query(
    query: dict[str, Any], *, pack: dict[str, Any] | None = None
) -> list[str]:
    """重建固定查詢並比對全部欄位，防止呼叫端夾帶自由文字。"""
    try:
        expected = build_deidentified_query(
            list(query.get("route_ids", [])),
            dict(query.get("fact_observations", {})),
            pack=pack,
        )
    except (TypeError, ValueError, RetrievalQueryError) as exc:
        return [str(exc)]
    if query != expected:
        return ["查詢內容與固定去識別產生器不一致"]
    return []


@runtime_checkable
class LegalRetrievalAdapter(Protocol):
    adapter_id: str
    external_network: bool

    def search(self, query: dict[str, Any]) -> dict[str, Any]: ...


class OfflineLinkageAdapter:
    """只回傳 PoC 已登錄且與查詢 route／fact 有關的來源 metadata。"""

    adapter_id = "offline-linkage-poc-v1"
    external_network = False

    def __init__(self, pack: dict[str, Any] | None = None) -> None:
        self.pack = pack if pack is not None else load_pack()
        errors = validate_pack(self.pack)
        if errors:
            raise RetrievalQueryError(f"offense linkage pack 無效：{errors}")

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        errors = validate_deidentified_query(query, pack=self.pack)
        if errors:
            raise RetrievalQueryError(f"去識別查詢無效：{errors}")

        selected_routes = set(query["route_ids"])
        selected_facts = set(query["fact_observations"])
        matched_relations = [
            relation
            for relation in self.pack.get("relations", [])
            if (
                relation.get("subject_route_id") in selected_routes
                or relation.get("object_route_id") in selected_routes
            )
            and (
                not selected_facts
                or relation.get("fact_target") in selected_facts
                or relation.get("object_fact_target") in selected_facts
            )
        ]
        matched_source_ids = {
            source_id
            for relation in matched_relations
            for source_id in relation.get("source_ids", [])
        }
        allowed_types = set(query["allowed_source_types"])
        sources = {
            source["source_id"]: source
            for source in self.pack.get("sources", [])
            if source["source_id"] in matched_source_ids
            and source.get("source_type") in allowed_types
        }
        hits = [
            {
                "source_id": source_id,
                "source_type": source["source_type"],
                "authority": source["authority"],
                "title": source["title"],
                "canonical_url": source["canonical_url"],
                "document_date": source["document_date"],
                "content_sha256": source["content_sha256"],
                "hash_scope": "REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT",
                "relation_ids": sorted(
                    relation["relation_id"]
                    for relation in matched_relations
                    if source_id in relation.get("source_ids", [])
                ),
                "legal_conclusion": False,
                "review_status": "HUMAN_REVIEW_REQUIRED",
            }
            for source_id, source in sorted(sources.items())
        ]
        return {
            "adapter_id": self.adapter_id,
            "external_network": self.external_network,
            "query_id": query["query_id"],
            "hits": hits,
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }


class DisabledExternalAdapter:
    """外部 MCP／PSUE 尚未授權時的明確 fail-closed adapter。"""

    adapter_id = "external-disabled-v1"
    external_network = True

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        errors = validate_deidentified_query(query)
        if errors:
            raise RetrievalQueryError(f"去識別查詢無效：{errors}")
        raise ExternalRetrievalNotAuthorized(
            "外部法律檢索尚未取得 Human Gate；不得傳送查詢或案件資料。"
        )
