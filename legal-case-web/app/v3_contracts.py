"""Provider-neutral contracts for the case-analysis v3 pipeline.

This module deliberately has no model or workflow side effects.  It defines the
versioned envelopes and fail-closed validators that must exist before a model
adapter can be connected to the formal runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


SCHEMA_VERSION = "case-analysis-v3-contract-v1"
MAX_STAGE_ATTEMPTS = 3  # Initial attempt plus at most two retries.
MAX_CANDIDATES = 4
MAX_REASON_LENGTH = 240
MAX_SUMMARY_LENGTH = 500
MAX_CONCLUSION_LENGTH = 800

STAGE_CANDIDATE_ANALYSIS = "candidate_analysis"
STAGE_ROUTE_ELEMENT_ANALYSIS = "route_element_analysis"
STAGE_STATEMENT_ASSEMBLY = "statement_assembly"
STAGES = {
    STAGE_CANDIDATE_ANALYSIS,
    STAGE_ROUTE_ELEMENT_ANALYSIS,
    STAGE_STATEMENT_ASSEMBLY,
}

TRI_STATE_VALUES = {"true", "false", "unknown"}
ELEMENT_STATUS_VALUES = {"EVIDENCED", "NEEDS_CONFIRMATION"}
PROSECUTION_VALUES = {"告訴乃論", "非告訴乃論", "待確認"}
FORBIDDEN_CONCLUSIONS = ("成立", "構成", "該當", "應論以")
REQUIRED_REVIEW_NOTICE = "僅供參考，須人工審核"
TODO_VALUE = "（待補）"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractValidationError(ValueError):
    """Stable validation error safe to expose through an API error envelope."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message

    def as_error(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": "v3 契約驗證失敗",
                "details": [{"field": self.path, "message": self.message}],
            }
        }


@dataclass(frozen=True)
class ContractContext:
    """Code-owned values used to validate a model or assembler response."""

    request_id: str
    case_revision: int
    input_hash: str
    source_snapshot_hashes: Mapping[str, str]
    case_text: str
    expected_attempt: int | None = None
    allowed_offense_ids: frozenset[str] = frozenset()
    route_parent_by_id: Mapping[str, str] | None = None
    element_ids_by_route: Mapping[str, frozenset[str]] | None = None
    prosecution_by_route: Mapping[str, str] | None = None
    allowed_template_fields: Mapping[str, frozenset[str]] | None = None


def canonical_sha256(value: Any) -> str:
    """Return a deterministic hash for JSON-compatible request content."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_request_envelope(
    *,
    stage: str,
    request_id: str,
    case_revision: int,
    attempt: int,
    input_payload: Mapping[str, Any],
    source_snapshot_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Build the code-owned request metadata that a response must echo."""

    if stage not in STAGES:
        _fail("INVALID_STAGE", "stage", "不支援的 v3 處理階段")
    _validate_nonempty_string(request_id, "request_id", maximum=128)
    _validate_revision(case_revision, "case_revision")
    _validate_attempt(attempt)
    _validate_hash_map(source_snapshot_hashes, "source_snapshot_hashes")
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "request_id": request_id,
        "case_revision": case_revision,
        "attempt": attempt,
        "input_hash": canonical_sha256(input_payload),
        "source_snapshot_hashes": dict(source_snapshot_hashes),
        "input_payload": dict(input_payload),
    }


