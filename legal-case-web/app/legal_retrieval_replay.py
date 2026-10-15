"""離線法律來源 golden fixture replay 與去識別驗收證據。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .legal_provider_fixtures import (
    JID_PATTERN,
    JudicialOpenDataFixtureAdapter,
    TaiwanLegalDbFixtureAdapter,
)
from .legal_retrieval import build_deidentified_query
from .legal_retrieval_batch import build_offline_batch_manifest, run_offline_batch
from .legal_retrieval_cache import RetrievalMetadataCache


REPLAY_CORPUS_VERSION = "legal-retrieval-golden-replay-corpus-v1"
REPLAY_REPORT_VERSION = "legal-retrieval-golden-replay-report-v1"
SCENARIO_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
MAX_SCENARIOS = 32
MAX_OPERATIONS_PER_SCENARIO = 8
ALLOWED_PROVIDERS = {"mcp_taiwan_legal_db", "judicial_jdoc"}
ALLOWED_ERROR_TYPES = {
    "FixtureContractError",
    "RetrievalCacheIntegrityError",
    "OfflineSyncError",
    "OfflineBatchError",
}
FORBIDDEN_FIXTURE_KEYS = {
    "name",
    "address",
    "case_payload",
    "personal_data",
    "content",
    "JFULLCONTENT",
    "excerpt",
    "summary",
}
EXPECTED_PROJECTION_KEYS = {
    "result_kind",
    "batch_status",
    "item_operations",
    "cache_exists",
    "entry_count",
    "audit_count",
    "record_count",
    "error_type",
}


class ReplayCorpusError(RuntimeError):
    pass


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(set(value) & FORBIDDEN_FIXTURE_KEYS)
        for child in value.values():
            found.update(_find_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_find_forbidden_keys(child))
    return found


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.isoformat().endswith("+00:00")


def load_replay_corpus(path: Path) -> dict[str, Any]:
    try:
        corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayCorpusError("無法讀取 golden replay corpus") from exc
    errors = validate_replay_corpus(corpus)
    if errors:
        raise ReplayCorpusError(f"golden replay corpus 無效：{errors}")
    return corpus


def validate_replay_corpus(corpus: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(corpus, dict) or set(corpus) != {
        "schema_version",
        "generated_for",
        "contains_case_data",
        "scenarios",
    }:
        return ["corpus 欄位集合不符"]
    if corpus.get("schema_version") != REPLAY_CORPUS_VERSION:
        errors.append("corpus schema 不符")
    if corpus.get("generated_for") != "OFFLINE_FIXTURE_REPLAY_ONLY":
        errors.append("corpus generated_for 不符")
    if corpus.get("contains_case_data") is not False:
        errors.append("corpus 不得包含案件資料")
    scenarios = corpus.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= MAX_SCENARIOS:
        return errors + ["corpus scenarios 數量錯誤"]
    scenario_ids: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {
            "scenario_id",
            "description",
            "route_ids",
            "observations",
            "operations",
            "commit",
            "observed_at",
            "expected",
        }:
            errors.append("scenario 欄位集合不符")
            continue
        scenario_id = scenario.get("scenario_id")
        if (
            not isinstance(scenario_id, str)
            or not SCENARIO_ID_PATTERN.fullmatch(scenario_id)
            or scenario_id in scenario_ids
        ):
            errors.append(f"scenario_id 無效或重複：{scenario_id!r}")
        else:
            scenario_ids.add(scenario_id)
        if not isinstance(scenario.get("description"), str) or not scenario["description"]:
            errors.append(f"{scenario_id}: description 缺漏")
        try:
            build_deidentified_query(scenario["route_ids"], scenario["observations"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{scenario_id}: query 設定無效：{exc}")
        operations = scenario.get("operations")
        if not isinstance(operations, list) or not 1 <= len(operations) <= MAX_OPERATIONS_PER_SCENARIO:
            errors.append(f"{scenario_id}: operations 數量錯誤")
            continue
        providers: set[str] = set()
        for operation in operations:
            if not isinstance(operation, dict) or set(operation) != {
                "provider",
                "fixture",
                "requested_jid",
            }:
                errors.append(f"{scenario_id}: operation 欄位集合不符")
                continue
            provider = operation.get("provider")
            if provider not in ALLOWED_PROVIDERS or provider in providers:
                errors.append(f"{scenario_id}: provider 不支援或重複：{provider!r}")
            else:
                providers.add(provider)
            fixture = operation.get("fixture")
            if not isinstance(fixture, dict):
                errors.append(f"{scenario_id}: fixture 格式錯誤")
            else:
                forbidden = _find_forbidden_keys(fixture)
                if forbidden:
                    errors.append(f"{scenario_id}: fixture 含禁止欄位：{sorted(forbidden)}")
            requested_jid = operation.get("requested_jid")
            if provider == "judicial_jdoc" and (
                not isinstance(requested_jid, str)
                or not JID_PATTERN.fullmatch(requested_jid)
            ):
                errors.append(f"{scenario_id}: judicial_jdoc requested_jid 格式錯誤")
            if provider != "judicial_jdoc" and requested_jid is not None:
                errors.append(f"{scenario_id}: 非 JDoc operation 不得設定 requested_jid")
        if not isinstance(scenario.get("commit"), bool):
            errors.append(f"{scenario_id}: commit 格式錯誤")
        if not _is_utc_timestamp(scenario.get("observed_at")):
            errors.append(f"{scenario_id}: observed_at 必須為 UTC ISO timestamp")
        expected = scenario.get("expected")
        if not isinstance(expected, dict) or set(expected) != EXPECTED_PROJECTION_KEYS:
            errors.append(f"{scenario_id}: expected 欄位集合不符")
            continue
        if expected.get("result_kind") not in {"REPORT", "ERROR"}:
            errors.append(f"{scenario_id}: expected result_kind 不支援")
        if expected.get("error_type") not in ALLOWED_ERROR_TYPES | {None}:
            errors.append(f"{scenario_id}: expected error_type 不支援")
        if expected.get("batch_status") not in {"DRY_RUN", "COMMITTED", None}:
            errors.append(f"{scenario_id}: expected batch_status 不支援")
        item_operations = expected.get("item_operations")
        if not isinstance(item_operations, list) or any(
            item not in {"STORE_METADATA", "REMOVE_METADATA"}
            for item in item_operations
        ):
            errors.append(f"{scenario_id}: expected item_operations 格式錯誤")
        if not isinstance(expected.get("cache_exists"), bool):
            errors.append(f"{scenario_id}: expected cache_exists 格式錯誤")
        for count_key in ("entry_count", "audit_count", "record_count"):
            count = expected.get(count_key)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                errors.append(f"{scenario_id}: expected {count_key} 格式錯誤")
        if expected.get("result_kind") == "REPORT" and (
            expected.get("batch_status") is None or expected.get("error_type") is not None
        ):
            errors.append(f"{scenario_id}: REPORT expected 狀態矛盾")
        if expected.get("result_kind") == "ERROR" and (
            expected.get("batch_status") is not None
            or expected.get("error_type") is None
            or item_operations != []
        ):
            errors.append(f"{scenario_id}: ERROR expected 狀態矛盾")
    return errors


def _build_adapters(
    operations: list[dict[str, Any]],
) -> tuple[list[tuple[str, Any]], dict[str, Any]]:
    requests: list[tuple[str, Any]] = []
    adapters: dict[str, Any] = {}
    for operation in operations:
        provider = operation["provider"]
        fixture = operation["fixture"]
        if provider == "mcp_taiwan_legal_db":
            adapter = TaiwanLegalDbFixtureAdapter(fixture)
        elif provider == "judicial_jdoc":
            adapter = JudicialOpenDataFixtureAdapter(
                fixture,
                requested_jid=operation["requested_jid"],
            )
        else:  # pragma: no cover - corpus validation prevents this path.
            raise ReplayCorpusError(f"不支援的 replay provider：{provider}")
        adapters[adapter.adapter_id] = adapter
        requests.append((adapter.adapter_id, adapter))
    return requests, adapters


def _cache_projection(cache: RetrievalMetadataCache) -> dict[str, Any]:
    if not cache.path.exists():
        return {
            "cache_exists": False,
            "entry_count": 0,
            "audit_count": 0,
            "record_count": 0,
        }
    payload = cache.load()
    return {
        "cache_exists": True,
        "entry_count": len(payload["entries"]),
        "audit_count": len(payload["removal_audit"]),
        "record_count": sum(
            len(response["records"]) for response in payload["entries"].values()
        ),
    }


def run_replay_suite(corpus: dict[str, Any], scratch_dir: Path) -> dict[str, Any]:
    errors = validate_replay_corpus(corpus)
    if errors:
        raise ReplayCorpusError(f"golden replay corpus 無效：{errors}")
    scratch_dir = Path(scratch_dir)
    results: list[dict[str, Any]] = []
    for scenario in corpus["scenarios"]:
        cache = RetrievalMetadataCache(scratch_dir / f"{scenario['scenario_id']}.json")
        if cache.path.exists():
            raise ReplayCorpusError(
                f"replay scratch cache 已存在，拒絕覆寫：{scenario['scenario_id']}"
            )
        query = build_deidentified_query(
            scenario["route_ids"], scenario["observations"]
        )
        requests_with_adapters, adapters = _build_adapters(scenario["operations"])
        manifest = build_offline_batch_manifest(
            [(adapter_id, query) for adapter_id, _adapter in requests_with_adapters]
        )
        try:
            report = run_offline_batch(
                manifest,
                adapters,
                cache,
                commit=scenario["commit"],
                observed_at=scenario["observed_at"],
            )
            actual = {
                "result_kind": "REPORT",
                "batch_status": report["status"],
                "item_operations": [item["operation"] for item in report["items"]],
                **_cache_projection(cache),
                "error_type": None,
            }
        except Exception as exc:
            actual = {
                "result_kind": "ERROR",
                "batch_status": None,
                "item_operations": [],
                **_cache_projection(cache),
                "error_type": type(exc).__name__,
            }
        results.append(
            {
                "scenario_id": scenario["scenario_id"],
                "status": "PASS" if actual == scenario["expected"] else "FAIL",
                "actual": actual,
                "evidence_sha256": _canonical_hash(
                    {"scenario_id": scenario["scenario_id"], "actual": actual}
                ),
            }
        )
    core = {
        "schema_version": REPLAY_REPORT_VERSION,
        "corpus_sha256": _canonical_hash(corpus),
        "scenario_count": len(results),
        "passed_count": sum(result["status"] == "PASS" for result in results),
        "failed_count": sum(result["status"] == "FAIL" for result in results),
        "all_passed": all(result["status"] == "PASS" for result in results),
        "results": results,
        "content_stored": False,
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    return {**core, "suite_evidence_sha256": _canonical_hash(core)}
