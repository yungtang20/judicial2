"""Read-only adapter for the repository's existing offence catalogue.

The catalogue is decision support, not an official law source.  Entries retain
their original verification flag and are always returned for human review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "fact-to-crime" / "00_資料" / "罪章"
_ARTICLE = re.compile(r"第\s*(\d+)\s*條(?:\s*之\s*(\d+))?|§\s*(\d+)(?:[-之](\d+))?")
_LAW_ALIASES = (
    ("詐欺犯罪危害防制條例", "詐欺犯罪危害防制條例"),
    ("兒童及少年性剝削防制條例", "兒童及少年性剝削防制條例"),
    ("毒品危害防制條例", "毒品危害防制條例"),
    ("毒條", "毒品危害防制條例"),
    ("家庭暴力防治法", "家庭暴力防治法"),
    ("性騷擾防治法", "性騷擾防治法"),
    ("性別平等工作法", "性別平等工作法"),
    ("道路交通管理處罰條例", "道路交通管理處罰條例"),
    ("道交法", "道路交通管理處罰條例"),
    ("刑法", "刑法"),
)


def extract_article_refs(value: str) -> list[str]:
    """Extract explicit law/article references and normalize spacing only."""
    occurrences: list[tuple[int, int, str]] = []
    for alias, full in _LAW_ALIASES:
        for match in re.finditer(re.escape(alias), value):
            occurrences.append((match.start(), match.end(), full))
    occurrences.sort()
    if not occurrences:
        return []
    refs: list[str] = []
    for index, (_start, content_start, law_name) in enumerate(occurrences):
        content_end = occurrences[index + 1][0] if index + 1 < len(occurrences) else len(value)
        segment = value[content_start:content_end]
        for match in _ARTICLE.finditer(segment):
            number = match.group(1) or match.group(3)
            sub = match.group(2) or match.group(4)
            article = f"{law_name}第 {number} 條"
            if sub:
                article += f"之 {sub}"
            if article not in refs:
                refs.append(article)
    return refs


def canonical_article_no(value: str) -> str | None:
    refs = extract_article_refs(value)
    return refs[0] if refs else None


def load_catalog() -> dict[str, list[dict[str, Any]]]:
    by_article: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(CATALOG_ROOT.glob("*/charges.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for charge in payload.get("charges", []):
            articles = extract_article_refs(str(charge.get("article", "")))
            if not articles:
                continue
            for article in articles:
                by_article.setdefault(article, []).append({
                    "charge_id": charge.get("id"),
                    "offense": charge.get("name", "UNKNOWN"),
                    "article_no": article,
                    "article_label": charge.get("article"),
                    "chapter_id": payload.get("chapter_id"),
                    "required_elements": charge.get("requires_elements", []),
                    "required_one_of": charge.get("requires_one_of", {}),
                    "catalog_verification": charge.get("verification", "unverified"),
                    "catalog_path": str(path.relative_to(PROJECT_ROOT)),
                })
    return by_article
