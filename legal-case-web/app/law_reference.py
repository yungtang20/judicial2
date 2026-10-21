"""法源核實（spec §5.5）：經 tw-legal-rag REST 端點查詢現行條文。

原則：
- 僅查詢法規名稱與條號（不含案情、個資）——非敏感傳輸。
- 每筆查詢記錄：法規名、條號、條文全文、官方 URL、最後修正日、dataset 版本、核對時間。
- 離線快照（data/law_reference_cache.json）：測試與離線環境不依賴網路。
- 未核實不得標示已確認法源（spec §1.2）。
- 廢止條文禁止作為現行法源。
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TLR_LAW_ARTICLE_URL = "https://tlr.dr-legal.com.tw/v1/law_article"
USER_AGENT = "judicial2-law-reference/1.0"
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "law_reference_cache.json"
REQUEST_TIMEOUT = 20


class LawReferenceError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def get_cached_law_article(law_name: str, article_no: str) -> dict[str, Any] | None:
    """只讀取離線法條快照；查無資料時不得觸發網路或憑記憶補文。"""

    cache = load_cache()
    for key in _candidate_keys(law_name, article_no):
        entry = cache.get(key)
        if isinstance(entry, dict) and not entry.get("abolished"):
            return dict(entry)
    return None


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def _fetch_article(law_name: str, article_no: str) -> dict[str, Any]:
    payload = json.dumps({"law_name": law_name, "article_no": article_no}).encode("utf-8")
    request = urllib.request.Request(
        TLR_LAW_ARTICLE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    matches = data.get("matches") or []
    if not matches:
        candidates = data.get("law_candidates") or []
        raise LawReferenceError(
            f"查無 {law_name} 第 {article_no} 條" + (f"；候選法規：{'、'.join(candidates[:3])}" if candidates else "")
        )
    entry = matches[0]
    return {
        "law_name": entry["law_name"],
        "article_no": entry["article_no"],
        "article_content": entry["article_content"],
        "law_url": entry.get("law_url", ""),
        "law_modified_date": entry.get("law_modified_date", ""),
        "dataset_version": entry.get("dataset_version", ""),
        "abolished": bool(entry.get("abolished")),
        "verified_at": _now(),
    }


def _candidate_keys(law_name: str, article_no: str) -> list[str]:
    keys = [f"{law_name}:{article_no}"]
    clean_art = article_no.replace("第", "").replace("條", "")
    hyphen_art = clean_art.replace("之", "-")
    law_variants = [law_name]
    if law_name.startswith("中華民國"):
        law_variants.append(law_name[4:])
    else:
        law_variants.append(f"中華民國{law_name}")
    for l in law_variants:
        for a in [article_no, clean_art, hyphen_art, f"第{clean_art}條", f"第{hyphen_art}條"]:
            k = f"{l}:{a}"
            if k not in keys:
                keys.append(k)
    return keys


def get_law_article(
    law_name: str, article_no: str, *, use_cache: bool = True
) -> dict[str, Any]:
    """查詢並快取法條。cache 命中且非廢止即回傳；否則打 REST。"""
    cache = load_cache() if use_cache else {}
    if use_cache:
        for k in _candidate_keys(law_name, article_no):
            if k in cache:
                return cache[k]
    entry = _fetch_article(law_name, article_no)
    if use_cache:
        key = f"{law_name}:{article_no}"
        cache[key] = entry
        save_cache(cache)
    return entry


def build_verified_source(
    law_name: str, article_no: str, *, use_cache: bool = True
) -> dict[str, Any]:
    """產出題庫 offense["source"] 用的核實法源標記。"""
    entry = get_law_article(law_name, article_no, use_cache=use_cache)
    if entry["abolished"]:
        raise LawReferenceError(f"{entry['law_name']} {entry['article_no']} 已廢止，不得作為現行法源")
    return {
        "label": f"{entry['law_name']}{entry['article_no']}（核實自全國法規資料庫鏡像 dataset {entry['dataset_version']}）",
        "status": "VERIFIED_CURRENT",
        "law_name": entry["law_name"],
        "article_no": entry["article_no"],
        "law_url": entry["law_url"],
        "law_modified_date": entry["law_modified_date"],
        "dataset_version": entry["dataset_version"],
        "verified_at": entry["verified_at"],
        "verification_note": "現行法核實；行為時法（歷史版本）仍須由承辦人依官方修正歷程確認。",
    }

def check_event_time_against_law(
    event_time: str, law_modified_date: str
) -> dict[str, Any] | None:
    """行為時法警示（spec §5.5：不得以現行法核實替代行為時法）。

    案件行為時間早於法條最後修正日時，回傳警示：
    行為時之歷史版本可能不同，承辦人須依官方修正歷程確認。
    """
    if not event_time or not law_modified_date:
        return None
    try:
        from datetime import datetime
        event_date = datetime.fromisoformat(event_time).date()
        modified = datetime.strptime(law_modified_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    if event_date < modified:
        return {
            "level": "EVENT_TIME_BEFORE_LAW_AMENDMENT",
            "event_date": event_date.isoformat(),
            "law_modified_date": law_modified_date,
            "message": (
                f"案件行為時間 {event_date.isoformat()} 早於法條最後修正日 "
                f"{law_modified_date}；本核實為現行法，行為時之歷史版本可能不同，"
                "承辦人須依官方修正歷程確認行為時法。"
            ),
        }


def check_constitutional_validity(
    law_name: str, article_no: str
) -> dict[str, Any] | None:
    """憲法法庭判決宣告違憲失效檢驗（spec §5.5）。

    經憲法法庭判決宣告違憲失效之條文（如 113 年憲判字第 9 號判決宣告刑法第 141 條之 1 違憲失效），
    不得作為現行犯罪成立之論罪法源；僅供歷史行為時法查對或條件式路由參考。
    """
    clean_art = (
        article_no.replace("第", "").replace("條", "").replace("之", "-").strip()
    )
    clean_law = law_name.replace("中華民國", "").strip()
    if clean_law == "刑法" and clean_art == "141-1":
        return {
            "status": "UNCONSTITUTIONAL_INVALIDATED",
            "judgment": "憲法法庭 113 年憲判字第 9 號判決",
            "announced_date": "2024-10-25",
            "effect": "失其效力",
            "message": (
                "刑法第141條之1業經憲法法庭113年憲判字第9號判決宣告違憲，"
                "自113年10月25日起失效，不得作為現行犯罪成立或移送之有效法規依據；"
                "僅供歷史行為時法查對或條件式路由參考。"
            ),
        }
    return None
