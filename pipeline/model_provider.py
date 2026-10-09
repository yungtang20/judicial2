"""Opt-in local OpenAI-compatible provider for Gate 1 fact extraction."""

from __future__ import annotations

import json
import os
import urllib.request
from urllib.parse import urlparse
from typing import Any

from pipeline.model_contract import validate_gate1_fields


_SYSTEM_PROMPT = """你只負責從去識別化案件摘要抽取程序事實。
輸出 JSON 物件，可用欄位為：受理性質、案號、刑事行為、被害人、event_time、location、summary、article_refs、claims、roles。
不得輸出路由，不得判定罪名，不得補充摘要未記載的事實。無法確認的欄位填 UNKNOWN。
article_refs 只可收錄原文明示條次，並附 source_span。"""


def _local_endpoint() -> str:
    endpoint = os.environ.get("JUDICIAL2_LOCAL_LLM_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("JUDICIAL2_LOCAL_LLM_ENDPOINT is not configured")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1", "localhost", "::1"
    }:
        raise RuntimeError("Gate 1 model endpoint must be loopback-local")
    return endpoint


def extract_fields(summary: str, timeout: float = 30.0) -> dict[str, Any]:
    endpoint = _local_endpoint()
    body = json.dumps(
        {
            "model": os.environ.get("JUDICIAL2_LOCAL_LLM_MODEL", "local-model"),
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": summary},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not isinstance(content, str):
        raise ValueError("local model returned no JSON content")
    return validate_gate1_fields(json.loads(content))
