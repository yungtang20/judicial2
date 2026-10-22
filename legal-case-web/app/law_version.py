"""行為時法（歷史版本）判定（2026-10-22 新增）。

背景：題庫與 ``app/law_reference.py`` 長年只提供「現行法核實」，並以
``verification_note`` 提醒「行為時法仍須由承辦人依官方修正歷程確認」。
本模組把這句提醒變成可重現的判定：讀取 ``data/law_amendment_history.json``
（由 ``scripts/capture_law_amendment_history.py`` 從全國法規資料庫「法規
沿革」頁產生，原始 HTML 與 hash 一併保存），針對**單一條號**回答：

- 事件日當時，該條號是否已施行？
- 事件日之後該條號是否曾被修正／刪除（因此現行文字不是行為時法）？
- 該次修正的公布日、施行日與官方沿革原文是哪一筆？

邊界（刻意設計）：
- **不重建歷史條文**。沿革頁只有條號與日期，沒有舊條文；本模組只指出
  「必須查哪一筆」，並附官方連結，不產生任何條文文字。
- 任何結果都帶 ``legal_conclusion: False`` 與
  ``review_status: HUMAN_REVIEW_REQUIRED``。
- 施行日不明（同一修正分段施行）時，若事件日在最後修正日之前，一律回
  ``VERSION_HISTORY_INCOMPLETE``，不以推測補值。
- 未出現在任何修正紀錄的條號，仍可能自制定時即存在；本模組回
  ``NO_AMENDMENT_RECORDED`` 並註明依據是官方沿革頁，而非條文本身。
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "law-amendment-history-v1"
AUDIT_SCHEMA = "law-version-audit-v1"
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "law_amendment_history.json"
)

STATUS_CURRENT = "CURRENT_VERSION_APPLIES"
STATUS_HISTORICAL = "HISTORICAL_VERSION_REQUIRED"
STATUS_NOT_YET = "ARTICLE_NOT_YET_IN_FORCE"
STATUS_REPEALED = "ARTICLE_NOT_IN_FORCE_AT_EVENT_TIME"
STATUS_NO_RECORD = "NO_AMENDMENT_RECORDED"
STATUS_INCOMPLETE = "VERSION_HISTORY_INCOMPLETE"
STATUS_EVENT_UNKNOWN = "EVENT_DATE_UNKNOWN"

HISTORICAL_TEXT_WARNING = (
    "本庫不含歷史條文文字；請依官方沿革頁與該次修正之公布／施行日期，"
    "調閱行為時有效之條文，並由承辦人覆核。"
)

_ARTICLE_PATTERN = re.compile(r"^(\d+)(?:-(\d+))?$")


class LawVersionError(ValueError):
    """快照或條號格式無法處理；不得以推測取代查證。"""


def normalize_article(article_no: str) -> str:
    """``第185條之3``／``第320條第1項``／``172-1`` → ``185-3``／``320``／``172-1``。"""

    text = str(article_no or "").strip()
    if not text:
        raise LawVersionError("條號不得為空")
    text = re.sub(r"^第\s*", "", text)
    text = text.split("第")[0]  # 去掉「第1項」「第2款」等後段
    text = text.replace("條", "").replace("之", "-").replace("　", "")
    text = text.strip(" -")
    match = _ARTICLE_PATTERN.fullmatch(text)
    if not match:
        raise LawVersionError(f"無法解析條號：{article_no!r}")
    main, sub = match.groups()
    return f"{main}-{sub}" if sub else main


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """回傳快照結構錯誤清單；空清單代表可用。"""

    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return ["快照必須是物件"]
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        errors.append(f"schema_version 必須為 {SNAPSHOT_SCHEMA}")
    if not str(snapshot.get("law_name", "")).strip():
        errors.append("law_name 不得為空")
    if not str(snapshot.get("pcode", "")).strip():
        errors.append("pcode 不得為空")
    source = snapshot.get("source")
    if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://"):
        errors.append("source.url 必須是官方 https 網址")
    amendments = snapshot.get("amendments")
    if not isinstance(amendments, list) or not amendments:
        errors.append("amendments 必須為非空清單")
        return errors
    if snapshot.get("amendment_count") != len(amendments):
        errors.append("amendment_count 與 amendments 長度不一致")
    previous: tuple[str, int] | None = None
    for index, item in enumerate(amendments):
        where = f"amendments[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} 必須是物件")
            continue
        if item.get("kind") not in {"ORIGINAL", "AMENDMENT"}:
            errors.append(f"{where}.kind 必須是 ORIGINAL 或 AMENDMENT")
        promulgated = _parse_date(item.get("promulgated_on"))
        if promulgated is None:
            errors.append(f"{where}.promulgated_on 格式錯誤")
        if item.get("effective_on") is not None and _parse_date(item.get("effective_on")) is None:
            errors.append(f"{where}.effective_on 格式錯誤")
        if item.get("effective_basis") not in {
            "EXPLICIT",
            "PUBLICATION_DAY",
            "PUBLICATION_DAY_DEFAULT",
            "MIXED",
        }:
            errors.append(f"{where}.effective_basis 不在允許值內")
        if item.get("effective_basis") == "MIXED" and item.get("effective_on") is not None:
            errors.append(f"{where}：MIXED 的 effective_on 必須為 null")
        for field in ("modified", "added", "deleted"):
            values = item.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not _ARTICLE_PATTERN.fullmatch(value)
                for value in values
            ):
                errors.append(f"{where}.{field} 必須是合法條號清單")
        if promulgated is not None:
            key = (promulgated.isoformat(), int(item.get("index", 0)))
            if previous is not None and key < previous:
                errors.append(f"{where}：amendments 未依公布日排序")
            previous = key
    if not any(item.get("kind") == "ORIGINAL" for item in amendments if isinstance(item, dict)):
        errors.append("amendments 必須包含一筆 ORIGINAL（制定公布）")
    return errors


def load_snapshot(path: Path | str | None = None) -> dict[str, Any]:
    return json.loads(Path(path or DEFAULT_SNAPSHOT_PATH).read_text(encoding="utf-8"))


# 目前只有刑法有官方沿革快照。別名集中在此，避免用模糊比對把特別法誤接上
# 刑法的修正紀錄（那會產生錯誤的行為時法判定）。
SNAPSHOT_LAW_ALIASES = frozenset({"刑法", "中華民國刑法"})


def matches_law(law_name: str) -> bool:
    """此法定名稱是否由本快照涵蓋（僅刑法）。"""

    return str(law_name or "").strip().replace(" ", "") in SNAPSHOT_LAW_ALIASES


@lru_cache(maxsize=1)
def get_snapshot() -> dict[str, Any]:
    """唯讀快照（行程內快取）。呼叫端不得修改回傳物件。"""

    snapshot = load_snapshot()
    errors = validate_snapshot(snapshot)
    if errors:
        raise LawVersionError("沿革快照無效：" + "；".join(errors))
    return snapshot


def clear_snapshot_cache() -> None:
    get_snapshot.cache_clear()


def _effective_key(item: dict[str, Any]) -> tuple[str, int]:
    return (
        str(item.get("effective_on") or item.get("promulgated_on") or ""),
        int(item.get("index", 0)),
    )


def article_events(snapshot: dict[str, Any], article: str) -> list[dict[str, Any]]:
    """回傳影響該條號的沿革事件（依生效日排序）。"""

    normalized = normalize_article(article)
    events: list[dict[str, Any]] = []
    for amendment in snapshot["amendments"]:
        deleted = normalized in amendment.get("deleted", [])
        added = normalized in amendment.get("added", [])
        modified = normalized in amendment.get("modified", [])
        if not (deleted or added or modified):
            continue
        kind = "DELETED" if deleted else ("ADDED" if added else "MODIFIED")
        events.append(
            {
                "index": amendment.get("index"),
                "type": kind,
                "promulgated_on": amendment.get("promulgated_on"),
                "effective_on": amendment.get("effective_on"),
                "effective_basis": amendment.get("effective_basis"),
                "official_text": amendment.get("text", ""),
            }
        )
    events.sort(key=_effective_key)
    return events


def _current_effective_from(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> str:
    changes = [event for event in events if event["type"] in {"ADDED", "MODIFIED"}]
    if changes:
        return str(changes[-1]["effective_on"] or changes[-1]["promulgated_on"])
    original = next(
        item for item in snapshot["amendments"] if item.get("kind") == "ORIGINAL"
    )
    return str(original.get("effective_on") or original.get("promulgated_on"))


def _original_change(amendment: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": amendment.get("index"),
        "type": "ORIGINAL",
        "promulgated_on": amendment.get("promulgated_on"),
        "effective_on": amendment.get("effective_on"),
        "official_text": amendment.get("text", ""),
    }


def _result(
    snapshot: dict[str, Any], article: str, event_date: str | None, status: str
) -> dict[str, Any]:
    return {
        "schema_version": AUDIT_SCHEMA,
        "status": status,
        "law_name": snapshot.get("law_name"),
        "pcode": snapshot.get("pcode"),
        "article": article,
        "event_date": event_date,
        "current_effective_from": None,
        "applicable_change": None,
        "next_change": None,
        "superseded_changes": [],
        "historical_text_required": False,
        "historical_text_in_repo": False,
        "official_history_url": (snapshot.get("source") or {}).get("url"),
        "snapshot_raw_sha256": (snapshot.get("source") or {}).get("raw_html_sha256"),
        "notes": [],
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }


def resolve(
    snapshot: dict[str, Any], article: str, event_date: str | None
) -> dict[str, Any]:
    """判定事件日當時應適用哪一版條文。

    回傳的 ``status`` 只有一個法律意義：是否需要另調行為時版本。所有結果都
    不是法律結論，須由承辦人覆核。
    """

    errors = validate_snapshot(snapshot)
    if errors:
        raise LawVersionError("快照無效：" + "；".join(errors))
    return _resolve_validated(snapshot, article, event_date)


def _resolve_validated(
    snapshot: dict[str, Any], article: str, event_date: str | None
) -> dict[str, Any]:
    normalized = normalize_article(article)
    parsed_event = _parse_date(event_date)
    events = article_events(snapshot, normalized)

    if parsed_event is None:
        result = _result(snapshot, normalized, None, STATUS_EVENT_UNKNOWN)
        result["historical_text_required"] = True
        result["notes"].append("事件日期缺漏或無法解析；不得以現行法推定行為時法。")
        return result

    result = _result(snapshot, normalized, parsed_event.isoformat(), STATUS_NO_RECORD)
    result["current_effective_from"] = _current_effective_from(snapshot, events)

    if not events:
        original = next(
            item for item in snapshot["amendments"] if item.get("kind") == "ORIGINAL"
        )
        in_force_since = _parse_date(original.get("effective_on")) or _parse_date(
            original.get("promulgated_on")
        )
        if in_force_since is not None and parsed_event < in_force_since:
            result["status"] = STATUS_NOT_YET
            result["next_change"] = _original_change(original)
            result["notes"].append(
                f"事件日早於本法制定施行日 {in_force_since.isoformat()}；當時尚無本法。"
            )
            return result
        result["status"] = STATUS_NO_RECORD
        result["notes"].append(
            "官方沿革頁未記載此條號之修正、增訂或刪除；現行文字推定為制定時原文。"
        )
        return result

    last_amended = _parse_date(snapshot.get("last_amended_on"))
    undated = [event for event in events if not event.get("effective_on")]
    if undated and (last_amended is None or parsed_event < last_amended):
        result["status"] = STATUS_INCOMPLETE
        result["historical_text_required"] = True
        result["notes"].append(
            "此條號涉及的修正有分段施行（effective_on 為 null），無法判定事件日當時版本；"
            + HISTORICAL_TEXT_WARNING
        )
        result["superseded_changes"] = undated
        return result

    active: dict[str, Any] | None = None
    for event in events:
        effective = _parse_date(event.get("effective_on")) or _parse_date(event.get("promulgated_on"))
        if effective is not None and effective <= parsed_event:
            active = event
    later = [
        event
        for event in events
        if (_parse_date(event.get("effective_on")) or _parse_date(event.get("promulgated_on")))
        > parsed_event
    ]

    first = events[0]
    if first["type"] == "ADDED" and active is None:
        result["status"] = STATUS_NOT_YET
        result["next_change"] = first
        result["notes"].append(
            f"此條號於 {first.get('effective_on') or first.get('promulgated_on')} 始增訂；"
            "事件日當時尚無本條，不得以現行法論罪。"
        )
        return result

    if active is None:
        original = next(
            item for item in snapshot["amendments"] if item.get("kind") == "ORIGINAL"
        )
        in_force_since = _parse_date(original.get("effective_on")) or _parse_date(
            original.get("promulgated_on")
        )
        if in_force_since is not None and parsed_event < in_force_since:
            result["status"] = STATUS_NOT_YET
            result["next_change"] = _original_change(original)
            result["notes"].append(
                f"事件日早於本法制定施行日 {in_force_since.isoformat()}；當時尚無本法。"
            )
            return result
        result["status"] = STATUS_HISTORICAL
        result["historical_text_required"] = True
        result["next_change"] = first
        result["superseded_changes"] = later
        result["notes"].append(
            "事件日早於此條號首次修正；行為時適用制定時原文，非現行文字。"
        )
        result["notes"].append(HISTORICAL_TEXT_WARNING)
        return result

    if active["type"] == "DELETED":
        result["status"] = STATUS_REPEALED
        result["applicable_change"] = active
        result["historical_text_required"] = True
        result["notes"].append(
            f"此條號於 {active.get('effective_on') or active.get('promulgated_on')} 刪除；"
            "事件日當時已無本條（或已非現行條號）。"
        )
        return result

    if later:
        result["status"] = STATUS_HISTORICAL
        result["applicable_change"] = active
        result["next_change"] = later[0]
        result["superseded_changes"] = later
        result["historical_text_required"] = True
        result["notes"].append(
            f"事件日之後此條號仍經 {len(later)} 次修正；現行文字不是行為時法。"
        )
        result["notes"].append(HISTORICAL_TEXT_WARNING)
        return result

    result["status"] = STATUS_CURRENT
    result["applicable_change"] = active
    result["notes"].append("事件日當時已為現行版本；仍須注意其他條文與競合之行為時法。")
    return result


def audit_articles(
    snapshot: dict[str, Any], event_date: str | None, articles: list[str]
) -> list[dict[str, Any]]:
    """批次判定；單一條號格式錯誤不會中斷其他條號。

    快照只驗證一次：呼叫端可能一次帶入整個罪章的條號（例如 20 條），逐條重驗
    會讓 58 筆沿革被反覆掃描。
    """

    errors = validate_snapshot(snapshot)
    if errors:
        raise LawVersionError("快照無效：" + "；".join(errors))
    results: list[dict[str, Any]] = []
    for article in articles:
        try:
            results.append(_resolve_validated(snapshot, article, event_date))
        except LawVersionError as exc:
            results.append(
                {
                    "schema_version": AUDIT_SCHEMA,
                    "status": "ARTICLE_UNPARSEABLE",
                    "article": str(article),
                    "event_date": event_date,
                    "message": str(exc),
                    "legal_conclusion": False,
                    "review_status": "HUMAN_REVIEW_REQUIRED",
                }
            )
    return results


SUMMARY_SCHEMA = "law-version-summary-v1"


def summarize(
    audits: list[dict[str, Any]], event_date: str | None, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """把逐條結果收斂成案件層摘要；不改變任何單條判定。"""

    by_status: dict[str, int] = {}
    for audit in audits:
        status = str(audit.get("status") or "UNKNOWN")
        by_status[status] = by_status.get(status, 0) + 1
    source = snapshot.get("source") or {}
    return {
        "schema_version": SUMMARY_SCHEMA,
        "status": "AUDIT_COMPLETED",
        "event_date": event_date or None,
        "article_count": len(audits),
        "by_status": by_status,
        "historical_text_required_count": sum(
            1 for audit in audits if audit.get("historical_text_required") is True
        ),
        "snapshot": {
            "law_name": snapshot.get("law_name"),
            "pcode": snapshot.get("pcode"),
            "amendment_count": snapshot.get("amendment_count"),
            "last_amended_on": snapshot.get("last_amended_on"),
            "official_history_url": source.get("url"),
            "raw_html_sha256": source.get("raw_html_sha256"),
        },
        "note": (
            "僅就官方沿革頁判斷事件日當時是否需要另調條文版本；"
            "不含歷史條文文字，也不作從舊從輕判斷。"
        ),
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }


def unavailable_summary(event_date: str | None, reason: str) -> dict[str, Any]:
    """沿革資料不可用時的摘要：明示未完成，不得視為「無須調閱」。"""

    return {
        "schema_version": SUMMARY_SCHEMA,
        "status": "AUDIT_UNAVAILABLE",
        "event_date": event_date or None,
        "article_count": 0,
        "by_status": {},
        "historical_text_required_count": 0,
        "reason": reason,
        "note": (
            "行為時法查對未完成（沿革資料無法讀取或格式不符）；"
            "不得以現行法推定行為時法，請人工確認。"
        ),
        "legal_conclusion": False,
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
