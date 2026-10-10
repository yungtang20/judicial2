"""外部 AI 候選罪章分析（OpenAI 相容端點）。

設計邊界：
- key/模型由 .env（IAMHC_API_KEY、IAMHC_BASE_URL、IAMHC_MODEL）提供。
- 只送出案情摘要（承辦人已寫入 intake.summary），不送年籍、案號或問答內容。
- key 未設定、網路失敗或回應不可解析時回傳 None，由呼叫端退回規則引擎。
- 每次呼叫 15 秒逾時；重試最多 1 次。
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


def _settings() -> tuple[str, str, str] | None:
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


def build_analyze_prompt(summary: str, offenses: list[dict[str, Any]]) -> list[dict[str, str]]:
    catalog = "\n".join(f"- {item['id']}：{item['name']}" for item in offenses)
    return [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {
            "role": "user",
            "content": (
                "以下是本案案情摘要（可能含 UNKNOWN 表示待查）。\n"
                f"案情摘要：{summary}\n\n"
                "候選罪章目錄（id：名稱）：\n"
                f"{catalog}\n\n"
                "任務：從目錄中選出案情摘要可能涉及的罪章 id（0 至 6 個，依可能性排序）。\n"
                "規則：\n"
                "1. 只依摘要文字判斷，不得假設摘要外的事實。\n"
                "2. 語意相近或易混淆的罪章（例如竊盜與侵占）都應列出供承辦人區辨。\n"
                "3. 摘要資訊不足以對應任何罪章時，回傳空陣列。\n"
                '輸出格式：{"candidates":[{"id":"罪章id","reason":"30字內理由"}]}'
            ),
        },
    ]


def analyze_candidates(
    summary: str, offenses: list[dict[str, Any]], max_candidates: int = 6
) -> dict[str, Any] | None:
    """回傳 {"candidates": [...], "model": str}；無法取得 AI 分析時回傳 None。"""
    settings = _settings()
    if settings is None:
        return None
    api_key, base_url, model = settings
    valid_ids = {item["id"] for item in offenses}
    messages = build_analyze_prompt(summary, offenses)
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