def validate_candidate_analysis_response(
    response: Mapping[str, Any], context: ContractContext
) -> dict[str, Any]:
    envelope = _validate_response_envelope(
        response, context, STAGE_CANDIDATE_ANALYSIS
    )
    payload = _mapping(envelope["response_payload"], "response_payload")
    _exact_keys(payload, {"candidates", "status"}, "response_payload")

    candidates = _list(payload["candidates"], "response_payload.candidates")
    if len(candidates) > MAX_CANDIDATES:
        _fail(
            "TOO_MANY_CANDIDATES",
            "response_payload.candidates",
            f"候選罪章最多 {MAX_CANDIDATES} 個",
        )
    seen: set[str] = set()
    validated_candidates: list[dict[str, Any]] = []
    for index, raw in enumerate(candidates):
        path = f"response_payload.candidates[{index}]"
        item = _mapping(raw, path)
        _exact_keys(
            item,
            {
                "offense_id",
                "reason",
                "basis_quote",
                "basis_start",
                "basis_end",
                "missing",
            },
            path,
        )
        offense_id = _validate_nonempty_string(
            item["offense_id"], f"{path}.offense_id", maximum=128
        )
        if offense_id not in context.allowed_offense_ids:
            _fail("UNKNOWN_OFFENSE_ID", f"{path}.offense_id", "罪章不在允許清單")
        if offense_id in seen:
            _fail("DUPLICATE_OFFENSE_ID", f"{path}.offense_id", "候選罪章不得重複")
        seen.add(offense_id)
        reason = _validate_safe_text(
            item["reason"], f"{path}.reason", maximum=MAX_REASON_LENGTH
        )
        quote, start, end = _validate_exact_quote(item, path, context.case_text)
        missing = _validate_string_list(item["missing"], f"{path}.missing", maximum=20)
        for missing_index, missing_item in enumerate(missing):
            _reject_forbidden(missing_item, f"{path}.missing[{missing_index}]")
        validated_candidates.append(
            {
                "offense_id": offense_id,
                "reason": reason,
                "basis_quote": quote,
                "basis_start": start,
                "basis_end": end,
                "missing": missing,
            }
        )

    status = _mapping(payload["status"], "response_payload.status")
    expected_status_keys = {"subject_identified", "has_victim", "is_solved"}
    _exact_keys(status, expected_status_keys, "response_payload.status")
    validated_status: dict[str, str] = {}
    for key in sorted(expected_status_keys):
        value = status[key]
        if value not in TRI_STATE_VALUES:
            _fail(
                "INVALID_STATUS",
                f"response_payload.status.{key}",
                "狀態必須為 true、false 或 unknown",
            )
        validated_status[key] = value

    return {**envelope, "response_payload": {
        "candidates": validated_candidates,
        "status": validated_status,
    }}


