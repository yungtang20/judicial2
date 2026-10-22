"""擷取官方「法規沿革」頁並產生可重現的歷史版本快照（2026-10-22 新增）。

用法：

    py -3 -X utf8 scripts/capture_law_amendment_history.py            # 抓取官方頁並更新快照
    py -3 -X utf8 scripts/capture_law_amendment_history.py --check    # 離線重解析，驗證快照未漂移
    py -3 -X utf8 scripts/capture_law_amendment_history.py --html X   # 從本機 HTML 產生快照

``--check`` 不連網：它重解析 ``data/sources`` 內的原始頁面，與
``data/law_amendment_history.json`` 逐欄位比對。只要兩者不一致就代表有人
手改快照或改了解析器，必須重新擷取並人工覆核。

本工具只記錄官方沿革頁明載的公布日、施行日與條號異動，**不重建歷史條文**。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.moj_law_history import (  # noqa: E402
    DEFAULT_SNAPSHOT_PATH,
    build_snapshot,
    fetch_history_html,
    write_snapshot,
)

RAW_DIR = ROOT / "data" / "sources"
DEFAULT_LAW_NAME = "中華民國刑法"
DEFAULT_PCODE = "C0000001"


def raw_path(pcode: str) -> Path:
    return RAW_DIR / f"moj_law_history_{pcode}.html"


def _summary(snapshot: dict, label: str) -> str:
    lines = [
        f"[{label}] {snapshot['law_name']}（pcode={snapshot['pcode']}）",
        f"  公布日：{snapshot['promulgated_on']}　修正日：{snapshot['last_amended_on']}",
        f"  修正次數：{snapshot['amendment_count']}",
        f"  原始頁面 bytes：{snapshot['source']['raw_html_bytes']}",
    ]
    for amendment in snapshot["amendments"][-2:]:
        lines.append(
            "  最新：{promulgated_on} 生效 {effective_on}（{effective_basis}）".format(
                **amendment
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="擷取法規沿革快照")
    parser.add_argument("--law-name", default=DEFAULT_LAW_NAME)
    parser.add_argument("--pcode", default=DEFAULT_PCODE)
    parser.add_argument("--check", action="store_true", help="離線驗證快照未漂移")
    parser.add_argument("--html", type=Path, help="從本機 HTML 檔產生快照（不連網）")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    target_snapshot = args.snapshot
    target_raw = raw_path(args.pcode)

    if args.check:
        if not target_raw.exists() or not target_snapshot.exists():
            print("找不到已提交的原始頁面或快照，無法離線驗證", file=sys.stderr)
            return 2
        rebuilt = build_snapshot(
            target_raw.read_bytes(), law_name=args.law_name, pcode=args.pcode
        )
        committed = json.loads(target_snapshot.read_text(encoding="utf-8"))
        if rebuilt != committed:
            print("快照漂移：重解析結果與已提交快照不一致", file=sys.stderr)
            differing = sorted(
                key
                for key in set(rebuilt) | set(committed)
                if rebuilt.get(key) != committed.get(key)
            )
            print("不一致欄位：" + "、".join(differing), file=sys.stderr)
            return 1
        print(_summary(rebuilt, "check-ok"))
        return 0

    if args.html:
        raw = args.html.read_bytes()
    else:
        raw = fetch_history_html(args.pcode)
    snapshot = build_snapshot(raw, law_name=args.law_name, pcode=args.pcode)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not args.html:
        target_raw.write_bytes(raw)
    write_snapshot(snapshot, target_snapshot)
    print(_summary(snapshot, "captured"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
