"""外部 AI 候選罪章分析（OpenAI 相容端點）。

設計邊界：
- key/模型由 .env（IAMHC_API_KEY、IAMHC_BASE_URL、IAMHC_MODEL）提供。
- 只送出案情摘要（承辦人已寫入 intake.summary），不送年籍、案號或問答內容。
- key 未設定、網路失敗或回應不可解析時回傳 None，由呼叫端退回規則引擎。
- 每次呼叫 70 秒逾時；總嘗試次數最多 4 次。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_BASE_URL = "https://api.iamhc.cn/v1"
DEFAULT_MODEL = "glm-5.3-flash"
TIMEOUT_SECONDS = 70
MAX_ATTEMPTS = 4
MAX_SUMMARY_CHARS_PER_CALL = 4000


class AiUnavailable(RuntimeError):
    pass


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def external_ai_enabled() -> bool:
    """外部 AI 必須由承辦人明確啟用，API key 本身不構成授權。"""
    env = _load_env()
    return _truthy(env.get("ALLOW_EXTERNAL_AI") or os.environ.get("ALLOW_EXTERNAL_AI"))


def _settings() -> tuple[str, str, str] | None:
    if not external_ai_enabled():
        return None
    env = _load_env()
    api_key = env.get("IAMHC_API_KEY") or os.environ.get("IAMHC_API_KEY", "")
    if not api_key:
        return None
    base_url = (env.get("IAMHC_BASE_URL") or os.environ.get("IAMHC_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = env.get("IAMHC_MODEL") or os.environ.get("IAMHC_MODEL") or DEFAULT_MODEL
    return api_key, base_url, model


def ai_configured() -> bool:
    return _settings() is not None


def _chat(api_key: str, base_url: str, model: str, messages: list[dict[str, str]], max_tokens: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urlrequest.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))
    choice = body.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AiUnavailable("AI 回應內容為空")
    return content


def _extract_json(content: str) -> Any:
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    candidate = fenced.group(1) if fenced else content
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise AiUnavailable("AI 回應不含 JSON")
    return json.loads(match.group(0))


ANALYZE_SYSTEM = (
    "你是警察機關筆錄製作輔助系統的罪章分析模組。"
    "你只做候選罪章分類，不做犯罪成立判斷。"
    "只輸出 JSON，不要輸出其他文字。"
)


def build_analyze_prompt(
    summary: str,
    offenses: list[dict[str, Any]],
    facts: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    catalog = "\n".join(f"- {item['id']}：{item['name']}" for item in offenses)
    facts_block = ""
    if facts:
        lines = []
        for f in facts:
            fields = []
            for key in ("subject", "action", "object", "time", "place"):
                value = str(f.get(key, "")).strip()
                if value:
                    fields.append(f"{key}={value}")
            lines.append(f"- {f['text']}" + (f"（{'；'.join(fields)}）" if fields else ""))
        facts_block = "\n已切分的結構化事實（僅供參考，不得新增其中不存在的事實）：\n" + "\n".join(lines) + "\n\n"
    return [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {
            "role": "user",
            "content": (
                "以下是本案案情摘要（可能含 UNKNOWN 表示待查）。\n"
                f"案情摘要：{summary}\n\n"
                f"{facts_block}"
                "候選罪章目錄（id：名稱）：\n"
                f"{catalog}\n\n"
                "任務：從目錄中選出案情摘要可能涉及的罪章 id（0 至 6 個，依可能性排序）。\n"
                "規則：\n"
                "1. 只依摘要文字判斷，不得假設摘要外的事實。\n"
                "2. 語意相近或易混淆的罪章（例如竊盜與侵占）都應列出供承辦人區辨。\n"
                "3. 摘要資訊不足以對應任何罪章時，回傳空陣列。\n"
                "4. 不得輸出犯罪成立、故意成立、因果關係成立或競合成立等結論；僅列候選方向。\n"
                '輸出格式：{"candidates":[{"id":"罪章id","reason":"30字內理由"}]}'
            ),
        },
    ]


def _summary_chunks(summary: str, limit: int = MAX_SUMMARY_CHARS_PER_CALL) -> list[str]:
    """以句界切分長摘要，避免外部 AI 只收到前段而遺失後段事實。"""
    normalized = summary.strip()
    if len(normalized) <= limit:
        return [normalized]
    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > limit:
        boundary = max(
            remaining.rfind(mark, 0, limit + 1)
            for mark in ("。", "！", "？", "；", "\n")
        )
        if boundary < max(1, limit // 2):
            boundary = limit
        else:
            boundary += 1
        chunks.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _analyze_candidates_once(
    summary: str,
    offenses: list[dict[str, Any]],
    max_candidates: int = 6,
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """對單一摘要片段呼叫一次分析；無法取得 AI 分析時回傳 None。

    facts：gate1 結構化事實（僅供提示注入；不得擴大判斷範圍）。
    """
    settings = _settings()
    if settings is None:
        return None
    api_key, base_url, model = settings
    valid_ids = {item["id"] for item in offenses}
    messages = build_analyze_prompt(summary, offenses, facts)
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            content = _chat(api_key, base_url, model, messages, max_tokens=700)
            data = _extract_json(content)
            raw_candidates = data.get("candidates", [])
            if not isinstance(raw_candidates, list):
                raise AiUnavailable("candidates 必須是陣列")
            candidates: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in raw_candidates:
                if not isinstance(item, dict):
                    continue
                offense_id = str(item.get("id", "")).strip()
                if offense_id not in valid_ids or offense_id in seen:
                    continue
                seen.add(offense_id)
                candidates.append({
                    "id": offense_id,
                    "reason": str(item.get("reason", ""))[:120],
                    "source": "ai",
                })
                if len(candidates) >= max_candidates:
                    break
            return {"candidates": candidates, "model": model}
        except (AiUnavailable, json.JSONDecodeError, URLError, OSError, KeyError, TimeoutError) as exc:
            last_error = exc
            if attempt == MAX_ATTEMPTS - 1:
                break
    if last_error is not None:
        # 靜默退回規則引擎；UI 顯示「規則候選」即可辨識。
        return None
    return None


def analyze_candidates(
    summary: str,
    offenses: list[dict[str, Any]],
    max_candidates: int = 6,
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """分析完整摘要；長摘要會分段呼叫並合併候選方向。"""
    chunks = _summary_chunks(summary)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    model = ""
    for chunk in chunks:
        result = _analyze_candidates_once(chunk, offenses, max_candidates, facts)
        if result is None:
            return None
        model = result.get("model", model)
        for item in result.get("candidates", []):
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            merged.append(item)
            if len(merged) >= max_candidates:
                break
        if len(merged) >= max_candidates:
            break
    return {
        "candidates": merged[:max_candidates],
        "model": model,
        "chunk_count": len(chunks),
    }

SEGMENT_SYSTEM = (
    "你是警察機關筆錄製作輔助系統的事實切分模組。"
    "你的任務是把單一段落案情摘要切成多筆結構化事實，供承辦人逐筆確認。"
    "你只做切分，不做法律評價；不得新增摘要中不存在的事實；"
    "不得推論行為人、故意、因果；摘要未交代的欄位一律留空字串。"
    "只輸出 JSON，不要輸出其他文字。"
)


def build_segment_prompt(summary: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SEGMENT_SYSTEM},
        {
            "role": "user",
            "content": (
                "把以下案情摘要切成 1 至 12 筆獨立事實。每筆事實：\n"
                "1. text：摘要中的原文片段（逐字，不得改寫、不得杜撰）。\n"
                "2. subject/action/object/recipient/time/place：摘要明確交代才填，否則空字串。\n"
                "3. kind：event（客觀事件）/ statement（當事人陳述）/ unknown（待查事項）。\n"
                "摘要：\n"
                f"{summary}\n\n"
                '輸出格式：{"facts":[{"text":"原文片段","kind":"event","subject":"",'
                '"action":"","object":"","recipient":"","time":"","place":""}]}'
            ),
        },
    ]


def segment_facts(
    summary: str, max_facts: int = 12
) -> dict[str, Any] | None:
    """把摘要切成結構化事實；無法取得 AI 時回傳 None（呼叫端退回規則路徑）。

    嚴格 schema 驗證：text 必須為摘要子字串（防杜撰）；kind 必須在允許集內。
    """
    settings = _settings()
    if settings is None:
        return None
    api_key, base_url, model = settings
    messages = build_segment_prompt(summary)
    for attempt in range(MAX_ATTEMPTS):
        try:
            content = _chat(api_key, base_url, model, messages, max_tokens=1600)
            data = _extract_json(content)
            raw_facts = data.get("facts", [])
            if not isinstance(raw_facts, list):
                raise AiUnavailable("facts 必須是陣列")
            lowered_summary = summary.casefold()
            facts: list[dict[str, Any]] = []
            allowed_kinds = {"event", "statement", "unknown"}
            for item in raw_facts:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                # 防杜撰：text 必須在摘要中逐字存在
                if text.casefold() not in lowered_summary:
                    continue
                kind = str(item.get("kind", "event")).strip()
                if kind not in allowed_kinds:
                    kind = "event"
                if len(facts) >= max_facts:
                    break
                facts.append({
                    "text": text,
                    "kind": kind,
                    "subject": str(item.get("subject", ""))[:60],
                    "action": str(item.get("action", ""))[:60],
                    "object": str(item.get("object", ""))[:60],
                    "recipient": str(item.get("recipient", ""))[:60],
                    "time": str(item.get("time", ""))[:40],
                    "place": str(item.get("place", ""))[:60],
                })
            if not facts:
                raise AiUnavailable("切分結果為空")
            return {"facts": facts, "model": model}
        except (AiUnavailable, json.JSONDecodeError, URLError, OSError, KeyError, TimeoutError):
            # 靜默退回規則路徑（analyze_gate1 fallback）；與 analyze_candidates 同模式
            if attempt == MAX_ATTEMPTS - 1:
                break
    return None