def validate_route_element_analysis_response(
    response: Mapping[str, Any], context: ContractContext
) -> dict[str, Any]:
    envelope = _validate_response_envelope(
        response, context, STAGE_ROUTE_ELEMENT_ANALYSIS
    )
    payload = _mapping(envelope["response_payload"], "response_payload")
    _exact_keys(payload, {"summary", "per_offence", "conclusion"}, "response_payload")
    summary = _validate_safe_text(
        payload["summary"], "response_payload.summary", maximum=MAX_SUMMARY_LENGTH
    )
    _validate_sentence_limit(summary, "response_payload.summary", maximum=2)
    conclusion = _validate_safe_text(
        payload["conclusion"],
        "response_payload.conclusion",
        maximum=MAX_CONCLUSION_LENGTH,
    )
    _validate_sentence_limit(conclusion, "response_payload.conclusion", maximum=4)
    if REQUIRED_REVIEW_NOTICE not in conclusion:
        _fail(
            "MISSING_REVIEW_NOTICE",
            "response_payload.conclusion",
            f"結論必須包含「{REQUIRED_REVIEW_NOTICE}」",
        )

    route_parents = context.route_parent_by_id or {}
    elements_by_route = context.element_ids_by_route or {}
    prosecution_by_route = context.prosecution_by_route or {}
    per_offence = _list(payload["per_offence"], "response_payload.per_offence")
    if not per_offence:
        _fail("EMPTY_ANALYSIS", "response_payload.per_offence", "要件分析不得為空")
    seen_routes: set[str] = set()
    validated_items: list[dict[str, Any]] = []
    for index, raw in enumerate(per_offence):
        path = f"response_payload.per_offence[{index}]"
        item = _mapping(raw, path)
        _exact_keys(
            item,
            {"offense_id", "route_id", "elements", "prosecution", "evidence_hints"},
            path,
        )
        offense_id = _validate_nonempty_string(item["offense_id"], f"{path}.offense_id")
        route_id = _validate_nonempty_string(item["route_id"], f"{path}.route_id")
        if offense_id not in context.allowed_offense_ids:
            _fail("UNKNOWN_OFFENSE_ID", f"{path}.offense_id", "罪章不在人工核准清單")
        if route_parents.get(route_id) != offense_id:
            _fail(
                "ROUTE_PARENT_MISMATCH",
                f"{path}.route_id",
                "法律路由不屬於指定的候選罪章",
            )
        if route_id in seen_routes:
            _fail("DUPLICATE_ROUTE_ID", f"{path}.route_id", "法律路由不得重複")
        seen_routes.add(route_id)

        allowed_elements = elements_by_route.get(route_id, frozenset())
        elements = _list(item["elements"], f"{path}.elements")
        if not elements:
            _fail("EMPTY_ELEMENTS", f"{path}.elements", "法律路由的要件分析不得為空")
        seen_elements: set[str] = set()
        validated_elements: list[dict[str, Any]] = []
        for element_index, raw_element in enumerate(elements):
            element_path = f"{path}.elements[{element_index}]"
            element = _mapping(raw_element, element_path)
            _exact_keys(
                element,
                {"element_id", "status", "basis_quote", "basis_start", "basis_end"},
                element_path,
            )
            element_id = _validate_nonempty_string(
                element["element_id"], f"{element_path}.element_id"
            )
            if element_id not in allowed_elements:
                _fail(
                    "UNKNOWN_ELEMENT_ID",
                    f"{element_path}.element_id",
                    "要件不屬於指定的法律路由",
                )
            if element_id in seen_elements:
                _fail(
                    "DUPLICATE_ELEMENT_ID",
                    f"{element_path}.element_id",
                    "同一法律路由的要件不得重複",
                )
            seen_elements.add(element_id)
            status = element["status"]
            if status not in ELEMENT_STATUS_VALUES:
                _fail(
                    "INVALID_ELEMENT_STATUS",
                    f"{element_path}.status",
                    "要件狀態必須為 EVIDENCED 或 NEEDS_CONFIRMATION",
                )
            if status == "EVIDENCED":
                quote, start, end = _validate_exact_quote(
                    element, element_path, context.case_text
                )
            else:
                quote, start, end = _validate_empty_quote(element, element_path)
            validated_elements.append(
                {
                    "element_id": element_id,
                    "status": status,
                    "basis_quote": quote,
                    "basis_start": start,
                    "basis_end": end,
                }
            )

        prosecution = item["prosecution"]
        if prosecution not in PROSECUTION_VALUES:
            _fail(
                "INVALID_PROSECUTION_STATUS",
                f"{path}.prosecution",
                "告訴乃論狀態不在允許值",
            )
        expected_prosecution = prosecution_by_route.get(route_id, "待確認")
        if prosecution != expected_prosecution:
            _fail(
                "PROSECUTION_SOURCE_MISMATCH",
                f"{path}.prosecution",
                "告訴乃論狀態與程式提供的法源資料不一致",
            )
        hints = _validate_string_list(
            item["evidence_hints"], f"{path}.evidence_hints", maximum=30
        )
        for hint_index, hint in enumerate(hints):
            _reject_forbidden(hint, f"{path}.evidence_hints[{hint_index}]")
        validated_items.append(
            {
                "offense_id": offense_id,
                "route_id": route_id,
                "elements": validated_elements,
                "prosecution": prosecution,
                "evidence_hints": hints,
            }
        )

    return {**envelope, "response_payload": {
        "summary": summary,
        "per_offence": validated_items,
        "conclusion": conclusion,
    }}


