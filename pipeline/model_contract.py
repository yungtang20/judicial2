"""Validation boundary for an optional local/web AI Gate 1 adapter.

The model may extract fields, but it cannot select a route or a crime chapter.
The deterministic gates remain the only components that route or query laws.
"""

from __future__ import annotations

from typing import Any


ALLOWED_FIELDS = {
    "受理性質", "案號", "刑事行為", "被害人", "event_time", "location", "summary",
    "article_refs", "claims", "roles",
    "case_number", "intake_nature", "criminal_act", "victim",
    "report_time", "婦幼案號", "管轄單位", "受理員警",
}


def validate_gate1_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Gate 1 model output must be an object")
    unknown = set(value) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Gate 1 model output has unsupported fields: {sorted(unknown)}")
    result = dict(value)
    article_refs = result.get("article_refs", [])
    if not isinstance(article_refs, list):
        raise TypeError("article_refs must be an array")
    for ref in article_refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("article_no"), str):
            raise TypeError("each article_ref must contain article_no")
        span = ref.get("source_span")
        if span is not None and (
            not isinstance(span, dict)
            or not isinstance(span.get("start"), int)
            or not isinstance(span.get("end"), int)
            or span["start"] < 0
            or span["end"] < span["start"]
        ):
            raise ValueError("article_ref source_span is invalid")
    return result
