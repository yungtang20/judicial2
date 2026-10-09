"""Deterministic masking for supported personal identifier formats."""

from __future__ import annotations

import re


_TAIWAN_ID = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]\d{9}(?![A-Za-z0-9])")
_MOBILE_PHONE = re.compile(r"(?<!\d)09\d{2}(?:[- ]?\d{3}){2}(?!\d)")
_LANDLINE_PHONE = re.compile(
    r"(?<!\d)(?:\(0\d{1,3}\)|0\d{1,3})(?:[- ]?\d{3,4}){2}(?!\d)"
)
_VEHICLE_PLATE = re.compile(
    r"(?<![A-Za-z0-9-])(?=[A-Za-z0-9-]{6,8}(?![A-Za-z0-9-]))"
    r"(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)"
    r"[A-Za-z0-9]{2,4}-[A-Za-z0-9]{3,4}(?![A-Za-z0-9])"
)
_PASSPORT = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]{8,9}(?![A-Za-z0-9]))"
    r"(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)"
    r"[A-Za-z0-9]{8,9}(?![A-Za-z0-9])"
)


def _mask_keep_last_three(match: re.Match[str]) -> str:
    value = match.group(0)
    return "*" * (len(value) - 3) + value[-3:]


def _mask_taiwan_id(match: re.Match[str]) -> str:
    value = match.group(0)
    return f"{value[0]}*{value[-3:]}"


def mask(text: str) -> str:
    """Mask supported identifiers without changing other text."""
    if not isinstance(text, str):
        raise TypeError("text must be str")

    masked = _TAIWAN_ID.sub(_mask_taiwan_id, text)
    masked = _MOBILE_PHONE.sub(_mask_keep_last_three, masked)
    masked = _LANDLINE_PHONE.sub(_mask_keep_last_three, masked)
    masked = _VEHICLE_PLATE.sub(_mask_keep_last_three, masked)
    return _PASSPORT.sub(_mask_keep_last_three, masked)