def validate_statement_assembly(
    response: Mapping[str, Any], context: ContractContext
) -> dict[str, Any]:
    """Validate code-generated statement fields; this is not a model contract."""

    envelope = _validate_response_envelope(
        response, context, STAGE_STATEMENT_ASSEMBLY
    )
    payload = _mapping(envelope["response_payload"], "response_payload")
    _exact_keys(payload, {"template_id", "fields", "notice"}, "response_payload")
    template_id = _validate_nonempty_string(
        payload["template_id"], "response_payload.template_id"
    )
    allowed_templates = context.allowed_template_fields or {}
    if template_id not in allowed_templates:
        _fail(
            "UNKNOWN_TEMPLATE_ID",
            "response_payload.template_id",
            "模板不在程式允許清單",
        )
    fields = _mapping(payload["fields"], "response_payload.fields")
    _exact_keys(fields, set(allowed_templates[template_id]), "response_payload.fields")
    validated_fields: dict[str, str] = {}
    for field_id, value in fields.items():
        if not isinstance(value, str):
            _fail(
                "INVALID_FIELD_VALUE",
                f"response_payload.fields.{field_id}",
                "條陳欄位必須是文字",
            )
        normalized = value.strip() or TODO_VALUE
        _reject_forbidden(normalized, f"response_payload.fields.{field_id}")
        validated_fields[field_id] = normalized
    notice = _validate_nonempty_string(
        payload["notice"], "response_payload.notice", maximum=300
    )
    if "不構成正式文書" not in notice:
        _fail(
            "MISSING_STATEMENT_NOTICE",
            "response_payload.notice",
            "條陳必須標示不構成正式文書",
        )
    return {**envelope, "response_payload": {
        "template_id": template_id,
        "fields": validated_fields,
        "notice": notice,
    }}


def _validate_response_envelope(
    response: Mapping[str, Any], context: ContractContext, expected_stage: str
) -> dict[str, Any]:
    envelope = _mapping(response, "response")
    expected_keys = {
        "schema_version",
        "stage",
        "request_id",
        "case_revision",
        "attempt",
        "input_hash",
        "source_snapshot_hashes",
        "response_payload",
    }
    _exact_keys(envelope, expected_keys, "response")
    if envelope["schema_version"] != SCHEMA_VERSION:
        _fail("SCHEMA_VERSION_MISMATCH", "schema_version", "不支援的 schema 版本")
    if envelope["stage"] != expected_stage:
        _fail("STAGE_MISMATCH", "stage", "回應階段與預期不符")
    if envelope["request_id"] != context.request_id:
        _fail("REQUEST_ID_MISMATCH", "request_id", "回應不屬於目前請求")
    _validate_revision(envelope["case_revision"], "case_revision")
    if envelope["case_revision"] != context.case_revision:
        _fail("STALE_CASE_REVISION", "case_revision", "案件 revision 已變更")
    attempt = _validate_attempt(envelope["attempt"])
    if context.expected_attempt is not None and attempt != context.expected_attempt:
        _fail("ATTEMPT_MISMATCH", "attempt", "回應 attempt 與目前嘗試次數不符")
    _validate_hash(envelope["input_hash"], "input_hash")
    if envelope["input_hash"] != context.input_hash:
        _fail("INPUT_HASH_MISMATCH", "input_hash", "回應輸入 hash 與目前請求不符")
    hashes = _validate_hash_map(
        envelope["source_snapshot_hashes"], "source_snapshot_hashes"
    )
    if hashes != dict(context.source_snapshot_hashes):
        _fail(
            "SOURCE_SNAPSHOT_MISMATCH",
            "source_snapshot_hashes",
            "法源或資料來源快照已變更",
        )
    return dict(envelope)


