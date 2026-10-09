"""Minimal deterministic Gate 1 routing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from pipeline.model_contract import validate_gate1_fields


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUTE_CONFIG_PATH = PROJECT_ROOT / "rules" / "route_config.yaml"

_ROUTE_A_NATURES = {"受理", "告訴", "告發"}
_ROUTE_B_NATURES = _ROUTE_A_NATURES | {"查獲"}
_ROUTE_SIGNAL_NATURES = {"報案", "通報", "函送", "移送"}
_ADMIN_TERMS = (
    "行政裁處",
    "社會秩序維護法",
    "道路交通管理處罰條例",
    "社維法違序",
    "自行車酒駕行政裁罰",
)
_NO_VALUE = {"", "無", "UNKNOWN", "不詳", "未提供"}
_EXPLICIT_LAW_REFERENCE = re.compile(
    r"刑法\s*第\s*(\d+)\s*條(?:\s*之\s*(\d+))?"
)


def _infer_procedural_fields(source: str) -> dict[str, str]:
    """Conservatively extract procedural signals from unstructured text.

    This is not a crime classifier.  It only recognizes the procedure words
    used in route_config.yaml, and every inferred field is marked for review.
    """
    nature = None
    nature_terms = (
        ("查獲", "查獲"),
        ("備案", "備案"),
        ("備查", "備案"),
        ("報案證明", "報案"),
        ("報案", "報案"),
        ("通報", "通報"),
        ("函送", "函送"),
        ("移送", "移送"),
        ("告發", "告發"),
        ("告訴", "告訴"),
        ("受理", "受理"),
    )
    for marker, value in nature_terms:
        if marker in source:
            nature = value
            break
    criminal = None
    if any(marker in source for marker in ("刑事", "告訴", "告發", "查獲", "函送", "移送")):
        criminal = "是"
    elif any(marker in source for marker in ("備案", "備查", "報案證明", "遺失", "救護", "自殺通報")):
        criminal = "否"
    victim = None
    if any(marker in source for marker in ("被害人", "受損", "受傷", "遭人", "遭竊")):
        victim = "有"
    elif any(marker in source for marker in ("通緝", "現行犯", "查獲") ):
        victim = "無"
    has_case_number = bool(re.search(r"案號|<CASE_NO>|\bZ\w{8,}\b|刑案案由", source))
    return {
        key: value for key, value in {
            "受理性質": nature,
            "刑事行為": criminal,
            "被害人": victim,
            "案號": "<CASE_NO>" if has_case_number else "無",
        }.items() if value is not None
    }


def _load_route_config() -> dict[str, Any]:
    config = yaml.safe_load(ROUTE_CONFIG_PATH.read_text(encoding="utf-8"))
    routes = {item["route"] for item in config.get("routes", [])}
    if routes != {"A", "B", "C", "D", "E"}:
        raise ValueError("route_config.yaml 結構不完整")
    return config


def _field_value(source: str, field: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(field)}\s*[：:]\s*(.*?)\s*$", source)
    return match.group(1).strip() if match else None


def _criminal_state(source: str) -> bool | None:
    explicit = _field_value(source, "刑事行為")
    if explicit in {"是", "有"}:
        return True
    if explicit in {"否", "無"}:
        return False
    if "事實含刑事行為" in source:
        return True
    if "事實無刑事行為" in source:
        return False
    return None


def _victim_state(source: str) -> bool | None:
    explicit = _field_value(source, "被害人")
    if explicit is not None:
        return explicit not in _NO_VALUE
    if "無被害人" in source:
        return False
    if "有被害人" in source:
        return True
    return None


def _has_case_number(source: str) -> bool:
    value = _field_value(source, "案號")
    return value is not None and value not in _NO_VALUE


def _is_administrative(source: str, nature: str | None) -> bool:
    return nature in _ADMIN_TERMS or any(term in source for term in _ADMIN_TERMS)


def _received_by_case_number(
    nature: str | None, has_case_number: bool, administrative: bool
) -> bool:
    explicit_natures = _ROUTE_B_NATURES | {"備案"}
    return (
        has_case_number
        and not administrative
        and (nature is None or nature in _NO_VALUE or nature not in explicit_natures)
    )


def _matching_routes(source: str) -> set[str]:
    criminal = _criminal_state(source)
    victim = _victim_state(source)
    nature = _field_value(source, "受理性質")
    has_case_number = _has_case_number(source)
    administrative = _is_administrative(source, nature)
    inferred_received = _received_by_case_number(
        nature, has_case_number, administrative
    )
    matches: set[str] = set()

    if criminal is True and victim is True:
        if nature in _ROUTE_A_NATURES | _ROUTE_SIGNAL_NATURES or inferred_received:
            matches.add("A")
    if criminal is True and victim is False:
        if nature in _ROUTE_B_NATURES | _ROUTE_SIGNAL_NATURES or inferred_received:
            matches.add("B")
    if criminal is False and has_case_number:
        matches.add("C")
    if not has_case_number and not administrative:
        if criminal is False or nature == "備案":
            matches.add("D")
    if administrative:
        matches.add("E")

    return matches


def _extract_explicit_law_facts(source: str) -> list[dict[str, Any]]:
    """Extract only explicitly written Criminal Code article references."""
    facts: list[dict[str, Any]] = []
    for match in _EXPLICIT_LAW_REFERENCE.finditer(source):
        article_no = f"刑法第 {match.group(1)} 條"
        if match.group(2) is not None:
            article_no += f"之 {match.group(2)}"
        facts.append(
            {
                "article_no": article_no,
                "source_span": {"start": match.start(), "end": match.end()},
                "text": match.group(0),
            }
        )
    return facts


def _record_source(record: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Build Gate 1 input from a cleaned record and optional model fields.

    The model is allowed to provide structured fields, but this adapter never
    invents them.  A record without those fields remains UNKNOWN instead of
    being routed from offence keywords.
    """
    source = str(record.get("source_raw") or record.get("summary") or "")
    structured: dict[str, Any] = {}
    origin = "none"
    for key in ("gate1_fields", "fields", "structured"):
        value = record.get(key)
        if isinstance(value, dict):
            structured.update(value)
            origin = "model" if key == "gate1_fields" else "provided"
    structured.update({k: v for k, v in record.items() if k in {
        "受理性質", "案號", "刑事行為", "被害人", "case_number",
        "intake_nature", "criminal_act", "victim",
    } and v is not None})
    for key in ("event_time", "location", "summary", "report_time", "婦幼案號", "管轄單位", "受理員警"):
        if record.get(key) is not None:
            structured.setdefault(key, record[key])
    labels = {
        "受理性質": structured.get("受理性質", structured.get("intake_nature")),
        "案號": structured.get("案號", structured.get("case_number")),
        "刑事行為": structured.get("刑事行為", structured.get("criminal_act")),
        "被害人": structured.get("被害人", structured.get("victim")),
    }
    if isinstance(labels["刑事行為"], bool):
        labels["刑事行為"] = "是" if labels["刑事行為"] else "否"
    if isinstance(labels["被害人"], bool):
        labels["被害人"] = "有" if labels["被害人"] else "無"
    labeled = [f"{k}：{v}" for k, v in labels.items() if v is not None]
    if structured:
        structured = validate_gate1_fields(structured)
    return ("\n".join(labeled + [source]) if labeled else source), structured, origin


