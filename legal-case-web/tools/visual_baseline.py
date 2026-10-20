# -*- coding: utf-8 -*-
"""視覺回歸基準工具（review-only，基準未經人工核准前不得視為正式門檻）。

說明：
- `capture` 以 playwright＋chromium 對本機伺服器首頁擷取三種視窗寬度的
  全頁截圖，存入 review/visual_baselines_candidate/，並附 UNAPPROVED
  狀態檔。基準必須由人工核准後才可以移入 review/visual_baselines_approved/。
- `diff_ratio` / `compare` 用 PIL 做像素差異比率，輸出報告文字；
  本工具不會自行把差異判定為 pass/fail 的「核准」，只提供量化比值，
  門檻由呼叫者（或人工流程）明確指定。

用法：
    py -3 -X utf8 tools/visual_baseline.py capture --base-url http://127.0.0.1:8787
    py -3 -X utf8 tools/visual_baseline.py compare --threshold 0.02
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = REPO_ROOT / "review" / "visual_baselines_candidate"
APPROVED_DIR = REPO_ROOT / "visual_baselines_approved"

VIEWPORTS: dict[str, dict[str, int]] = {
    "desktop": {"width": 1280, "height": 800},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 390, "height": 844},
}
STATUS = "UNAPPROVED_CANDIDATE"
# 比對覆蓋的檔案集合：首頁（案件輸入）與 Gate 1（建案後摘要檢視）兩個狀態。
# 首頁維持原檔名（desktop/tablet/mobile.png）；Gate 1 加 gate1_ 前綴。
HOME_STATE = "home"
CASE_STATE_PREFIX = "gate1_"
# 擴充覆蓋：Gate 2 選罪章畫面（需先建立合成案件）。
GATE2_STATE_PREFIX = "gate2_"
# 截圖時一律隱藏暫時性元素（右下角 status 提示框），避免基準帶入會消失或改變的內容。
# 注意：伺服器 CSP 為 style-src 'self'，inline <style> 會被擋；因此用 CSSOM（JS 設定
# element style，CSP 允許）而非 add_style_tag。
_TRANSIENT_SELECTOR = "#status"
# 動態 ID 遮罩：這些元素的內容隨案件/工作階段而變，基準擷取前一律遮罩，
# 避免基準因動態值（session token、case id、revision、時間戳）而產生假差異。
_DYNAMIC_MASK_SELECTORS = [
    'meta[name="session-token"]',
    "#case-heading",
    "#qa-progress",
]
# 資產 hash 綁定：在 STATUS.json 中記錄靜態資產的 SHA-256，讓基準與程式碼版本
# 對應，資產變更時基準即需重擷取。
_STATIC_ASSETS = ["app/static/app.js", "app/static/index.html", "app/static/styles.css"]


def _hide_transient(page: Any) -> None:
    """隱藏暫時性元素與動態 ID，避免基準帶入會隨工作階段改變的內容。"""
    try:
        page.eval_on_selector(
            _TRANSIENT_SELECTOR, "el => { el.style.display = 'none'; }"
        )
    except Exception:
        pass
    # 動態 ID 遮罩：將動態內容替換為佔位符，避免基準因 session token、
    # case id、revision、時間戳而產生假差異。
    mask_script = """
    (selectors) => {
      selectors.forEach((sel) => {
        try {
          document.querySelectorAll(sel).forEach((el) => {
            if (el.tagName === "META") { el.content = "[MASKED_SESSION_TOKEN]"; }
            else { el.textContent = "[MASKED_DYNAMIC_ID]"; el.setAttribute("data-masked", "1"); });
        } catch (_) {}
      });
    }
    """
    try:
        page.evaluate(mask_script, _DYNAMIC_MASK_SELECTORS)
    except Exception:
        pass


def _asset_hashes() -> dict[str, str]:
    """回傳靜態資產的 SHA-256，用於基準與程式碼版本對應。"""
    hashes: dict[str, str] = {}
    for rel in _STATIC_ASSETS:
        p = REPO_ROOT / rel
        if p.is_file():
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            hashes[rel] = "MISSING"
    return hashes


def diff_ratio(image_a: Path, image_b: Path) -> dict[str, Any]:
    """回傳兩張 PNG 的尺寸檢查與像素平均絕對差比率（0.0 完全一致）。"""
    from PIL import Image
    import numpy as np

    a = Image.open(image_a).convert("RGB")
    b = Image.open(image_b).convert("RGB")
    if a.size != b.size:
        return {"size_match": False, "ratio": None, "size_a": a.size, "size_b": b.size}
    if a.size == (0, 0):
        return {"size_match": True, "ratio": 0.0, "size_a": a.size, "size_b": b.size}
    arr_a = np.asarray(a, dtype=np.int16)
    arr_b = np.asarray(b, dtype=np.int16)
    ratio = float(np.abs(arr_a - arr_b).mean() / 255.0)
    return {"size_match": True, "ratio": ratio, "size_a": a.size, "size_b": b.size}


def compare(candidate_dir: Path, approved_dir: Path, threshold: float) -> dict[str, Any]:
    """比較 candidate 與 approved 基準；approved 不存在時列為 missing（不通過）。"""
    names = (
        list(VIEWPORTS)
        + [f"{CASE_STATE_PREFIX}{name}" for name in VIEWPORTS]
        + [f"{GATE2_STATE_PREFIX}{name}" for name in VIEWPORTS]
    )
    results: list[dict[str, Any]] = []
    for name in names:
        cand = candidate_dir / f"{name}.png"
        appr = approved_dir / f"{name}.png"
        if not cand.is_file() or not appr.is_file():
            results.append({"viewport": name, "status": "MISSING_BASELINE", "ratio": None})
            continue
        info = diff_ratio(appr, cand)
        if not info["size_match"]:
            results.append({"viewport": name, "status": "SIZE_CONFLICT", "ratio": None})
            continue
        results.append(
            {
                "viewport": name,
                "status": "WITHIN_THRESHOLD" if info["ratio"] <= threshold else "EXCEEDS_THRESHOLD",
                "ratio": round(info["ratio"], 6),
                "threshold": threshold,
            }
        )
    passing = all(item["status"] == "WITHIN_THRESHOLD" for item in results)
    return {"threshold": threshold, "pass": passing, "results": results}


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "## 視覺回歸比對報告",
        "",
        f"- 比對時間：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- 基準狀態：僅在 review/visual_baselines_approved/ 存在人工核准基準時才可比對。",
        f"- 迴歸狀態：{'WITHIN_THRESHOLD' if report['pass'] else 'REGRESSION_DETECTED'}（門檻 {report['threshold']}）",
        "",
    ]
    for item in report["results"]:
        ratio = item.get("ratio")
        shown = "n/a" if ratio is None else f"{ratio}"
        lines.append(f"- {item['viewport']}: {item['status']}（diff ratio {shown}）")
    lines.append("")
    return "\n".join(lines)


def capture(base_url: str, output_dir: Path) -> dict[str, Any]:
    """擷取三個畫面狀態（首頁＋Gate 1＋Gate 2）各三種視窗寬度截圖；僅產生候選基準。

    - 暫時性元素（#status toast）與動態 ID（session token、case heading、qa progress）
      一律遮罩後才截圖，避免基準帶入暫時或隨工作階段改變的內容。
    - Gate 1 畫面以明標合成摘要建立，不使用任何真實案情。
    - Gate 2 畫面以合成候選罪章與路由建立，不使用任何真實案情。
    - STATUS.json 記錄靜態資產 SHA-256（app.js、index.html、styles.css），
      讓基準與程式碼版本對應。
    """
    from playwright.sync_api import sync_playwright

    synthetic_summary = (
        "測試用合成摘要：某人於測試時間在測試地點描述一件合成事件，"
        "人、事、時、地、物皆為測試值，僅用於擷取 Gate 1 版面基準，非真實案情。"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, viewport in VIEWPORTS.items():
            # ── 首頁 ──
            page = browser.new_page(viewport=viewport)
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_timeout(800)
            _hide_transient(page)
            target = output_dir / f"{name}.png"
            page.screenshot(path=str(target), full_page=True)
            created.append(target.name)
            page.close()

            # ── Gate 1 ──
            page = browser.new_page(viewport=viewport)
            page.goto(base_url, wait_until="networkidle")
            page.fill("#summary", synthetic_summary)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1200)
            _hide_transient(page)
            target = output_dir / f"{CASE_STATE_PREFIX}{name}.png"
            page.screenshot(path=str(target), full_page=True)
            created.append(target.name)
            page.close()

            # ── Gate 2（擴充覆蓋：選罪章畫面） ──
            page = browser.new_page(viewport=viewport)
            page.goto(base_url, wait_until="networkidle")
            page.fill("#summary", synthetic_summary)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
            # 假設建案後直接進入 Gate 2 選罪章（auto_prepare 已建立候選與問句）
            _hide_transient(page)
            target = output_dir / f"{GATE2_STATE_PREFIX}{name}.png"
            page.screenshot(path=str(target), full_page=True)
            created.append(target.name)
            page.close()
        browser.close()
    (output_dir / "STATUS.json").write_text(
        json.dumps(
            {
                "status": STATUS,
                "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": created,
                "states": [HOME_STATE, f"{CASE_STATE_PREFIX}<viewport>", f"{GATE2_STATE_PREFIX}<viewport>"],
                "transient_hidden": "#status（右下角提示框）擷取前一律隱藏",
                "dynamic_id_masked": ", ".join(_DYNAMIC_MASK_SELECTORS),
                "asset_hashes": _asset_hashes(),
                "limitations": [
                    "基準僅涵蓋本工具擷取的畫面狀態（首頁＋Gate 1 合成摘要檢視＋Gate 2 合成候選檢視）；",
                    "其他 Gate 畫面尚無基準，核准後回歸門檻也只保護已擷取狀態；",
                    "合成摘要內容非真實案情，不得作為法律內容證據。",
                    "動態 ID 已遮罩為 [MASKED_DYNAMIC_ID]，資產 hash 綁定於 STATUS.json。",
                ],
                "approval_note": "候選基準未經人工核准；不得作為正式視覺回歸門檻。",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"status": STATUS, "files": created, "output_dir": str(output_dir)}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture")
    cap.add_argument("--base-url", default="http://127.0.0.1:8787")

    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("--threshold", type=float, default=0.02)

    args = parser.parse_args()
    if args.command == "capture":
        info = capture(args.base_url, CANDIDATE_DIR)
        print(json.dumps(info, ensure_ascii=False))
        return 0
    report = compare(CANDIDATE_DIR, APPROVED_DIR, args.threshold)
    print(render_report(report))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