def _validate_attempt(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_STAGE_ATTEMPTS:
        _fail(
            "ATTEMPT_LIMIT_EXCEEDED",
            "attempt",
            f"attempt 必須介於 1 與 {MAX_STAGE_ATTEMPTS}",
        )
    return value


def _validate_revision(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("INVALID_REVISION", path, "case_revision 必須是非負整數")
    return value


def _validate_hash_map(value: Any, path: str) -> dict[str, str]:
    hashes = _mapping(value, path)
    if not hashes:
        _fail("EMPTY_SOURCE_SNAPSHOTS", path, "至少需要一個來源快照 hash")
    validated: dict[str, str] = {}
    for key, digest in hashes.items():
        name = _validate_nonempty_string(key, f"{path}.<key>", maximum=128)
        validated[name] = _validate_hash(digest, f"{path}.{name}")
    return validated


def _validate_hash(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        _fail("INVALID_SHA256", path, "必須是小寫十六進位 SHA-256")
    return value


def _validate_exact_quote(
    item: Mapping[str, Any], path: str, case_text: str
) -> tuple[str, int, int]:
    quote = _validate_nonempty_string(
        item["basis_quote"], f"{path}.basis_quote", maximum=1000
    )
    start = item["basis_start"]
    end = item["basis_end"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end > len(case_text)
        or case_text[start:end] != quote
    ):
        _fail(
            "BASIS_QUOTE_MISMATCH",
            f"{path}.basis_quote",
            "案情引句及其位置無法逐字回查",
        )
    return quote, start, end


def _validate_empty_quote(
    item: Mapping[str, Any], path: str
) -> tuple[str, None, None]:
    if item["basis_quote"] != "案情未述" or item["basis_start"] is not None or item["basis_end"] is not None:
        _fail(
            "UNSUPPORTED_BASIS_FOR_PENDING",
            f"{path}.basis_quote",
            "待確認要件必須使用「案情未述」且不提供位置",
        )
    return "案情未述", None, None


def _validate_safe_text(value: Any, path: str, *, maximum: int) -> str:
    text = _validate_nonempty_string(value, path, maximum=maximum)
    _reject_forbidden(text, path)
    return text


def _validate_sentence_limit(value: str, path: str, *, maximum: int) -> None:
    sentences = [part for part in re.split(r"[。！？!?]+", value) if part.strip()]
    if len(sentences) > maximum:
        _fail("TOO_MANY_SENTENCES", path, f"最多 {maximum} 句")


def _reject_forbidden(value: str, path: str) -> None:
    hit = next((word for word in FORBIDDEN_CONCLUSIONS if word in value), None)
    if hit:
        _fail("FORBIDDEN_CONCLUSION", path, f"不得使用「{hit}」")


def _validate_nonempty_string(value: Any, path: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("INVALID_STRING", path, "必須是非空文字")
    text = value.strip()
    if len(text) > maximum:
        _fail("TEXT_TOO_LONG", path, f"文字不得超過 {maximum} 字")
    return text


def _validate_string_list(value: Any, path: str, *, maximum: int) -> list[str]:
    items = _list(value, path)
    if len(items) > maximum:
        _fail("TOO_MANY_ITEMS", path, f"項目不得超過 {maximum} 筆")
    validated: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        text = _validate_nonempty_string(item, f"{path}[{index}]", maximum=500)
        if text in seen:
            _fail("DUPLICATE_ITEM", f"{path}[{index}]", "項目不得重複")
        seen.add(text)
        validated.append(text)
    return validated


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("INVALID_OBJECT", path, "必須是 JSON object")
    if any(not isinstance(key, str) for key in value):
        _fail("INVALID_OBJECT_KEY", path, "JSON object key 必須是文字")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("INVALID_ARRAY", path, "必須是 JSON array")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown:
        _fail("UNKNOWN_FIELD", path, "包含未知欄位：" + "、".join(unknown))
    if missing:
        _fail("MISSING_FIELD", path, "缺少必要欄位：" + "、".join(missing))


def _fail(code: str, path: str, message: str) -> None:
    raise ContractValidationError(code, path, message)
