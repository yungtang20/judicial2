"""Synchronize only explicit offence-catalog articles from twlegalrag.

No case text is used. Queries contain a public law name and article number only.
Existing hand-provided raw files are never modified.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from twlegalrag.retrieval import TLRClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.offense_catalog import load_catalog


DB_PATH = ROOT / "law" / "judicial2_laws.sqlite3"
RAW_ROOT = ROOT / "law" / "raw" / "twlegalrag"
MANIFEST_PATH = ROOT / "law" / "twlegalrag_sync_manifest.json"
_CANONICAL = re.compile(r"^(?P<law>.+?)第\s*(?P<number>\d+)\s*條(?:之\s*(?P<sub>\d+))?$")


def _query_parts(article_no: str) -> tuple[str, str]:
    match = _CANONICAL.fullmatch(article_no)
    if not match:
        raise ValueError(f"unsupported article reference: {article_no}")
    number = match.group("number")
    if match.group("sub"):
        number += f"-{match.group('sub')}"
    return match.group("law"), number


def sync() -> dict[str, object]:
    client = TLRClient()
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    articles = sorted(load_catalog())
    imported: list[str] = []
    failed: list[dict[str, str]] = []
    with sqlite3.connect(DB_PATH) as connection:
        for canonical in articles:
            law_name, number = _query_parts(canonical)
            response = client.law_article(law_name, number)
            matches = response.get("matches", [])
            if not response.get("found") or len(matches) != 1:
                failed.append({"article_no": canonical, "reason": "not exactly one match"})
                continue
            match = matches[0]
            if match.get("article_content_truncated"):
                failed.append({"article_no": canonical, "reason": "article content truncated"})
                continue
            raw_path = RAW_ROOT / f"{match['pcode']}_{number.replace('-', '_')}.json"
            raw_bytes = json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8")
            raw_path.write_bytes(raw_bytes)
            raw_sha256 = hashlib.sha256(raw_bytes).hexdigest().upper()
            connection.execute(
                """
                INSERT OR REPLACE INTO laws (
                    article_no, article_text, source_command, source_url,
                    dataset_version, verification_date, last_modified_date,
                    status, notes, raw_path, raw_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    canonical,
                    match["article_content"],
                    f"twlegalrag law {law_name} {number}",
                    match.get("law_url", ""),
                    match.get("dataset_version", ""),
                    date.today().isoformat(),
                    match.get("law_modified_date", ""),
                    "待人工核定",
                    "twlegalrag 2.3.0；現行整編版本；行為時法需另查",
                    str(raw_path.relative_to(ROOT)),
                    raw_sha256,
                ),
            )
            imported.append(canonical)
        connection.commit()
    manifest = {
        "query_policy": "public law name and article number only; no case data",
        "verification_date": date.today().isoformat(),
        "requested": len(articles),
        "imported": imported,
        "failed": failed,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = sync()
    print(json.dumps({"requested": result["requested"], "imported": len(result["imported"]), "failed": result["failed"]}, ensure_ascii=False, indent=2))
