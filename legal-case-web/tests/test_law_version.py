"""行為時法判定與沿革解析的鎖定測試（2026-10-22 新增）。

三層驗證：
1. 沿革頁解析（中文數字、條號範圍、分段施行、制定公布）。
2. 已提交快照與 ``data/sources`` 原始頁面的一致性（離線可重現）。
3. ``resolve`` 對真實刑法沿革的判定，以及合成快照的邊界情境。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import law_version, moj_law_history
from app.law_version import (
    STATUS_CURRENT,
    STATUS_HISTORICAL,
    STATUS_INCOMPLETE,
    STATUS_NO_RECORD,
    STATUS_NOT_YET,
    STATUS_REPEALED,
)
from app.moj_law_history import (
    LawHistoryParseError,
    expand_article_list,
    parse_chinese_number,
    parse_history_html,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "sources" / "moj_law_history_C0000001.html"
SNAPSHOT_PATH = ROOT / "data" / "law_amendment_history.json"


# ---------------------------------------------------------------- 解析器


@pytest.mark.parametrize(
    ("text", "expected"),
    [("十", 10), ("二十四", 24), ("三十五", 35), ("七十九", 79), ("九十八", 98), ("一百十五", 115), ("一百十", 110)],
)
def test_chinese_numbers(text: str, expected: int) -> None:
    assert parse_chinese_number(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10、61", ["10", "61"]),
        ("315-2", ["315-2"]),
        ("274～279", ["274", "275", "276", "277", "278", "279"]),
        ("74～75-1", ["74", "75", "75-1"]),
        ("42-1～42-3", ["42-1", "42-2", "42-3"]),
        ("80", ["80"]),
    ],
)
def test_article_list_expansion(text: str, expected: list[str]) -> None:
    assert expand_article_list(text) == expected


def test_article_list_rejects_abnormal_range() -> None:
    with pytest.raises(LawHistoryParseError):
        expand_article_list("279～274")


SYNTHETIC_HTML = """
<table>
<tr id="trLNODate"><th>公布日期：</th><td>民國 24 年 01 月 01 日 </td></tr>
<tr id="trLNNDate"><th>修正日期：</th><td>民國 115 年 07 月 22 日 </td></tr>
</table>
<div class="col-data text-pre">1. 中華民國二十四年一月一日國民政府制定公布全文 357 條；
並自二十四年七月一日施行</div>
<div class="col-data text-pre">2. 中華民國九十八年六月十日總統令修
正公布第 42、74～75-1 條條文；增訂第 42-1 條條文；其中第 42 條條文自公布日施行；
第 42-1、74～75-1 條條文自九十八年九月一日施行</div>
<div class="col-data text-pre">3. 中華民國一百零八年五月二十九日總統令修正公布第 320 條條文</div>
"""


def test_parse_history_html_handles_original_split_effective_and_default_day() -> None:
    snapshot = parse_history_html(
        SYNTHETIC_HTML, law_name="測試法", pcode="T0000001"
    )
    assert snapshot["promulgated_on"] == "1935-01-01"
    assert snapshot["last_amended_on"] == "2026-07-22"
    assert snapshot["amendment_count"] == 3
    original, mixed, default_day = snapshot["amendments"]
    assert original["kind"] == "ORIGINAL"
    assert original["article_count"] == 357
    assert original["effective_on"] == "1935-07-01"
    assert mixed["effective_basis"] == "MIXED"
    assert mixed["effective_on"] is None
    assert mixed["modified"] == ["42", "74", "75", "75-1"]
    assert mixed["added"] == ["42-1"]
    # 未載施行日者依中央法規標準法第 13 條，公布日 +2 日生效。
    assert default_day["effective_basis"] == "PUBLICATION_DAY_DEFAULT"
    assert default_day["promulgated_on"] == "2019-05-29"
    assert default_day["effective_on"] == "2019-05-31"
    assert default_day["modified"] == ["320"]


def test_parse_history_html_fails_closed_on_unrecognised_entry() -> None:
    html = SYNTHETIC_HTML + '<div class="col-data text-pre">4. 中華民國一百年一月一日總統令</div>'
    with pytest.raises(LawHistoryParseError):
        parse_history_html(html, law_name="測試法", pcode="T0000001")


# ---------------------------------------------------------------- 快照完整性


def test_committed_snapshot_matches_raw_official_page() -> None:
    raw = RAW_PATH.read_bytes()
    rebuilt = moj_law_history.build_snapshot(
        raw, law_name="中華民國刑法", pcode="C0000001"
    )
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert rebuilt == committed


def test_committed_snapshot_is_valid_and_complete() -> None:
    snapshot = law_version.load_snapshot()
    assert law_version.validate_snapshot(snapshot) == []
    assert snapshot["law_name"] == "中華民國刑法"
    assert snapshot["amendment_count"] >= 50
    assert snapshot["source"]["url"].startswith("https://law.moj.gov.tw/")
    assert len(snapshot["source"]["raw_html_sha256"]) == 64


def test_snapshot_rejects_tampering() -> None:
    snapshot = json.loads(json.dumps(law_version.load_snapshot()))
    snapshot["amendment_count"] += 1
    assert any("amendment_count" in error for error in law_version.validate_snapshot(snapshot))
    with pytest.raises(law_version.LawVersionError):
        law_version.resolve(snapshot, "320", "2020-01-01")


# ---------------------------------------------------------------- 條號正規化


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("第320條", "320"),
        ("320", "320"),
        ("第185條之3", "185-3"),
        ("第320條第1項", "320"),
        ("第172條之1第2項", "172-1"),
        (" 第 42 條 ", "42"),
    ],
)
def test_normalize_article(raw: str, expected: str) -> None:
    assert law_version.normalize_article(raw) == expected


@pytest.mark.parametrize("raw", ["", "第條", "abc", "第320條之x"])
def test_normalize_article_rejects_unparseable(raw: str) -> None:
    with pytest.raises(law_version.LawVersionError):
        law_version.normalize_article(raw)


# ---------------------------------------------------------------- 真實沿革判定


def test_added_article_did_not_exist_before_1999() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "第185條之3", "1998-01-01")
    assert audit["status"] == STATUS_NOT_YET
    assert audit["next_change"]["effective_on"] == "1999-04-23"
    assert audit["legal_conclusion"] is False
    assert audit["review_status"] == "HUMAN_REVIEW_REQUIRED"


def test_article_320_in_2010_applies_the_original_text() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "第320條", "2010-01-05")
    assert audit["status"] == STATUS_HISTORICAL
    assert audit["applicable_change"] is None
    assert audit["next_change"]["index"] == 38
    assert audit["next_change"]["effective_on"] == "2019-05-31"
    assert audit["historical_text_required"] is True
    assert audit["historical_text_in_repo"] is False
    assert len(audit["superseded_changes"]) == 1
    assert "article_content" not in audit


def test_article_320_after_2019_amendment_is_current() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "第320條", "2020-01-01")
    assert audit["status"] == STATUS_CURRENT
    assert audit["applicable_change"]["index"] == 38
    assert audit["historical_text_required"] is False


def test_event_before_the_statute_existed() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "320", "1930-01-01")
    assert audit["status"] == STATUS_NOT_YET


def test_article_without_amendment_record_is_reported_as_such() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "第9條", "2010-01-05")
    assert audit["status"] == STATUS_NO_RECORD
    assert "官方沿革頁未記載" in " ".join(audit["notes"])


def test_missing_event_date_is_never_guessed() -> None:
    audit = law_version.resolve(law_version.load_snapshot(), "320", "")
    assert audit["status"] == "EVENT_DATE_UNKNOWN"
    assert audit["historical_text_required"] is True


def test_audit_articles_keeps_going_after_bad_input() -> None:
    audits = law_version.audit_articles(
        law_version.load_snapshot(), "2010-01-05", ["第320條", "無法解析", "第9條"]
    )
    assert [audit["status"] for audit in audits] == [
        STATUS_HISTORICAL,
        "ARTICLE_UNPARSEABLE",
        STATUS_NO_RECORD,
    ]


# ---------------------------------------------------------------- 合成快照邊界


def _synthetic_snapshot(amendments: list[dict], last_amended: str = "2020-12-31") -> dict:
    return {
        "schema_version": "law-amendment-history-v1",
        "law_name": "測試法",
        "pcode": "T0000001",
        "promulgated_on": "1935-01-01",
        "last_amended_on": last_amended,
        "amendment_count": len(amendments),
        "effective_rule": "測試",
        "amendments": amendments,
        "source": {
            "provider": "測試",
            "url": "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode=T0000001",
            "raw_html_sha256": "0" * 64,
            "raw_html_bytes": 1,
            "parser": "test",
        },
        "unknowns": [],
    }


def _original() -> dict:
    return {
        "index": 1,
        "kind": "ORIGINAL",
        "promulgated_on": "1935-01-01",
        "effective_on": "1935-07-01",
        "effective_basis": "EXPLICIT",
        "article_count": 357,
        "modified": [],
        "added": [],
        "deleted": [],
        "text": "制定公布全文 357 條",
    }


def _amendment(index: int, promulgated: str, effective: str | None, **changes) -> dict:
    base = {
        "index": index,
        "kind": "AMENDMENT",
        "promulgated_on": promulgated,
        "effective_on": effective,
        "effective_basis": "EXPLICIT" if effective else "MIXED",
        "article_count": None,
        "modified": [],
        "added": [],
        "deleted": [],
        "text": "測試修正",
    }
    base.update(changes)
    return base


def test_deleted_article_is_reported_as_out_of_force() -> None:
    snapshot = _synthetic_snapshot(
        [
            _original(),
            _amendment(2, "2010-01-01", "2010-01-03", modified=["320"]),
            _amendment(3, "2020-01-01", "2020-01-03", deleted=["320"]),
        ]
    )
    audit = law_version.resolve(snapshot, "320", "2021-01-01")
    assert audit["status"] == STATUS_REPEALED
    assert audit["applicable_change"]["index"] == 3


def test_mixed_effective_dates_before_last_amendment_are_incomplete() -> None:
    snapshot = _synthetic_snapshot(
        [_original(), _amendment(2, "2010-01-01", None, modified=["320"])],
        last_amended="2020-12-31",
    )
    audit = law_version.resolve(snapshot, "320", "2015-01-01")
    assert audit["status"] == STATUS_INCOMPLETE
    assert audit["historical_text_required"] is True


def test_event_before_first_amendment_requires_original_text() -> None:
    snapshot = _synthetic_snapshot(
        [_original(), _amendment(2, "2010-01-01", "2010-01-03", modified=["320"])]
    )
    audit = law_version.resolve(snapshot, "320", "2000-01-01")
    assert audit["status"] == STATUS_HISTORICAL
    assert audit["applicable_change"] is None
    assert audit["next_change"]["index"] == 2


def test_synthetic_snapshot_is_valid() -> None:
    snapshot = _synthetic_snapshot([_original()])
    assert law_version.validate_snapshot(snapshot) == []
