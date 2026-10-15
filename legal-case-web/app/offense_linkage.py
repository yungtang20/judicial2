"""離線罪章關聯 PoC。

本模組只驗證及投影 ``data/offense_linkage_poc.json``。它不接入 Gate 2、
不產生罪名結論，也不依觀察資料計算有罪機率。正式 runtime 若要使用此資料，
仍須另經 Human Gate 與接線驗證。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PACK_PATH = Path(__file__).resolve().parents[1] / "data" / "offense_linkage_poc.json"
CROSSWALK_PATH = Path(__file__).resolve().parents[1] / "data" / "legal_route_crosswalk.json"

ALLOWED_SOURCE_TYPES = {"statute", "judgment", "official_guidance"}
ALLOWED_RELATION_TYPES = {"DISTINGUISHED_FROM", "AGGRAVATES", "REQUIRES_FACT"}
ALLOWED_OBSERVATION_STATUSES = {"OBSERVED", "UNKNOWN", "CONFLICT", "NOT_FOUND"}


def fingerprint(text: str) -> str:
    """回傳 PoC 內正規化文字的 SHA-256。"""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def load_pack(path: Path = PACK_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_crosswalk_route_ids(path: Path = CROSSWALK_PATH) -> set[str]:
    crosswalk = json.loads(path.read_text(encoding="utf-8"))
    return {
        child["id"]
        for parent in crosswalk.get("routes", [])
        for child in parent.get("child_routes", [])
    }


def validate_pack(
    pack: dict[str, Any], *, known_route_ids: set[str] | None = None
) -> list[str]:
    """驗證來源、關聯、hash 與 fail-closed 邊界；回傳所有錯誤。"""
    errors: list[str] = []
    known_routes = known_route_ids if known_route_ids is not None else load_crosswalk_route_ids()

    if pack.get("runtime_enabled") is not False:
        errors.append("runtime_enabled 必須為 false")
    if pack.get("legal_conclusion") is not False:
        errors.append("legal_conclusion 必須為 false")
    if pack.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        errors.append("review_status 必須為 HUMAN_REVIEW_REQUIRED")

    source_ids: set[str] = set()
    for source in pack.get("sources", []):
        source_id = source.get("source_id", "")
        if not source_id or source_id in source_ids:
            errors.append(f"來源 ID 缺漏或重複：{source_id!r}")
        source_ids.add(source_id)
        if source.get("source_type") not in ALLOWED_SOURCE_TYPES:
            errors.append(f"{source_id}: 不支援的 source_type")
        if not str(source.get("canonical_url", "")).startswith("https://"):
            errors.append(f"{source_id}: canonical_url 必須使用 https")
        text = str(source.get("fingerprinted_text", ""))
        if not text or source.get("content_sha256") != fingerprint(text):
            errors.append(f"{source_id}: content_sha256 不符")

    profiles = pack.get("route_profiles", [])
    profile_ids = {profile.get("route_id", "") for profile in profiles}
    for route_id in profile_ids:
        if route_id not in known_routes:
            errors.append(f"未知 child route：{route_id}")
    if "prosecution_document" in {s.get("source_type") for s in pack.get("sources", [])}:
        errors.append("PoC 尚未核准匯入起訴書")
    if pack.get("ingestion_status", {}).get("prosecution_documents") != "NOT_INGESTED":
        errors.append("prosecution_documents 必須維持 NOT_INGESTED")

    relation_ids: set[str] = set()
    for relation in pack.get("relations", []):
        relation_id = relation.get("relation_id", "")
        if not relation_id or relation_id in relation_ids:
            errors.append(f"關聯 ID 缺漏或重複：{relation_id!r}")
        relation_ids.add(relation_id)
        if relation.get("relation_type") not in ALLOWED_RELATION_TYPES:
            errors.append(f"{relation_id}: 不支援的 relation_type")
        if relation.get("subject_route_id") not in profile_ids:
            errors.append(f"{relation_id}: subject route 不在 PoC scope")
        object_route = relation.get("object_route_id")
        object_fact = relation.get("object_fact_target")
        if bool(object_route) == bool(object_fact):
            errors.append(f"{relation_id}: 必須且只能指定 route 或 fact target")
        if object_route and object_route not in profile_ids:
            errors.append(f"{relation_id}: object route 不在 PoC scope")
        refs = relation.get("source_ids", [])
        if not refs or any(ref not in source_ids for ref in refs):
            errors.append(f"{relation_id}: 缺少有效來源")
        proposition = str(relation.get("proposition", ""))
        if not proposition or relation.get("evidence_sha256") != fingerprint(proposition):
            errors.append(f"{relation_id}: evidence_sha256 不符")
        if relation.get("review_status") != "HUMAN_REVIEW_REQUIRED":
            errors.append(f"{relation_id}: 必須保留人工審查")
        if relation.get("legal_conclusion") is not False:
            errors.append(f"{relation_id}: 不得產生法律結論")

    for axis in pack.get("question_axes", []):
        axis_id = axis.get("axis_id", "")
        if not axis.get("fact_target") or not axis.get("neutral_prompt"):
            errors.append(f"{axis_id}: 缺少 fact target 或中性問句")
        refs = axis.get("relation_ids", [])
        if not refs or any(ref not in relation_ids for ref in refs):
            errors.append(f"{axis_id}: 缺少有效 relation_ids")
        if axis.get("runtime_enabled") is not False:
            errors.append(f"{axis_id}: runtime_enabled 必須為 false")

    return errors


def build_review_matrix(
    pack: dict[str, Any], observations: dict[str, str]
) -> dict[str, Any]:
    """把人工提供的事實狀態投影成逐 route 覆蓋表，不作法律評價。"""
    invalid = {
        key: status
        for key, status in observations.items()
        if status not in ALLOWED_OBSERVATION_STATUSES
    }
    if invalid:
        raise ValueError(f"不支援的觀察狀態：{invalid}")

    routes: list[dict[str, Any]] = []
    for profile in pack.get("route_profiles", []):
        elements = [
            {
                "fact_target": fact_target,
                "status": observations.get(fact_target, "UNKNOWN"),
            }
            for fact_target in profile.get("required_fact_targets", [])
        ]
        routes.append(
            {
                "route_id": profile["route_id"],
                "elements": elements,
                "missing_fact_targets": [
                    item["fact_target"]
                    for item in elements
                    if item["status"] in {"UNKNOWN", "NOT_FOUND", "CONFLICT"}
                ],
                "legal_conclusion": False,
                "review_status": "HUMAN_REVIEW_REQUIRED",
            }
        )
    return {
        "schema_version": pack.get("schema_version"),
        "routes": routes,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
