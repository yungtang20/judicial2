"""民國紀年日期格式化工具。

供 workflow（Gate 1 初始時間）、documents（筆錄、條陳）、UI 顯示共用。
輸入為 ISO datetime-local 字串（YYYY-MM-DDTHH:MM）或空白。
"""

from __future__ import annotations

from datetime import datetime


def format_roc_time(value: str) -> str:
    """2026-10-10T10:30 → 115年10月10日10時30分；空白 → 年月日時分；不可解析原樣返回。

    民國前（year < 1912）→ 標記「民國前N年」，避免輸出誤導性的「0年」。
    """
    if not value:
        return "年月日時分"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    roc_year = moment.year - 1911
    prefix = f"民國前{1911 - moment.year + 1}年" if moment.year < 1912 else f"{roc_year}年"
    return f"{prefix}{moment.month}月{moment.day}日{moment.hour}時{moment.minute:02d}分"


def format_roc_date(value: str) -> str:
    """2026-10-10T10:30 → 115年10月10日；空白 → 年月日；不可解析原樣返回。"""
    if not value:
        return "年月日"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    roc_year = moment.year - 1911
    prefix = f"民國前{1911 - moment.year + 1}年" if moment.year < 1912 else f"{roc_year}年"
    return f"{prefix}{moment.month}月{moment.day}日"
