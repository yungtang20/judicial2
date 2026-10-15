"""法律來源的離線 fixture adapters。

這些 adapter 只解析測試 fixture，不發出網路請求。只有已有公開 schema 或原始碼
證據的 provider 可以解析結果；Taiwan Law MCP 與 PSUE 因缺少足夠 response/API
契約而維持 discovery-only。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .legal_retrieval import RetrievalQueryError, load_pack, validate_deidentified_query
from .offense_linkage import validate_pack


JID_PATTERN = re.compile(r"^[A-Z]{2,6},\d+,[^,]+,[0-9A-Za-z-]+,\d{8},\d+$")


class FixtureContractError(ValueError):
    pass


class ProviderContractNotAvailable(RuntimeError):
    pass


class SourceRemovalRequired(RuntimeError):
    def __init__(self, provider_id: str, source_locator: str) -> None:
        super().__init__(f"{provider_id} 回報來源已移除；必須清除既有快取：{source_locator}")
        self.provider_id = provider_id
        self.source_locator = source_locator


def _validate_query(query: dict[str, Any]) -> None:
    errors = validate_deidentified_query(query)
    if errors:
        raise RetrievalQueryError(f"去識別查詢無效：{errors}")


class _RegistryBackedFixtureAdapter:
    external_network = False

    def __init__(self, fixture: dict[str, Any], pack: dict[str, Any] | None = None) -> None:
        self.fixture = fixture
        self.pack = pack if pack is not None else load_pack()
        errors = validate_pack(self.pack)
        if errors:
            raise FixtureContractError(f"offense linkage pack 無效：{errors}")

    def _source_by_jid(self, jid: str) -> dict[str, Any] | None:
        return next(
            (
                source
                for source in self.pack.get("sources", [])
                if source.get("provider_locators", {}).get("judicial_jid") == jid
            ),
            None,
        )

    def _relation_ids(self, source_id: str, query: dict[str, Any]) -> list[str]:
        routes = set(query["route_ids"])
        facts = set(query["fact_observations"])
        return sorted(
            relation["relation_id"]
            for relation in self.pack.get("relations", [])
            if source_id in relation.get("source_ids", [])
            and (
                relation.get("subject_route_id") in routes
                or relation.get("object_route_id") in routes
            )
            and (
                not facts
                or relation.get("fact_target") in facts
                or relation.get("object_fact_target") in facts
            )
        )

    def _hit(
        self,
        source: dict[str, Any],
        query: dict[str, Any],
        *,
        content_sha256: str | None = None,
        hash_scope: str = "REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT",
    ) -> dict[str, Any] | None:
        relation_ids = self._relation_ids(source["source_id"], query)
        if not relation_ids or source.get("source_type") not in query["allowed_source_types"]:
            return None
        return {
            "source_id": source["source_id"],
            "source_type": source["source_type"],
            "authority": source["authority"],
            "title": source["title"],
            "canonical_url": source["canonical_url"],
            "document_date": source["document_date"],
            "content_sha256": content_sha256 or source["content_sha256"],
            "hash_scope": hash_scope,
            "relation_ids": relation_ids,
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }

    def _result(self, query: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "external_network": False,
            "query_id": query["query_id"],
            "hits": sorted(hits, key=lambda hit: hit["source_id"]),
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }


class TaiwanLegalDbFixtureAdapter(_RegistryBackedFixtureAdapter):
    """解析 mcp-taiwan-legal-db ``search_judgments`` 的離線結果。"""

    adapter_id = "fixture-mcp-taiwan-legal-db-v1"

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        _validate_query(query)
        if self.fixture.get("success") is not True:
            raise FixtureContractError("mcp-taiwan-legal-db fixture success 必須為 true")
        results = self.fixture.get("results")
        if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
            raise FixtureContractError("mcp-taiwan-legal-db results 格式錯誤")
        hits: list[dict[str, Any]] = []
        for item in results:
            jid = item.get("jid")
            if not isinstance(jid, str) or not JID_PATTERN.fullmatch(jid):
                raise FixtureContractError("mcp-taiwan-legal-db jid 格式錯誤")
            source = self._source_by_jid(jid)
            if source:
                hit = self._hit(source, query)
                if hit:
                    hits.append(hit)
        return self._result(query, hits)


class TlrAnchorFixtureAdapter(_RegistryBackedFixtureAdapter):
    """解析 TLR anchor bundle；只有 allowed_citations 可成為 hit。"""

    adapter_id = "fixture-tlr-anchor-v1"

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        _validate_query(query)
        allowed = self.fixture.get("allowed_citations")
        judgments = self.fixture.get("judgments")
        unread = self.fixture.get("unread_candidates", [])
        if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
            raise FixtureContractError("TLR allowed_citations 格式錯誤")
        if not isinstance(judgments, list) or any(not isinstance(item, dict) for item in judgments):
            raise FixtureContractError("TLR judgments 格式錯誤")
        if not isinstance(unread, list):
            raise FixtureContractError("TLR unread_candidates 格式錯誤")
        unread_ids = {
            item.get("citation_id")
            for item in unread
            if isinstance(item, dict) and isinstance(item.get("citation_id"), str)
        }
        hits: list[dict[str, Any]] = []
        for item in judgments:
            citation_id = item.get("citation_id")
            jid = item.get("jid")
            if citation_id not in allowed or citation_id in unread_ids:
                continue
            if item.get("fulltext_available") is not True:
                continue
            if not isinstance(jid, str) or not JID_PATTERN.fullmatch(jid):
                raise FixtureContractError("TLR judgment jid 格式錯誤")
            source = self._source_by_jid(jid)
            if source:
                hit = self._hit(source, query)
                if hit:
                    hits.append(hit)
        return self._result(query, hits)


class JudicialOpenDataFixtureAdapter(_RegistryBackedFixtureAdapter):
    """解析司法院 JDoc fixture；只輸出全文 hash，不保存 JFULLCONTENT。"""

    adapter_id = "fixture-judicial-open-data-jdoc-v1"

    def __init__(
        self,
        fixture: dict[str, Any],
        *,
        requested_jid: str,
        pack: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(fixture, pack)
        self.requested_jid = requested_jid

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        _validate_query(query)
        if "error" in self.fixture:
            raise SourceRemovalRequired(self.adapter_id, self.requested_jid)
        jid = self.fixture.get("JID")
        if jid != self.requested_jid or not isinstance(jid, str) or not JID_PATTERN.fullmatch(jid):
            raise FixtureContractError("司法院 JDoc JID 不一致或格式錯誤")
        jid_date = jid.split(",")[4]
        if self.fixture.get("JDATE") != jid_date:
            raise FixtureContractError("司法院 JDoc JDATE 與 JID 不一致")
        full = self.fixture.get("JFULLX")
        if not isinstance(full, dict) or full.get("JFULLTYPE") not in {"text", "file"}:
            raise FixtureContractError("司法院 JFULLX 格式錯誤")
        content = full.get("JFULLCONTENT")
        if not isinstance(content, str) or not content.strip():
            raise FixtureContractError("司法院 JFULLCONTENT 缺漏")
        source = self._source_by_jid(jid)
        hits: list[dict[str, Any]] = []
        if source:
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            hit = self._hit(
                source,
                query,
                content_sha256=content_hash,
                hash_scope="FULL_PUBLIC_DOCUMENT",
            )
            if hit:
                hits.append(hit)
        return self._result(query, hits)


class DiscoveryOnlyFixtureAdapter:
    """公開能力存在但 response/API schema 證據不足時的 fail-closed adapter。"""

    external_network = False

    def __init__(self, provider_id: str, reason: str) -> None:
        self.adapter_id = f"fixture-{provider_id}-discovery-only"
        self.reason = reason

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        _validate_query(query)
        raise ProviderContractNotAvailable(
            f"{self.adapter_id} 尚無足夠公開 response/API schema：{self.reason}"
        )


def taiwan_law_mcp_discovery_adapter() -> DiscoveryOnlyFixtureAdapter:
    return DiscoveryOnlyFixtureAdapter(
        "taiwan-law-mcp",
        "公開頁面列出工具與 Streamable HTTP endpoint，但未提供本 PoC 可固定的回應欄位契約。",
    )


def psue_discovery_adapter() -> DiscoveryOnlyFixtureAdapter:
    return DiscoveryOnlyFixtureAdapter(
        "psue",
        "公開書類系統未提供本 PoC 可驗證的公開 API response schema，且起訴書仍為 NOT_INGESTED。",
    )
