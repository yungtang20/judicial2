"""外部 AI 候選罪章分析（OpenAI 相容端點）。

設計邊界：
- key/模型由 .env（IAMHC_API_KEY、IAMHC_BASE_URL、IAMHC_MODEL）提供。
- 只送出案情摘要（承辦人已寫入 intake.summary），不送年籍、案號或問答內容。
- key 未設定、網路失敗或回應不可解析時回傳 None，由呼叫端退回規則引擎。
- 每次呼叫 70 秒逾時；正式 Gate 2 v3 契約為首次加最多 2 次重試。
- 舊版相容函式仍保留原有最多 4 次嘗試，不再由正式 Gate 2 呼叫。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError
from uuid import uuid4

from .v3_contracts import (
    ContractContext,
    ContractValidationError,
    MAX_STAGE_ATTEMPTS,
    SCHEMA_VERSION,
    STAGE_CANDIDATE_ANALYSIS,
    build_request_envelope,
    validate_candidate_analysis_response,
)

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


def _chat(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    *,
    temperature: float = 0.2,
) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
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
                "任務：從目錄中選出案情摘要最相關的 1 至 4 個罪章 id，依可能性排序；完全沒有相關方向時才回傳空陣列。\n"
                "規則：\n"
                "1. 只依摘要文字判斷，不得假設摘要外的事實。\n"
                "2. 即使事實不完整或主體不明，仍盡力提出最接近候選，並把欠缺要件放入 missing。\n"
                "3. 代稱不明（他、對方、有人等）時仍可列候選，但 missing 必須含主體不明。\n"
                "4. 有姓名、可辨識監視器畫面或已鎖定對象時，subject_identified 為 true。\n"
                "5. 已鎖定行為人但贓物尚未尋獲時，is_solved 可為 true，missing 加入贓物流向待查。\n"
                "6. 沒有對人施強暴或使人不能抗拒的行為，即使有取財，也不要優先列強盜。\n"
                "7. 可使用可能涉及、高度可能涉及，不得輸出犯罪成立、構成、該當或應論以等最終法律結論。\n"
                '輸出格式：{"candidates":[{"id":"罪章id","reason":"一句話引用案情","missing":["欠缺要件"]}],"status":{"subject_identified":"true|false|unknown","has_victim":"true|false|unknown","is_solved":"true|false|unknown"}}'
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


V3_CANDIDATE_SYSTEM = (
    "你是案件分類器，只提出候選罪章，不做犯罪成立判斷。"
    "只能依 request.input_payload.case_text 與 offense_catalog 判斷。"
    "必須逐字回傳案情引句及其 Python 字元索引。"
    "只輸出單一 JSON object，不得輸出 Markdown、程式碼圍欄或其他文字。"
)


def build_v3_candidate_prompt(
    request_envelope: dict[str, Any],
    offenses: list[dict[str, Any]],
    *,
    prior_error: ContractValidationError | None = None,
) -> list[dict[str, str]]:
    """建立 v3 候選分類提示；metadata 由程式產生並要求逐欄原樣回傳。"""

    response_template = {
        key: request_envelope[key]
        for key in (
            "schema_version",
            "stage",
            "request_id",
            "case_revision",
            "attempt",
            "input_hash",
            "source_snapshot_hashes",
        )
    }
    response_template["response_payload"] = {
        "candidates": [
            {
                "offense_id": "清單中的 id",
                "reason": "一句話，引用案情原文說明為何可能涉及",
                "basis_quote": "案情逐字引句",
                "basis_start": 0,
                "basis_end": 0,
                "missing": ["仍缺的關鍵事實"],
            }
        ],
        "status": {
            "subject_identified": "true|false|unknown",
            "has_victim": "true|false|unknown",
            "is_solved": "true|false|unknown",
        },
    }
    correction = ""
    if prior_error is not None:
        correction = (
            "\n前次輸出未通過契約驗證："
            f"{prior_error.code}，欄位 {prior_error.path}。請修正後完整重送。\n"
        )
    user_content = (
        "【程式產生的 request】\n"
        f"{json.dumps(request_envelope, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "【offense_catalog】\n"
        f"{json.dumps(offenses, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "規則：\n"
        "1. 從 offense_catalog 選 1 至 4 個 offense_id，不得自創；完全沒有相關方向時才回傳空陣列。\n"
        "2. 只根據 case_text 明載事實，不補人物、時間、地點或動機。\n"
        "3. 即使事實不完整或主體不明，仍盡力提出最接近候選，並把欠缺要件放入 missing。\n"
        "4. 代稱無法辨識時，missing 必須包含「主體不明」。\n"
        "5. reason 與 missing 不得使用「成立、構成、該當、應論以」，只寫可能涉及或待確認。\n"
        "6. basis_quote 必須是 case_text 的連續逐字原文，basis_start/basis_end 使用 Python 字元索引。\n"
        "7. 相對時間照抄，不換算日期。\n"
        "8. 已明示姓名、可辨識監視器畫面或已鎖定對象時，subject_identified 為 true。\n"
        "9. 已鎖定行為人但贓物未尋獲時，is_solved 可為 true，且 missing 加入「贓物流向待查」。\n"
        "10. 沒有對人施強暴或使人不能抗拒的行為，即使有取財，也不要優先列強盜。\n"
        "11. 三個 status 只能是字串 true、false、unknown。\n"
        f"{correction}"
        "【唯一允許的回應形狀；metadata 必須原樣回傳】\n"
        f"{json.dumps(response_template, ensure_ascii=False, separators=(',', ':'))}"
    )
    return [
        {"role": "system", "content": V3_CANDIDATE_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_lawbank_analysis_prompt(
    case_text: str,
    candidate_result: dict[str, Any],
    law_text: str,
) -> list[dict[str, str]]:
    """建立法源風格的第二階段分析提示。

    此提示只負責產生分析 JSON。法條內容由程式注入，判決字號不得由模型
    憑記憶補入。正式 runtime 仍須經 v3 route contract 與人工審核。
    """
    payload = {
        "summary": "2～4 句的專業簡述",
        "per_offence": [{
            "name": "罪名（含條號）",
            "elements": [{
                "element": "要件名稱",
                "status": "已具備|待確認|高度可能",
                "basis": "案情依據或案情未述",
            }],
            "similar_crimes_excluded": ["排除的罪名與簡要理由"],
            "prosecution": "告訴乃論|非告訴乃論|待確認",
            "evidence_hints": ["具體補證建議"],
            "practical_risk": "實務風險評估（1～2句）",
        }],
        "detailed_analysis": {
            "1_行為定性": "",
            "2_與類似罪名區別": "",
            "3_程序要件與告訴乃論": "",
            "4_證據缺口與補證方向": "",
            "5_實務見解參考": "",
        },
        "conclusion": "總結性結論，結尾必須含僅供參考，須人工審核",
    }
    user = (
        "你是資深刑事法務分析助理，輸出風格接近法源法律網。\n"
        "即使案情不完整或主體不明，也要分析可能方向並標示缺口。\n"
        "只能依案情、候選結果與法條原文判斷，不得補人物、時間、地點、動機。\n"
        "每個候選拆解要件，status 只能是已具備、待確認或高度可能。\n"
        "主動比較相似罪名並說明排除理由，評估告訴乃論、告訴期間及實務風險。\n"
        "無法確認判決字號時，只能寫實務上（參考類似判決精神），不得虛構字號。\n"
        "相對時間照抄，不換算。沒有對人施強暴或使人不能抗拒，即使有取財，也不要論以強盜。\n"
        "只輸出 JSON，結論必須含「僅供參考，須人工審核」。\n\n"
        f"【案情】\n{case_text}\n\n"
        f"【候選罪名結果】\n{json.dumps(candidate_result, ensure_ascii=False)}\n\n"
        f"【法條原文】\n{law_text}\n\n"
        f"【唯一允許的 JSON 形狀】\n{json.dumps(payload, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": "你只輸出單一 JSON object，不輸出 Markdown 或其他文字。"},
        {"role": "user", "content": user},
    ]


def analyze_candidates_v3(
    summary: str,
    offenses: list[dict[str, Any]],
    *,
    case_revision: int,
    source_snapshot_hashes: dict[str, str],
) -> dict[str, Any] | None:
    """以 v3 fail-closed 契約分析 Gate 2 候選；失敗時由工作流退回規則路徑。"""

    settings = _settings()
    if settings is None or not summary.strip() or len(summary) > MAX_SUMMARY_CHARS_PER_CALL:
        return None
    api_key, base_url, model = settings
    catalog = [{"id": item["id"], "name": item["name"]} for item in offenses]
    input_payload = {"case_text": summary, "offense_catalog": catalog}
    request_id = str(uuid4())
    prior_error: ContractValidationError | None = None

    for attempt in range(1, MAX_STAGE_ATTEMPTS + 1):
        request_envelope = build_request_envelope(
            stage=STAGE_CANDIDATE_ANALYSIS,
            request_id=request_id,
            case_revision=case_revision,
            attempt=attempt,
            input_payload=input_payload,
            source_snapshot_hashes=source_snapshot_hashes,
        )
        context = ContractContext(
            request_id=request_id,
            case_revision=case_revision,
            input_hash=request_envelope["input_hash"],
            source_snapshot_hashes=source_snapshot_hashes,
            case_text=summary,
            expected_attempt=attempt,
            allowed_offense_ids=frozenset(item["id"] for item in catalog),
        )
        try:
            content = _chat(
                api_key,
                base_url,
                model,
                build_v3_candidate_prompt(
                    request_envelope, catalog, prior_error=prior_error
                ),
                max_tokens=1400,
                temperature=0,
            )
            response = json.loads(content)
            validated = validate_candidate_analysis_response(response, context)
            payload = validated["response_payload"]
            return {
                "candidates": [
                    {
                        "id": item["offense_id"],
                        "reason": item["reason"],
                        "basis_quote": item["basis_quote"],
                        "basis_start": item["basis_start"],
                        "basis_end": item["basis_end"],
                        "missing": item["missing"],
                        "source": "ai",
                    }
                    for item in payload["candidates"]
                ],
                "status": payload["status"],
                "model": model,
                "contract": {
                    "schema_version": SCHEMA_VERSION,
                    "stage": STAGE_CANDIDATE_ANALYSIS,
                    "request_id": request_id,
                    "case_revision": case_revision,
                    "attempt_count": attempt,
                    "input_hash": request_envelope["input_hash"],
                    "source_snapshot_hashes": dict(source_snapshot_hashes),
                },
            }
        except ContractValidationError as exc:
            prior_error = exc
        except (
            AiUnavailable,
            json.JSONDecodeError,
            URLError,
            OSError,
            KeyError,
            IndexError,
            AttributeError,
            TimeoutError,
            TypeError,
        ):
            prior_error = None
    return None

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
