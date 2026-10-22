"""全國法規資料庫「法規沿革」頁的解析與快照擷取（2026-10-22 新增）。

用途：補上題庫 ``verification_note`` 一直寫著的系統性缺口——「行為時法
（歷史版本）仍須由承辦人依官方修正歷程確認」。本模組只處理**官方沿革頁
已明載的事實**：每次修正的公布日、施行日，以及被修正／增訂／刪除的條號。
它不重建歷史條文，也不判斷從舊從輕。

來源：``https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode=<pcode>``
（全國法規資料庫，法務部）。頁面以民國紀年與中文數字記載日期。

TLS 注意：Python 3.13 起 ``create_default_context()`` 預設啟用
``VERIFY_X509_STRICT``，對本站憑證會因缺少 Subject Key Identifier 而失敗。
本模組只關閉嚴格延伸檢查，**不關閉憑證鏈驗證**。

生效日規則：頁面明載「並自…施行」者記為 ``EXPLICIT``；明載「自公布日
施行」或未載施行日者，依中央法規標準法第 13 條「自公布之日起算至第三日
起發生效力」記為 ``PUBLICATION_DAY`` 並以公布日 +2 日推算；同一修正有
多個不同施行日時記為 ``MIXED``，``effective_on`` 留空，交由解析器標記
``VERSION_HISTORY_INCOMPLETE``。
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.request
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from typing import Any

HISTORY_URL = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"
USER_AGENT = "judicial2-law-history/1.0"
SNAPSHOT_SCHEMA = "law-amendment-history-v1"
PARSER_ID = "moj_law_history_v1"
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "law_amendment_history.json"
)
EFFECTIVE_RULE = "中央法規標準法第13條：自公布之日起算至第三日起發生效力"

_DIGITS = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_DATE_PATTERN = re.compile(
    r"(?:中華民國)?\s*([0-9〇○零一二三四五六七八九十百千]+)\s*年\s*"
    r"([0-9〇○零一二三四五六七八九十百千]+)\s*月\s*"
    r"([0-9〇○零一二三四五六七八九十百千]+)\s*日"
)
_ROC_PREFIXED_DATE_PATTERN = re.compile(
    r"(?:中華)?民國\s*([0-9〇○零一二三四五六七八九十百千]+)\s*年\s*"
    r"([0-9〇○零一二三四五六七八九十百千]+)\s*月\s*"
    r"([0-9〇○零一二三四五六七八九十百千]+)\s*日"
)
_ROW_PATTERN = re.compile(
    r'<div class="col-data text-pre">(.*?)</div>', re.S | re.I
)
_ARTICLE_ACTION = re.compile(
    r"(修正公布|增訂公布|增訂|刪除)第\s*([0-9][0-9、\-～~\s]*?)\s*條"
)
_EFFECTIVE_CLAUSE = re.compile(r"自\s*([^；。]{1,40}?)\s*施行")
_ORIGINAL_PATTERN = re.compile(r"制定公布全文(\d+)條")


class LawHistoryParseError(ValueError):
    """頁面結構或日期無法解析；不得以部分結果充當完整沿革。"""


def parse_chinese_number(text: str) -> int:
    """把中文數字轉為整數（支援 一百十五、七十九、九十八）。"""

    total = 0
    section = 0
    number = 0
    for char in text.strip():
        if char in _DIGITS:
            number = _DIGITS[char]
        elif char in _UNITS:
            unit = _UNITS[char]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
        elif char.isdigit():
            return int(text)
        else:
            raise LawHistoryParseError(f"無法解析中文數字：{text!r}")
    return section + number


def _roc_date(text: str, *, require_prefix: bool = True) -> str:
    """民國紀年字串 → ISO 日期（民國年 + 1911）。"""

    pattern = _ROC_PREFIXED_DATE_PATTERN if require_prefix else _DATE_PATTERN
    match = pattern.search(text)
    if not match:
        raise LawHistoryParseError(f"找不到民國日期：{text!r}")
    year = parse_chinese_number(match.group(1)) + 1911
    month = parse_chinese_number(match.group(2))
    day = parse_chinese_number(match.group(3))
    return date(year, month, day).isoformat()


def expand_article_list(text: str) -> list[str]:
    """展開 ``10、61、274～279、315-2`` 這類條號清單（回傳 ``172-1`` 形式）。"""

    references: list[str] = []
    for token in re.split(r"[、,，]", text):
        token = token.strip().replace(" ", "")
        if not token:
            continue
        if "～" in token or "~" in token:
            range_match = re.fullmatch(
                r"(\d+)(?:-(\d+))?[～~](\d+)(?:-(\d+))?", token
            )
            if not range_match:
                raise LawHistoryParseError(f"無法解析條號範圍：{token!r}")
            start_main, start_sub, end_main, end_sub = range_match.groups()
            start_main_i, end_main_i = int(start_main), int(end_main)
            if start_main_i > end_main_i or end_main_i - start_main_i > 100:
                raise LawHistoryParseError(f"條號範圍異常：{token!r}")
            if start_main_i == end_main_i and start_sub and end_sub:
                for sub in range(int(start_sub), int(end_sub) + 1):
                    references.append(f"{start_main_i}-{sub}")
                continue
            for main in range(start_main_i, end_main_i + 1):
                if main == start_main_i and start_sub is not None:
                    references.append(f"{main}-{start_sub}")
                elif main == end_main_i and end_sub is not None:
                    references.append(str(main))
                    references.append(f"{main}-{end_sub}")
                else:
                    references.append(str(main))
            continue
        simple = re.fullmatch(r"(\d+)(?:-(\d+))?", token)
        if not simple:
            raise LawHistoryParseError(f"無法解析條號：{token!r}")
        references.append(f"{simple.group(1)}-{simple.group(2)}" if simple.group(2) else simple.group(1))
    deduped: list[str] = []
    for reference in references:
        if reference not in deduped:
            deduped.append(reference)
    return deduped


def _clean_block(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = unescape(text).replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def _effective_on(text: str, promulgated_on: str) -> tuple[str | None, str]:
    clauses = [match.group(1) for match in _EFFECTIVE_CLAUSE.finditer(text)]
    explicit_dates: list[str] = []
    publication_day = False
    for clause in clauses:
        if "公布日" in clause:
            publication_day = True
            continue
        if _DATE_PATTERN.search(clause):
            explicit_dates.append(_roc_date(clause, require_prefix=False))
    if len(set(explicit_dates)) > 1 or (explicit_dates and publication_day):
        return None, "MIXED"
    if explicit_dates:
        return explicit_dates[0], "EXPLICIT"
    # 明載自公布日施行，或未載施行日均依中央法規標準法第 13 條推算。
    basis = "PUBLICATION_DAY" if publication_day else "PUBLICATION_DAY_DEFAULT"
    return (date.fromisoformat(promulgated_on) + timedelta(days=2)).isoformat(), basis


def parse_history_html(html: str, *, law_name: str, pcode: str) -> dict[str, Any]:
    """解析沿革頁；結構不符時丟出 ``LawHistoryParseError``。"""

    promulgated_match = re.search(
        r"<th>\s*公布日期：\s*</th>\s*<td[^>]*>\s*([^<]+)</td>", html, flags=re.I
    )
    amended_match = re.search(
        r"<th>\s*修正日期：\s*</th>\s*<td[^>]*>\s*([^<]+)</td>", html, flags=re.I
    )
    blocks = _ROW_PATTERN.findall(html)
    if not blocks:
        raise LawHistoryParseError("沿革頁找不到修正紀錄區塊")

    amendments: list[dict[str, Any]] = []
    for block in blocks:
        text = _clean_block(block)
        index_match = re.match(r"(\d+)\.\s*(.*)$", text)
        if not index_match:
            continue
        index = int(index_match.group(1))
        body = index_match.group(2)
        # 官方頁面會在詞語中間插入 <br>，清理後變成「令修 正公布」這類空格；
        # 結構分析一律使用去空白版本，避免關鍵詞被拆開而漏判。
        compact = re.sub(r"\s+", "", body)
        if not _DATE_PATTERN.search(compact):
            raise LawHistoryParseError(f"第 {index} 筆修正紀錄缺少日期：{body[:80]!r}")
        promulgated_on = _roc_date(compact)
        effective_on, basis = _effective_on(compact, promulgated_on)
        modified: list[str] = []
        added: list[str] = []
        deleted: list[str] = []
        for action, articles in _ARTICLE_ACTION.findall(compact):
            try:
                expanded = expand_article_list(articles)
            except LawHistoryParseError as exc:
                raise LawHistoryParseError(f"第 {index} 筆：{exc}") from exc
            if action.startswith("修正"):
                modified.extend(expanded)
            elif action.startswith("增訂"):
                added.extend(expanded)
            else:
                deleted.extend(expanded)
        original = _ORIGINAL_PATTERN.search(compact)
        if original:
            kind = "ORIGINAL"
            article_count: int | None = int(original.group(1))
        elif modified or added or deleted:
            kind = "AMENDMENT"
            article_count = None
        else:
            raise LawHistoryParseError(f"第 {index} 筆無法辨識任何條號：{body[:80]!r}")
        amendments.append(
            {
                "index": index,
                "kind": kind,
                "promulgated_on": promulgated_on,
                "effective_on": effective_on,
                "effective_basis": basis,
                "article_count": article_count,
                "modified": sorted(set(modified)),
                "added": sorted(set(added)),
                "deleted": sorted(set(deleted)),
                "text": body,
            }
        )
    amendments.sort(key=lambda item: (item["promulgated_on"], item["index"]))
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "law_name": law_name,
        "pcode": pcode,
        "promulgated_on": _roc_date(promulgated_match.group(1)) if promulgated_match else None,
        "last_amended_on": _roc_date(amended_match.group(1)) if amended_match else None,
        "amendment_count": len(amendments),
        "effective_rule": EFFECTIVE_RULE,
        "amendments": amendments,
        "unknowns": [
            "沿革頁只列修正／增訂／刪除的條號，未提供各該條文的歷史文字。",
            "同一修正有分段施行時，effective_on 記為 null（MIXED），須人工確認。",
        ],
    }


def fetch_history_html(pcode: str, *, timeout: int = 40) -> bytes:
    """抓取官方沿革頁原始 bytes。

    只關閉 X509 嚴格延伸檢查，憑證鏈驗證仍開啟。
    """

    context = ssl.create_default_context()
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    request = urllib.request.Request(
        HISTORY_URL.format(pcode=pcode), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.read()


def build_snapshot(raw: bytes, *, law_name: str, pcode: str) -> dict[str, Any]:
    """把官方頁面原始 bytes 轉成快照（含來源與原始頁面 hash，不含抓取時間）。

    刻意不記錄抓取時間：``data/sources`` 內的原始頁面與 hash 才是可重現的
    依據；加入時間戳會讓 ``--check`` 無法逐位元組比對。
    """

    snapshot = parse_history_html(raw.decode("utf-8"), law_name=law_name, pcode=pcode)
    snapshot["source"] = {
        "provider": "全國法規資料庫（法務部）",
        "url": HISTORY_URL.format(pcode=pcode),
        "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_html_bytes": len(raw),
        "parser": PARSER_ID,
    }
    return snapshot


def write_snapshot(snapshot: dict[str, Any], path: Path | str | None = None) -> Path:
    target = Path(path or DEFAULT_SNAPSHOT_PATH)
    target.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return target


def load_snapshot(path: Path | str | None = None) -> dict[str, Any]:
    return json.loads(Path(path or DEFAULT_SNAPSHOT_PATH).read_text(encoding="utf-8"))
