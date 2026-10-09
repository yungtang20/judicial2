"""Command-line entry point for the minimal Gate pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline import gate1, gate2, gate3


def _execute_one(record: str | dict[str, Any]) -> dict[str, Any]:
    gate1_output = gate1.run(record)
    gate2_output = gate2.run(gate1_output)
    gate3_output = gate3.run(gate2_output)
    return {"gate1": gate1_output, "gate2": gate2_output, "gate3": gate3_output}


def execute(case_path: Path) -> dict[str, Any]:
    payload = json.loads(case_path.read_text(encoding="utf-8")) if case_path.suffix.lower() == ".json" else None
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        results = [_execute_one(record) for record in payload["records"]]
        return {"record_count": len(results), "results": results}
    return _execute_one(case_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the minimal Gate 1 pipeline")
    parser.add_argument("case_file", type=Path)
    args = parser.parse_args()
    print(json.dumps(execute(args.case_file), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
