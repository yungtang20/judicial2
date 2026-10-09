"""Second-pass de-identification for already parsed local datasets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_ROLE_NAME = re.compile(
    r"(報案人|被害人|嫌疑人|涉嫌人|行為人|相對人|當事人|店長|代表人|"
    r"母親|父親|配偶|男友|女友|友人|同事|所長|副所長|警員|員警)"
    r"([為係稱叫名：:\s]*)"
    r"([A-Z][A-Z\s]{2,40}|[\u4e00-\u9fff○ＯO0]{2,4})(?=[（(、，,\s])"
)
_NAME_BEFORE_DEMOGRAPHIC = re.compile(
    r"(?<![\u4e00-\u9fff])([A-Z][A-Z\s]{2,40}|[\u4e00-\u9fff○ＯO0]{2,4})"
    r"(?=[（(](?:男|女|\d{2,3}年次))"
)
_DIRECT_IDENTIFIERS = (
    re.compile(r"\b[A-Z][12]\d{8}\b"),
    re.compile(r"\b09\d{8}\b"),
    re.compile(r"\b[A-Z]{2,4}-?\d{3,4}\b"),
)


def sanitize_text(value: str) -> str:
    text = _ROLE_NAME.sub(lambda m: f"{m.group(1)}{m.group(2)}<PERSON>", value)
    text = _NAME_BEFORE_DEMOGRAPHIC.sub("<PERSON>", text)
    for pattern in _DIRECT_IDENTIFIERS:
        text = pattern.sub("<REDACTED>", text)
    return text


def _walk(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _walk(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(item, key) for item in value]
    if isinstance(value, str) and key == "summary":
        return sanitize_text(value)
    return value


def sanitize_file(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cleaned = _walk(payload)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cleaned.get("records", []))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    for name in ("line_training_input.json", "line_answer_key.json"):
        print(name, sanitize_file(root / "data" / "cleaned" / name))