def _has_route_fields(structured: dict[str, Any]) -> bool:
    return any(
        key in structured
        for key in (
            "受理性質", "案號", "刑事行為", "被害人",
            "case_number", "intake_nature", "criminal_act", "victim",
        )
    )


def _structured_article_facts(structured: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for ref in structured.get("article_refs", []):
        facts.append(
            {
                "article_no": ref["article_no"],
                "source_span": ref.get("source_span"),
                "text": ref.get("text"),
                "source": "model_structured",
            }
        )
    return facts


def run(source: str | dict[str, Any]) -> dict[str, Any]:
    """Return a Gate 1 result for raw text or a cleaned/model-enriched record."""
    structured: dict[str, Any] = {}
    structured_origin = "none"
    record_id = None
    if isinstance(source, dict):
        record_id = source.get("case_id")
        source_text, structured, structured_origin = _record_source(source)
        if not _has_route_fields(structured) and structured_origin != "model":
            inferred = _infer_procedural_fields(source_text)
            if inferred:
                structured.update(inferred)
                structured_origin = "rule_fallback"
                labels = "\n".join(f"{k}：{v}" for k, v in inferred.items())
                source_text = f"{labels}\n{source_text}"
    else:
        source_text = source
    source_text = str(source_text)
    _load_route_config()
    warnings: list[str] = []
    source_unit_ids = [str(record_id)] if record_id else (["unit-001"] if source_text.strip() else [])

    matches = _matching_routes(source_text)
    route = next(iter(matches)) if len(matches) == 1 else "UNKNOWN"
    if route == "UNKNOWN":
        warnings.append("路由無法唯一判定")
    if structured_origin == "rule_fallback":
        warnings.append("Gate 1 程序欄位由規則抽取，待人工核定")
    elif structured_origin == "model":
        warnings.append("Gate 1 模型抽取欄位，待人工核定")
    elif structured_origin == "provided":
        warnings.append("Gate 1 提供欄位，待人工核定")
    elif isinstance(source, dict):
        warnings.append("Gate 1 結構化欄位未提供")
    if route in {"A", "B"} and _field_value(source_text, "案號") in _NO_VALUE:
        warnings.append("案號未填，請承辦人補填")

    return {
        "route": route,
        "warnings": warnings,
        "source_unit_ids": source_unit_ids,
        "facts": _extract_explicit_law_facts(source_text) + _structured_article_facts(structured),
        "fields": structured,
        "field_origin": structured_origin,
        "source_raw": source_text,
    }
