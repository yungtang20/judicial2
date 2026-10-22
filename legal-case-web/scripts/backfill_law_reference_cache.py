"""補齊離線法條快照中題庫所需的條文。

背景：``data/question_bank.json`` 的 ``source.article_no`` 有 14 個罪章使用
章節範圍（例如 ``第100條至第119條``）。範圍字串在 2026-10-22 之前被當成
單一條號查詢，因此必定查無資料，``/api/question-bank`` 把它們標成
NOT_FOUND。本工具把範圍解析成個別條號，回報缺口，並可選擇以既有
``app.law_reference`` 的 TLR REST client 補齊。

用法：
    py -3 -X utf8 scripts/backfill_law_reference_cache.py --check
    py -3 -X utf8 scripts/backfill_law_reference_cache.py --fetch

邊界：
- 預設 ``--check`` 完全離線，不發出網路請求。
- ``--fetch`` 只送出法規名稱與條號，不含案情、姓名、案號或任何個資。
- 新補條目標記 ``official_verification_status: PENDING``；第三方檢索結果
  不得當成官方複核完成，仍需承辦人以全國法規資料庫核對。
- 既有條目預設不覆寫；要更新請明確加 ``--refresh``。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import law_reference as lr  # noqa: E402

PROVIDER_ID = "tlr.dr-legal.com.tw/v1/law_article"
CACHE_PATH = ROOT / "data" / "law_reference_cache.json"
BANK_PATH = ROOT / "data" / "question_bank.json"


def _required_references() -> list[tuple[str, str, str]]:
    """回傳題庫需要的 (offense_id, law_name, article_reference) 清單。"""

    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    required: list[tuple[str, str, str]] = []
    for offense in bank["offenses"]:
        source = offense.get("source") or {}
        pairs = [(source.get("law_name", ""), source.get("article_no", ""))]
        pairs.extend(
            (item.get("law_name", ""), item.get("article_no", ""))
            for item in source.get("related_articles", [])
        )
        for law_name, article_no in pairs:
            if not (law_name and article_no):
                continue
            for reference in lr.parse_article_spec(article_no):
                required.append((offense["id"], law_name, reference))
    deduped: dict[tuple[str, str], str] = {}
    for offense_id, law_name, reference in required:
        deduped.setdefault((law_name, reference), offense_id)
    return [(offense_id, law_name, ref) for (law_name, ref), offense_id in deduped.items()]


def _missing(cache: dict[str, Any]) -> list[tuple[str, str, str]]:
    missing: list[tuple[str, str, str]] = []
    for offense_id, law_name, reference in _required_references():
        if not any(
            isinstance(cache.get(key), dict) and not cache[key].get("abolished")
            for key in lr._candidate_keys(law_name, reference)
        ):
            missing.append((offense_id, law_name, reference))
    return missing


def _with_provenance(entry: dict[str, Any]) -> dict[str, Any]:
    entry = dict(entry)
    entry["retrieval_provider"] = PROVIDER_ID
    entry["official_verification_status"] = "PENDING"
    entry["official_source_url"] = entry.get("law_url", "")
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只回報缺口（預設行為，完全離線）")
    parser.add_argument("--fetch", action="store_true", help="以 TLR REST 補齊缺口")
    parser.add_argument("--refresh", action="store_true", help="一併重抓既有條目")
    parser.add_argument("--delay", type=float, default=0.4, help="每次請求間隔秒數")
    parser.add_argument("--limit", type=int, default=400, help="單次最多補幾條")
    args = parser.parse_args(argv)

    cache = lr.load_cache()
    missing = _missing(cache)

    if not args.fetch:
        total = len(_required_references())
        print(f"題庫需要條文：{total}　快照已有：{total - len(missing)}　缺：{len(missing)}")
        for offense_id, law_name, reference in missing[:40]:
            print(f"  MISS {offense_id:20} {law_name} {reference}")
        if len(missing) > 40:
            print(f"  ... 另有 {len(missing) - 40} 條")
        return 0 if not missing else 1

    if args.refresh:
        for offense_id, law_name, reference in _required_references():
            for key in lr._candidate_keys(law_name, reference):
                cache.pop(key, None)
        missing = _missing(cache)

    failures: list[str] = []
    added = 0
    for index, (offense_id, law_name, reference) in enumerate(missing[: args.limit], 1):
        try:
            entry = lr.get_law_article(law_name, reference, use_cache=False)
        except Exception as exc:  # noqa: BLE001 - 逐條回報，不中斷整批
            failures.append(f"{law_name} {reference} ({offense_id}): {exc}")
            continue
        cache[f"{law_name}:{reference}"] = _with_provenance(entry)
        added += 1
        print(f"[{index}/{min(len(missing), args.limit)}] {law_name} {reference} OK")
        time.sleep(args.delay)

    cache["_snapshot"] = {
        "provider": PROVIDER_ID,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "official_verification_status": "PENDING",
        "note": (
            "條文由第三方檢索服務取得並逐條記錄 dataset 版本；"
            "不得視為全國法規資料庫人工複核完成，亦不得作為行為時法之依據。"
        ),
        "required_references": len(_required_references()),
        "missing_after_run": len(_missing(cache)),
    }
    lr.save_cache(cache)

    remaining = _missing(cache)
    print(f"補齊完成：新增 {added} 條；仍缺 {len(remaining)} 條；失敗 {len(failures)} 筆")
    for item in remaining:
        print(f"  STILL_MISSING {item}")
    for failure in failures:
        print(f"  FAILED {failure}")
    return 0 if not remaining and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
