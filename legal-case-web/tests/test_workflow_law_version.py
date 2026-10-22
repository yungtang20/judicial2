"""行為時法接入案件流程的鎖定測試（2026-10-23 新增）。

``set_offenses`` 之後，每個已選罪章的刑法條號都必須留下「行為日當時是否
需要另調版本」的判定。這些判定：

- 只讀官方沿革快照，不重建歷史條文、不作從舊從輕；
- 一律 ``legal_conclusion: False``、``HUMAN_REVIEW_REQUIRED``；
- 沿革資料不可用時明示 ``AUDIT_UNAVAILABLE``，不得靜默當成「無須調閱」；
- 行為日或罪章變動後不得沿用舊判定。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import law_version, workflow
from app.law_version import STATUS_HISTORICAL
from app.workflow import apply_action, create_case
from tests.helpers import BANK, intake

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "law_amendment_history.json"


def _case_with_offense(event_time: str, offense: str = "theft") -> dict:
    raw = intake()
    raw["event_time"] = event_time
    case = create_case(raw, BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    return apply_action(
        case,
        "set_offenses",
        {
            "offense_ids": [offense],
            "legal_route_ids": [],
            "route_review_confirmed": True,
            "role": "victim",
        },
        BANK,
    )


def test_set_offenses_attaches_version_audit_per_article() -> None:
    case = _case_with_offense("2010-01-05T10:00")

    audits = case["law_version_audits"]
    assert len(audits) == 1, "竊盜只有單一主條文，應只有一筆判定"
    audit = audits[0]
    assert audit["offense_id"] == "theft"
    assert audit["article"] == "320"
    assert audit["article_no"] == "第320條"
    assert audit["status"] == STATUS_HISTORICAL
    assert audit["historical_text_required"] is True
    assert audit["legal_conclusion"] is False
    assert audit["review_status"] == "HUMAN_REVIEW_REQUIRED"


def test_summary_pins_official_history_provenance() -> None:
    case = _case_with_offense("2010-01-05T10:00")
    summary = case["law_version_summary"]

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert summary["status"] == "AUDIT_COMPLETED"
    assert summary["article_count"] == 1
    assert summary["by_status"] == {STATUS_HISTORICAL: 1}
    assert summary["historical_text_required_count"] == 1
    assert summary["legal_conclusion"] is False
    assert summary["review_status"] == "HUMAN_REVIEW_REQUIRED"
    assert summary["snapshot"]["law_name"] == "中華民國刑法"
    assert summary["snapshot"]["raw_html_sha256"] == snapshot["source"]["raw_html_sha256"]
    assert summary["snapshot"]["official_history_url"] == snapshot["source"]["url"]


def test_event_date_after_last_amendment_needs_no_historical_text() -> None:
    case = _case_with_offense("2026-10-10T10:30")
    audit = case["law_version_audits"][0]

    assert audit["status"] == law_version.STATUS_CURRENT
    assert audit["historical_text_required"] is False
    assert case["law_version_summary"]["historical_text_required_count"] == 0


def test_missing_event_time_is_reported_not_guessed() -> None:
    raw = intake()
    raw["event_time"] = ""
    case = create_case(raw, BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(
        case,
        "set_offenses",
        {
            "offense_ids": ["theft"],
            "legal_route_ids": [],
            "route_review_confirmed": True,
            "role": "victim",
        },
        BANK,
    )

    # 行為日不明時仍逐條留下判定，狀態必須是「行為日不明、須人工查證」，
    # 不得因為沒有日期就跳過查對或推定為現行法。
    assert len(case["law_version_audits"]) == 1
    audit = case["law_version_audits"][0]
    assert audit["status"] == law_version.STATUS_EVENT_UNKNOWN
    assert audit["historical_text_required"] is True
    summary = case["law_version_summary"]
    assert summary["status"] == "AUDIT_COMPLETED"
    assert summary["historical_text_required_count"] == 1
    assert summary["legal_conclusion"] is False


def test_unavailable_snapshot_does_not_break_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> dict:
        raise law_version.LawVersionError("快照毀損")

    monkeypatch.setattr(law_version, "get_snapshot", boom)
    case = _case_with_offense("2010-01-05T10:00")

    assert case["law_version_audits"] == []
    summary = case["law_version_summary"]
    assert summary["status"] == "AUDIT_UNAVAILABLE"
    assert summary["reason"] == "LawVersionError"
    assert summary["note"].startswith("行為時法查對未完成")
    events = [entry["event"] for entry in case["audit"]]
    assert "LAW_VERSION_AUDIT_UNAVAILABLE" in events


def test_audit_cap_truncates_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow, "MAX_VERSION_AUDIT_ARTICLES", 0)
    case = _case_with_offense("2010-01-05T10:00")

    summary = case["law_version_summary"]
    assert case["law_version_audits"] == []
    assert summary["truncated"] is True
    assert summary["skipped"], "被略過的條號必須列出，不得靜默丟棄"


def test_update_gate1_clears_stale_version_audits() -> None:
    case = _case_with_offense("2010-01-05T10:00")
    assert case["law_version_audits"]

    case = apply_action(
        case,
        "update_gate1",
        {"gate1": {"times": ["2011-01-01T00:00"]}},
        BANK,
    )

    assert case["selected_offenses"] == []
    assert case["law_version_audits"] == []
    assert case["law_version_summary"] is None
    assert case["temporal_law_warnings"] == []


def test_version_audit_is_cleared_by_reselecting_offenses() -> None:
    case = _case_with_offense("2010-01-05T10:00")
    case = apply_action(
        case,
        "set_offenses",
        {
            "offense_ids": ["theft"],
            "legal_route_ids": [],
            "route_review_confirmed": True,
            "role": "victim",
        },
        BANK,
    )
    assert len(case["law_version_audits"]) == 1, "重選罪章不得累加舊判定"
