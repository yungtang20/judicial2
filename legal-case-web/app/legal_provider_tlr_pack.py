"""TLR ``pack`` bundle 的離線契約層（2026-10-22 新增）。

背景：``docs/HG_LR_01_PROVIDER_REVIEW.md`` 把 TLR hosted 列為
``CONDITIONAL_CITATION_RETRIEVAL_CANDIDATE``，而 ``app/legal_provider_fixtures.py``
已有 ``fixture-tlr-anchor-v1`` 解析 anchor bundle；本模組補上 ``twlegalrag pack``
（``schema = twlegalrag.bundle/v1``）的契約，讓判決字號可以回到已登錄的
offense linkage 來源，而不是只停在 ``needs_external``。

邊界（刻意設計）：
- 本模組的 adapter 只解析**已凍結的 fixture**，``external_network = False``。
- bundle 的 ``query`` 必須等於去識別查詢產生器的 ``query_text``，否則拒絕：
  防止把別的查詢結果貼進來當成本案證據。
- 只輸出 citation metadata 與摘錄 hash；``listing``、``hit_excerpt``、
  ``fulltext_excerpt`` 一律不得離開本模組（隱私與檔案大小）。
- ``fulltext_truncated`` 為真時不得當成可引用的全文，直接跳過。
- JID 不在 offense linkage registry 時不得自行編造 ``source_id``，記為
  ``UNREGISTERED_JID`` 並跳過。
- live 呼叫（``TlrPackCliClient``）只有在 Human Gate 封包的
  ``decision_status`` 為 ``APPROVED`` 時才能建立；目前封包為
  ``PENDING_HUMAN_APPROVAL``，因此在正式環境一律建構失敗。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .legal_provider_fixtures import (
    JID_PATTERN,
    TlrAnchorFixtureAdapter,
    _RegistryBackedFixtureAdapter,
    _validate_query,
)
from .offense_linkage import validate_pack

TLR_PACK_SCHEMA = "twlegalrag.bundle/v1"
CITATION_ID_PATTERN = re.compile(r"^J(?:[1-9]|10)$")
MAX_JUDGMENTS = 10
PACK_TEXT_FIELDS = ("listing", "hit_excerpt", "fulltext_excerpt")
GATE_PACKET_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "evidence"
    / "legal_retrieval_human_gate_packet.json"
)
CLI_TIMEOUT_SECONDS = 90


class TlrBundleContractError(ValueError):
    """bundle 不符合已凍結的 schema 或內部一致性規則。"""


class TlrBundleQueryMismatch(RuntimeError):
    """bundle 不是由本次去識別查詢產生。"""


class TlrPackNotAuthorized(RuntimeError):
    """Human Gate 未核准，不得發出 live 呼叫。"""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _excerpt_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_pack_bundle(bundle: dict[str, Any], *, query: dict[str, Any]) -> list[str]:
    """回傳契約錯誤清單；空清單代表 bundle 可用。

    只檢查結構與內部一致性，不判斷判決內容是否支持任何法律命題。
    """

    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle 必須是物件"]
    if bundle.get("schema") != TLR_PACK_SCHEMA:
        errors.append(f"schema 必須為 {TLR_PACK_SCHEMA}")
    if bundle.get("retrieval_only") is not True:
        errors.append("retrieval_only 必須為 true")
    if not isinstance(bundle.get("source"), str) or not bundle["source"].strip():
        errors.append("source 必須為非空字串")
    if bundle.get("query") != query.get("query_text"):
        raise TlrBundleQueryMismatch(
            "bundle.query 與本次去識別查詢不一致；不得把其他查詢的結果當成本案證據"
        )

    allowed = bundle.get("allowed_citations")
    if not isinstance(allowed, list) or not allowed:
        errors.append("allowed_citations 必須為非空清單")
        allowed = []
    elif len(allowed) > MAX_JUDGMENTS:
        errors.append(f"allowed_citations 不得超過 {MAX_JUDGMENTS} 筆")
    if len(set(allowed)) != len(allowed):
        errors.append("allowed_citations 不得重複")
    errors.extend(
        f"citation_id 格式錯誤：{item!r}"
        for item in allowed
        if not isinstance(item, str) or not CITATION_ID_PATTERN.fullmatch(item)
    )

    judgments = bundle.get("judgments")
    if not isinstance(judgments, list) or not judgments:
        errors.append("judgments 必須為非空清單")
        judgments = []
    elif len(judgments) > MAX_JUDGMENTS:
        errors.append(f"judgments 不得超過 {MAX_JUDGMENTS} 筆")

    seen: set[str] = set()
    for index, item in enumerate(judgments):
        where = f"judgments[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} 必須是物件")
            continue
        citation_id = item.get("citation_id")
        if citation_id not in allowed:
            errors.append(f"{where}.citation_id 不在 allowed_citations 內")
        elif citation_id in seen:
            errors.append(f"{where}.citation_id 重複")
        seen.add(citation_id if isinstance(citation_id, str) else "")
        doc_id = item.get("doc_id")
        if not isinstance(doc_id, str) or not JID_PATTERN.fullmatch(doc_id):
            errors.append(f"{where}.doc_id 不是合法 JID")
            continue
        jdate = item.get("jdate")
        if not isinstance(jdate, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", jdate):
            errors.append(f"{where}.jdate 格式錯誤")
        elif jdate.replace("-", "") != doc_id.split(",")[4]:
            errors.append(f"{where}.jdate 與 doc_id 日期不一致")
        if not isinstance(item.get("citation_text"), str):
            errors.append(f"{where}.citation_text 必須是字串")
        if item.get("case_category") != "刑事":
            errors.append(f"{where}.case_category 必須為刑事")
        if not isinstance(item.get("citation_url"), str):
            errors.append(f"{where}.citation_url 必須是字串")
        cited = item.get("cited_articles")
        if not isinstance(cited, list) or any(not isinstance(x, str) for x in cited):
            errors.append(f"{where}.cited_articles 必須是字串清單")
        if not isinstance(item.get("fulltext_truncated"), bool):
            errors.append(f"{where}.fulltext_truncated 必須是布林值")
        if not isinstance(item.get("fulltext_excerpt"), str):
            errors.append(f"{where}.fulltext_excerpt 必須是字串")

    missing_judgments = sorted(set(allowed) - seen)
    if missing_judgments:
        errors.append(f"allowed_citations 缺少對應 judgment：{missing_judgments}")

    instructions = bundle.get("verification_instructions")
    if not isinstance(instructions, dict):
        errors.append("verification_instructions 必須是物件")
    else:
        if instructions.get("required") is not True:
            errors.append("verification_instructions.required 必須為 true")
        rules = instructions.get("rules")
        if not isinstance(rules, list) or not rules:
            errors.append("verification_instructions.rules 必須為非空清單")
        elif any(not isinstance(rule, str) or not rule.strip() for rule in rules):
            errors.append("verification_instructions.rules 含非字串項目")
    return errors


def summarize_pack_bundle(bundle: dict[str, Any], *, query: dict[str, Any]) -> dict[str, Any]:
    """產生不含判決文字的可保存摘要，供證據與 replay 使用。"""

    errors = validate_pack_bundle(bundle, query=query)
    if errors:
        raise TlrBundleContractError("；".join(errors))
    sanitized = {
        "schema": bundle["schema"],
        "source": bundle["source"],
        "retrieval_only": True,
        "query": bundle["query"],
        "allowed_citations": list(bundle["allowed_citations"]),
        "judgments": [
            {
                key: item.get(key)
                for key in (
                    "citation_id",
                    "doc_id",
                    "citation_text",
                    "citation_url",
                    "court_name",
                    "jdate",
                    "case_category",
                    "cited_articles",
                    "fulltext_truncated",
                    "fulltext_total_chars",
                )
            }
            for item in bundle["judgments"]
        ],
        "verification_required": bundle["verification_instructions"]["required"],
    }
    return {
        "bundle_sha256": _canonical_sha256(sanitized),
        "schema": bundle["schema"],
        "source": bundle["source"],
        "query_sha256": _canonical_sha256({"query": bundle["query"]}),
        "allowed_citations": list(bundle["allowed_citations"]),
        "judgment_count": len(bundle["judgments"]),
        "verification_required": True,
        "contains_excerpt_text": False,
    }


class TlrPackFixtureAdapter(_RegistryBackedFixtureAdapter):
    """解析已凍結的 ``twlegalrag pack`` bundle，對應回 registry 來源。

    沿用 ``TlrAnchorFixtureAdapter`` 的相同立場：只有 ``allowed_citations``
    內、全文未截斷、且能對應到已登錄 JID 的判決，才能成為 hit。
    """

    adapter_id = "fixture-tlr-pack-v1"
    external_network = False

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        _validate_query(query)
        summary = summarize_pack_bundle(self.fixture, query=query)
        hits: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for item in self.fixture["judgments"]:
            citation_id = item["citation_id"]
            if item["fulltext_truncated"]:
                skipped.append({"citation_id": citation_id, "reason": "TRUNCATED_FULLTEXT"})
                continue
            source = self._source_by_jid(item["doc_id"])
            if source is None:
                skipped.append({"citation_id": citation_id, "reason": "UNREGISTERED_JID"})
                continue
            relation_ids = self._relation_ids(source["source_id"], query)
            if not relation_ids or source.get("source_type") not in query["allowed_source_types"]:
                skipped.append({"citation_id": citation_id, "reason": "NO_RELATION_COVERAGE"})
                continue
            hits.append(
                {
                    "source_id": source["source_id"],
                    "source_type": source["source_type"],
                    "authority": source["authority"],
                    "title": source["title"],
                    "canonical_url": source["canonical_url"],
                    "document_date": source["document_date"],
                    "content_sha256": _excerpt_sha256(item["fulltext_excerpt"]),
                    "hash_scope": "RETRIEVED_EXCERPT_SHA256_NOT_FULL_DOCUMENT",
                    "relation_ids": relation_ids,
                    "citation_id": citation_id,
                    "citation_text": item["citation_text"],
                    "citation_url": item["citation_url"],
                    "judicial_jid": item["doc_id"],
                    "case_category": item["case_category"],
                    "legal_conclusion": False,
                    "review_status": "HUMAN_REVIEW_REQUIRED",
                }
            )
        return {
            "adapter_id": self.adapter_id,
            "external_network": False,
            "query_id": query["query_id"],
            "bundle": summary,
            "hits": sorted(hits, key=lambda hit: hit["source_id"]),
            "skipped": sorted(skipped, key=lambda item: item["citation_id"]),
            "legal_conclusion": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }


def load_pack_fixture(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_fixture_adapter(
    path: str | Path, *, pack: dict[str, Any] | None = None
) -> TlrPackFixtureAdapter:
    """建立離線 adapter；registry pack 無效時立即失敗。"""

    adapter = TlrPackFixtureAdapter(load_pack_fixture(path), pack=pack)
    errors = validate_pack(adapter.pack)
    if errors:
        raise TlrBundleContractError(f"offense linkage pack 無效：{errors}")
    return adapter


def live_call_authorization(packet: dict[str, Any] | None = None) -> tuple[bool, str]:
    """檢查 Human Gate 封包是否允許 live 呼叫。

    這不是核准判斷，只是把封包的 ``decision_status`` 忠實轉成 fail-closed
    結果；本函式不得被用來自動核准任何 Gate。
    """

    if packet is None:
        try:
            packet = json.loads(GATE_PACKET_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"無法讀取 Human Gate 封包：{exc}"
    status = str(packet.get("decision_status", ""))
    if status != "APPROVED":
        return False, (
            "HG-LR-01／HG-LR-02 尚未核准（封包 decision_status="
            f"{status or 'UNKNOWN'}）；不得對 TLR 發出 live 查詢"
        )
    return True, "APPROVED"


class TlrPackCliClient:
    """受 Human Gate 約束的 ``twlegalrag pack`` 客戶端。

    建構時即檢查封包；未核准就無法取得實例。``dry_run`` 只回傳 argv，
    不執行任何外部程式，供測試與審查核對送出的內容。
    """

    adapter_id = "tlr-pack-cli-v1"
    external_network = True

    def __init__(
        self, *, packet: dict[str, Any] | None = None, timeout: int = CLI_TIMEOUT_SECONDS
    ) -> None:
        authorized, reason = live_call_authorization(packet)
        if not authorized:
            raise TlrPackNotAuthorized(reason)
        self.timeout = timeout

    def dry_run(self, query: dict[str, Any], *, limit: int = 5) -> list[str]:
        _validate_query(query)
        if not 1 <= limit <= MAX_JUDGMENTS:
            raise TlrBundleContractError(f"limit 必須介於 1 與 {MAX_JUDGMENTS}")
        return ["twlegalrag", "pack", query["query_text"], "--n", str(limit)]

    def fetch(self, query: dict[str, Any], *, limit: int = 5) -> dict[str, Any]:
        argv = self.dry_run(query, limit=limit)
        completed = subprocess.run(
            argv, capture_output=True, timeout=self.timeout, check=False
        )
        if completed.returncode != 0:
            raise TlrBundleContractError(
                "twlegalrag pack 失敗：" + completed.stderr.decode("utf-8", "replace")[:400]
            )
        bundle = json.loads(completed.stdout.decode("utf-8"))
        errors = validate_pack_bundle(bundle, query=query)
        if errors:
            raise TlrBundleContractError("；".join(errors))
        return bundle


# 明確標示兩個既有 fixture adapter 的關係，避免被誤用。
ANCHOR_FIXTURE_ADAPTER = TlrAnchorFixtureAdapter
