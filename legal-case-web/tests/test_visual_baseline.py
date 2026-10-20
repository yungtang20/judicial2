"""visual_baseline 工具單元測試：只測純函數，不啟動伺服器或瀏覽器。

契約：
- diff_ratio：尺寸不同一律回 size_match=False 且 ratio=None；全黑圖可計算。
- compare：approved 基準不存在必須列 MISSING_BASELINE 並判定不通過；
  本工具不得自行「核准」任何基準。
- 擴充覆蓋（2026-10-20）：compare 涵蓋首頁、Gate 1、Gate 2 三組視口共九張。
- 資產 hash 綁定：capture 產出 STATUS.json 必須包含 app.js/index.html/styles.css SHA-256。
- 動態 ID 遮罩：capture 必須遮罩 session-token meta、#case-heading、#qa-progress。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.visual_baseline import (
    STATUS,
    _DYNAMIC_MASK_SELECTORS,
    _STATIC_ASSETS,
    _asset_hashes,
    compare,
    diff_ratio,
    render_report,
)


def _png(path: Path, color, size=(4, 4)) -> None:
    from PIL import Image

    Image.new("RGB", size, color).save(path, format="PNG")


@pytest.fixture()
def image_dirs(tmp_path):
    cand = tmp_path / "candidate"
    appr = tmp_path / "approved"
    cand.mkdir()
    appr.mkdir()
    return cand, appr


def test_diff_ratio_flags_size_mismatch_without_ratio(image_dirs):
    cand, appr = image_dirs
    _png(cand / "d.png", (0, 0, 0), size=(4, 4))
    _png(appr / "d.png", (0, 0, 0), size=(6, 4))
    info = diff_ratio(appr / "d.png", cand / "d.png")
    assert info["size_match"] is False
    assert info["ratio"] is None


def test_diff_ratio_same_image_is_zero(image_dirs):
    cand, _ = image_dirs
    _png(cand / "same.png", (12, 34, 56))
    info = diff_ratio(cand / "same.png", cand / "same.png")
    assert info["size_match"] is True
    assert info["ratio"] == 0.0


def test_compare_requires_approved_baseline(image_dirs):
    cand, _ = image_dirs
    _png(cand / "desktop.png", (0, 0, 0))
    _png(cand / "gate1_desktop.png", (0, 0, 0))
    report = compare(cand, cand.parent / "approved", 0.02)
    assert report["pass"] is False
    assert all(item["status"] == "MISSING_BASELINE" for item in report["results"])
    # 首頁、Gate 1、Gate 2 三組視口都在比對範圍內
    expected = {"desktop", "gate1_desktop", "gate2_desktop"}
    assert expected <= {item["viewport"] for item in report["results"]}


def test_compare_within_and_exceeding_threshold(image_dirs):
    cand, appr = image_dirs
    for name in (
        "desktop", "tablet", "mobile",
        "gate1_desktop", "gate1_tablet", "gate1_mobile",
        "gate2_desktop", "gate2_tablet", "gate2_mobile",
    ):
        _png(appr / f"{name}.png", (0, 0, 0))
        _png(cand / f"{name}.png", (4, 4, 4))  # 每像素差 4/255 ≈ 0.0157
    small = compare(cand, appr, 0.02)
    assert small["pass"] is True
    assert small["results"][0]["status"] == "WITHIN_THRESHOLD"
    strict = compare(cand, appr, 0.001)
    assert strict["pass"] is False
    assert strict["results"][0]["status"] == "EXCEEDS_THRESHOLD"


def test_compare_includes_gate2_viewports(image_dirs):
    cand, appr = image_dirs
    for name in (
        "desktop", "tablet", "mobile",
        "gate1_desktop", "gate1_tablet", "gate1_mobile",
        "gate2_desktop", "gate2_tablet", "gate2_mobile",
    ):
        _png(appr / f"{name}.png", (0, 0, 0))
        _png(cand / f"{name}.png", (0, 0, 0))
    report = compare(cand, appr, 0.02)
    assert report["pass"] is True
    assert len(report["results"]) == 9
    gate2_names = {item["viewport"] for item in report["results"] if item["viewport"].startswith("gate2_")}
    assert gate2_names == {"gate2_desktop", "gate2_tablet", "gate2_mobile"}


def test_asset_hashes_cover_static_assets():
    hashes = _asset_hashes()
    for rel in _STATIC_ASSETS:
        assert rel in hashes, f"asset hash missing: {rel}"
        # 每個 hash 必須是 64 位十六進位或 MISSING
        assert len(hashes[rel]) == 64 or hashes[rel] == "MISSING"


def test_dynamic_mask_selectors_cover_session_token_and_dynamic_ids():
    # 遮罩清單必須涵蓋 session-token meta、case-heading、qa-progress
    assert 'meta[name="session-token"]' in _DYNAMIC_MASK_SELECTORS
    assert "#case-heading" in _DYNAMIC_MASK_SELECTORS
    assert "#qa-progress" in _DYNAMIC_MASK_SELECTORS


def test_render_report_never_claims_human_approval(image_dirs):
    cand, _ = image_dirs
    report = compare(cand, cand.parent / "approved", 0.02)
    text = render_report(report)
    assert "REGRESSION_DETECTED" in text
    assert "視覺回歸比對報告" in text
    # 工具本身不得宣告基準已核准
    assert STATUS == "UNAPPROVED_CANDIDATE"
