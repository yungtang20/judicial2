"""Formatting-only normalization for evaluation labels.

This function does not map one offence to another.  It removes procedural
suffixes and superficial `案` / `罪` endings solely for comparison metrics.
"""

from __future__ import annotations

import re


_PROCEDURAL = re.compile(
    r"[（(][^）)]*(?:告訴|破獲|發生|現行犯|移送|受理|備案|通緝|查獲|線上立破)[^）)]*[）)]"
)


def normalize_offense_label(value: str) -> str:
    normalized = _PROCEDURAL.sub("", value).strip()
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"(?:案件|案|罪)$", "", normalized)
    return normalized
