"""區段感知的 Markdown 問句解析。

questions/*.md 問句段位階（review-checklist.md 第四節優先序）：
  core（核心問句）→ evidence_gap（補充問句，查證身分、文件與來源）
  → reinforce（補強問句，佐證與後續）→ distinguishing（區分問句）
  → aggravating（加重問句）

標題對照（實際檔內出現的標題）：
  核心問句 → core
  補充問句 → evidence_gap
  補強問句 → reinforce
  區分問句 → distinguishing
  加重問句 → aggravating
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any


QUESTION_RE = re.compile(
    r"^\s*-\s+\*\*(?P<id>[A-Z0-9]+-(?:C|S|R|D|A|N|W)-[A-Z0-9]+)\*\*"
    r"(?:（[^）]*）)?：(?P<text>.+?)\s*$"
)

SECTION_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("core", ("核心問句",)),
    ("evidence_gap", ("補充問句",)),
    ("reinforce", ("補強問句",)),
    ("distinguishing", ("區分問句",)),
    ("aggravating", ("加重問句",)),
)

SECTION_PRIORITY: dict[str, int] = {
    "core": 1,
    "evidence_gap": 2,
    "reinforce": 3,
    "distinguishing": 4,
    "aggravating": 5,
}


def _section_of(heading: str) -> str | None:
    for section, keywords in SECTION_MAP:
        if any(word in heading for word in keywords):
            return section
    return None


def _role_for_heading(heading: str) -> str:
    if any(word in heading for word in ("涉嫌人", "行為人", "相對人端")):
        return "suspect"
    if any(word in heading for word in ("被害人", "告訴人", "舉發人", "機關端", "執行單位端")):
        return "victim"
    if "證人" in heading:
        return "witness"
    return "both"


def read_section_questions(path: Path) -> dict[str, dict[str, list[dict[str, str]]]]:
    """回傳 {role: {section: [question]}}。question 具 id 與 text。

    部分檔案（如新建小罪章檔）題目直接列在檔頭下方、沒有「核心問句」等段標題；
    此時依問句 id 字碼判斷：C=core、S=evidence_gap、R=reinforce、D=distinguishing、
    A=aggravating、N/W（涉嫌人／證人核心）=core。
    """
    result: dict[str, dict[str, list[dict[str, str]]]] = {
        "victim": {name: [] for name, _ in SECTION_MAP},
        "suspect": {name: [] for name, _ in SECTION_MAP},
        "transfer": {name: [] for name, _ in SECTION_MAP},
    }
    heading = ""
    section: str | None = None
    seen: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            new_heading = line.lstrip("# ").strip()
            section = _section_of(new_heading)
            heading = new_heading
            continue
        match = QUESTION_RE.match(line)
        if not match:
            continue
        text = match.group("text").strip()
        if text.count("？") > 1:
            continue
        resolved = section if section is not None else _section_by_id(match.group("id"))
        if resolved is None:
            continue
        role = _role_for_heading(heading)
        roles = ("victim", "suspect", "transfer") if role == "both" else (
            ("victim",) if role == "witness" else (("suspect", "transfer") if role == "suspect" else ("victim",))
        )
        for target in roles:
            key = (target, text)
            if key in seen:
                continue
            seen.add(key)
            result[target][resolved].append({"id": match.group("id"), "text": text})
    return result


_ID_CODES: dict[str, tuple[str, ...]] = {
    "core": ("C", "N", "W"),
    "evidence_gap": ("S",),
    "reinforce": ("R",),
    "distinguishing": ("D",),
    "aggravating": ("A",),
}


def _section_by_id(question_id: str) -> str | None:
    segments = question_id.split("-")
    if len(segments) < 2:
        return None
    code = segments[1][:1]
    for section, codes in _ID_CODES.items():
        if code in codes:
            return section
    return None


def ordered_section_questions(
    sections: dict[str, list[dict[str, str]]],
    role: str,
    offense_id: str,
    offense_name: str,
    source: dict[str, Any],
    *,
    max_questions: int | None = None,
) -> list[dict[str, Any]]:
    """依核心→補充→補強→區分→加重順序展開為問句物件。"""
    kind_by_section = {
        "core": "core",
        "evidence_gap": "supplemental",
        "reinforce": "reinforce",
        "distinguishing": "distinguishing",
        "aggravating": "aggravating",
    }
    questions: list[dict[str, Any]] = []
    for section, _ in SECTION_MAP:
        for raw in sections.get(section, []):
            if max_questions is not None and len(questions) >= max_questions:
                return questions
            questions.append({
                "id": f"{role[0].upper()}-{offense_id}-{raw['id']}",
                "text": raw["text"],
                "kind": kind_by_section[section],
                "section": section,
                "priority": SECTION_PRIORITY[section],
                "role": role,
                "offense_id": offense_id,
                "offense_name": offense_name,
                "source": deepcopy(source),
                "status": "PENDING",
                "answer": "",
            })
    return questions
