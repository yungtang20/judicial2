import json
from pathlib import Path
from typing import Any

import pytest

from validators.caseno_check import check


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "caseno_samples.json"


def _load_samples() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if data.get("purpose") != "synthetic test data only, not real records":
        raise AssertionError("fixture_purpose_mismatch")
    return data["samples"]


def _parameter(sample: dict[str, Any]) -> Any:
    if sample["expected_status"] == "SKIP":
        return pytest.param(
            sample,
            id=sample["id"],
            marks=pytest.mark.skip(reason=f'{sample["id"]}: {sample["note"]}'),
        )
    return pytest.param(sample, id=sample["id"])


PARAMETERS = [_parameter(sample) for sample in _load_samples()]


@pytest.mark.parametrize("sample", PARAMETERS)
def test_check_sample(sample: dict[str, Any]) -> None:
    result = check(sample["input"])

    if result["kind"] != sample["expected_kind"]:
        pytest.fail(f'{sample["id"]}: kind_mismatch', pytrace=False)
    if result["status"] != sample["expected_status"]:
        pytest.fail(f'{sample["id"]}: status_mismatch', pytrace=False)

    expected_normalized = sample["expected_normalized"]
    if expected_normalized is not None and result["normalized"] != expected_normalized:
        pytest.fail(f'{sample["id"]}: normalized_mismatch', pytrace=False)


def test_check_rejects_non_string_input() -> None:
    with pytest.raises(TypeError):
        check(None)  # type: ignore[arg-type]
