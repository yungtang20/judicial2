import json
from pathlib import Path
from typing import Any

import pytest

from validators.pii_filter import mask


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "pii_samples.json"


def _load_samples() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if data.get("purpose") != "synthetic test data only, not real records":
        raise AssertionError("fixture_purpose_mismatch")
    return data["samples"]


SAMPLES = _load_samples()


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
def test_mask_sample(sample: dict[str, Any]) -> None:
    actual = mask(sample["input"])
    if actual != sample["expected"]:
        pytest.fail(f'{sample["id"]}: mask_mismatch', pytrace=False)


def test_mask_rejects_non_string_input() -> None:
    with pytest.raises(TypeError):
        mask(None)  # type: ignore[arg-type]
