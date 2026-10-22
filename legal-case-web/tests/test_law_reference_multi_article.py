"""題庫條號解析與多條法源快照解析（2026-10-22 新增）。

題庫的 ``source.article_no`` 除了單一條號，也用章節範圍表示（例如
``第100條至第119條``）。過去範圍字串被當成單一條號查詢，因此必定查無
資料，``/api/question-bank`` 會把整個罪章誤標為 NOT_FOUND。本檔鎖定
「先解析、再逐條查快照、任一缺漏即 fail-closed」的行為。
"""

from __future__ import annotations

import pytest

from app import law_reference as lr
from tests.helpers import BANK


def test_parse_single_article() -> None:
    assert lr.parse_article_spec("第320條") == ["320"]
    assert lr.parse_article_spec("320") == ["320"]


def test_parse_sub_numbered_article() -> None:
    assert lr.parse_article_spec("第172條之1") == ["172-1"]
    assert lr.parse_article_spec("第319-1條") == ["319-1"]


def test_parse_article_list() -> None:
    assert lr.parse_article_spec("第2條、第25條") == ["2", "25"]


def test_parse_article_range() -> None:
    assert lr.parse_article_spec("第100條至第119條") == [str(n) for n in range(100, 120)]


def test_parse_sub_numbered_range() -> None:
    assert lr.parse_article_spec("第172條之1至第172條之3") == ["172-1", "172-2", "172-3"]


def test_parse_range_ending_with_sub_number_keeps_main_article() -> None:
    # 「第74條至第75條之1」涵蓋第75條本身，不可只留 75-1。
    assert lr.parse_article_spec("第74條至第75條之1") == ["74", "75", "75-1"]


def test_parse_same_article_sub_numbered_range() -> None:
    assert lr.parse_article_spec("第319條至第319條之6") == [
        "319",
        "319-1",
        "319-2",
        "319-3",
        "319-4",
        "319-5",
        "319-6",
    ]


def test_parse_rejects_unbounded_or_invalid_specs() -> None:
    assert lr.parse_article_spec("") == []
    assert lr.parse_article_spec("沒有條號") == []
    # 展開超過上限時不得猜測，交由呼叫端標記 INVALID_SPEC。
    assert lr.parse_article_spec("第1條至第9999條") == []


def _write_cache(tmp_path, monkeypatch, cache: dict) -> None:
    monkeypatch.setattr(lr, "CACHE_PATH", tmp_path / "law_cache.json")
    lr.save_cache(cache)


def _entry(article_no: str, content: str = "條文內容") -> dict:
    return {
        "law_name": "中華民國刑法",
        "article_no": article_no,
        "article_content": content,
        "law_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=C0000001",
        "law_modified_date": "2026-07-22",
        "dataset_version": "2026-10-08",
        "abolished": False,
        "verified_at": "2026-10-22T00:00:00+00:00",
    }


def test_resolution_status_verified_partial_not_found(tmp_path, monkeypatch) -> None:
    _write_cache(
        tmp_path,
        monkeypatch,
        {
            "中華民國刑法:2": _entry("第2條", "第一段"),
            "中華民國刑法:25": _entry("第25條", "第二段"),
        },
    )
    assert lr.resolve_cached_articles("中華民國刑法", "第2條、第25條")["status"] == "VERIFIED_CACHE"
    partial = lr.resolve_cached_articles("中華民國刑法", "第2條、第26條")
    assert partial["status"] == "PARTIAL_CACHE"
    assert partial["missing"] == ["26"]
    assert lr.resolve_cached_articles("中華民國刑法", "第26條")["status"] == "NOT_FOUND"
    assert lr.resolve_cached_articles("中華民國刑法", "第?條")["status"] == "INVALID_SPEC"


def test_multi_article_lookup_is_fail_closed(tmp_path, monkeypatch) -> None:
    _write_cache(
        tmp_path,
        monkeypatch,
        {
            "中華民國刑法:100": _entry("第100條", "甲條"),
            "中華民國刑法:101": _entry("第101條", "乙條"),
        },
    )
    composite = lr.get_cached_law_article("中華民國刑法", "第100條至第101條")
    assert composite is not None
    assert composite["article_count"] == 2
    assert composite["article_no"] == "第100條至第101條"
    assert "第100條" in composite["article_content"]
    assert "乙條" in composite["article_content"]
    # 範圍內有一條缺漏時不得回傳殘缺法源。
    assert lr.get_cached_law_article("中華民國刑法", "第100條至第102條") is None


def test_abolished_article_inside_range_blocks_composite(tmp_path, monkeypatch) -> None:
    abolished = _entry("第101條", "已廢止")
    abolished["abolished"] = True
    _write_cache(
        tmp_path,
        monkeypatch,
        {"中華民國刑法:100": _entry("第100條"), "中華民國刑法:101": abolished},
    )
    assert lr.get_cached_law_article("中華民國刑法", "第100條至第101條") is None


def test_every_bank_source_spec_is_fully_cached() -> None:
    """題庫每個罪章的法源條號都必須在離線快照中完整解析。

    這是 2026-10-22 重測發現的缺陷鎖定：14 個罪章使用章節範圍，修正前
    一律被標成 NOT_FOUND。
    """

    missing: list[str] = []
    for offense in BANK["offenses"]:
        source = offense.get("source") or {}
        law_name, article_no = source.get("law_name"), source.get("article_no")
        if not (law_name and article_no):
            continue
        resolution = lr.resolve_cached_articles(law_name, article_no)
        if resolution["status"] != "VERIFIED_CACHE":
            missing.append(
                f"{offense['id']}: {law_name} {article_no} -> "
                f"{resolution['status']} missing={resolution['missing']}"
            )
    assert not missing, "法源快照未完整覆蓋題庫條號：\n" + "\n".join(missing)


def test_bank_related_articles_stay_offline_resolvable() -> None:
    """關聯法條必須能只靠快照解析，不得在測試中觸發網路。"""

    missing: list[str] = []
    for offense in BANK["offenses"]:
        for related in offense.get("source", {}).get("related_articles", []):
            entry = lr.get_cached_law_article(related["law_name"], related["article_no"])
            if entry is None:
                missing.append(f"{offense['id']}: {related['law_name']} {related['article_no']}")
    assert not missing, "關聯法條未進離線快照：\n" + "\n".join(missing)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("第141條之1", ["141-1"]),
        ("第201條至第205條", ["201", "202", "203", "204", "205"]),
    ],
)
def test_parser_representative_specs(spec: str, expected: list[str]) -> None:
    assert lr.parse_article_spec(spec) == expected
