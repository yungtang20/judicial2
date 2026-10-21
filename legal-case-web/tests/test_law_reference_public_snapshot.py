from __future__ import annotations

from app.law_reference import get_cached_law_article


def test_cached_law_article_is_read_only_and_returns_verified_text():
    entry = get_cached_law_article("中華民國刑法", "第320條")
    assert entry is not None
    assert entry["article_content"]
    assert entry["dataset_version"]
    assert entry["abolished"] is False


def test_cached_law_article_returns_none_without_network_fallback():
    assert get_cached_law_article("不存在法規", "第99999條") is None
