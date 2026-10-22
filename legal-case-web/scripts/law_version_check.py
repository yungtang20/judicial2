"""行為時法查對 CLI（2026-10-22 新增）。

用法：

    py -3 -X utf8 scripts/law_version_check.py --article 第320條 --event-date 2010-01-05
    py -3 -X utf8 scripts/law_version_check.py --article 320 --article 185-3 \
        --event-date 2010-01-05 --json

輸出只說明「是否需要另調行為時版本」與應查的官方沿革紀錄，**不含條文文字**，
也不構成法律結論。判讀仍由承辦人為之。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.law_version import (  # noqa: E402
    STATUS_CURRENT,
    STATUS_HISTORICAL,
    STATUS_INCOMPLETE,
    STATUS_NO_RECORD,
    STATUS_NOT_YET,
    STATUS_REPEALED,
    audit_articles,
    load_snapshot,
)

_LABELS = {
    STATUS_CURRENT: "現行版本（事件日在最後一次修正生效之後）",
    STATUS_HISTORICAL: "須調閱行為時版本（事件日後仍有修正）",
    STATUS_NOT_YET: "事件日當時尚無本條",
    STATUS_REPEALED: "事件日當時本條已刪除",
    STATUS_NO_RECORD: "沿革頁無此條號異動紀錄（推定為制定時原文）",
    STATUS_INCOMPLETE: "沿革資料不足，須人工查證",
    "EVENT_DATE_UNKNOWN": "事件日期不明，須人工查證",
}


def _format(audit: dict) -> str:
    lines = [
        f"第 {audit.get('article')} 條（{audit.get('law_name')}）",
        f"  事件日：{audit.get('event_date') or '未提供'}",
        f"  判定：{_LABELS.get(audit.get('status'), audit.get('status'))}",
        f"  現行版本生效日：{audit.get('current_effective_from') or '未知'}",
    ]
    applicable = audit.get("applicable_change")
    if applicable:
        lines.append(
            "  行為時對應修正：{promulgated_on} 公布、{effective_on} 施行（{type}）".format(
                promulgated_on=applicable.get("promulgated_on"),
                effective_on=applicable.get("effective_on") or "未載明",
                type=applicable.get("type"),
            )
        )
        if applicable.get("official_text"):
            lines.append(f"  官方沿革原文：{applicable['official_text'][:120]}")
    nxt = audit.get("next_change")
    if nxt and nxt.get("official_text"):
        lines.append(f"  下一次異動：{nxt['official_text'][:120]}")
    for note in audit.get("notes", []):
        lines.append(f"  註：{note}")
    if audit.get("official_history_url"):
        lines.append(f"  官方沿革：{audit['official_history_url']}")
    lines.append("  狀態：僅供查對，非法律結論；須由承辦人覆核。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="行為時法查對")
    parser.add_argument("--article", action="append", required=True, help="可重複指定條號")
    parser.add_argument("--event-date", required=True, help="行為日（YYYY-MM-DD）")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args(argv)

    audits = audit_articles(load_snapshot(), args.event_date, args.article)
    if args.json:
        print(json.dumps(audits, ensure_ascii=False, indent=2))
    else:
        print("\n".join(_format(audit) for audit in audits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
