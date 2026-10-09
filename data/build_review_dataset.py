"""Build a human-review dataset without inventing legal labels."""

from __future__ import annotations

import json
from pathlib import Path


def build(input_path: Path, answer_path: Path, output_path: Path) -> int:
    inputs = json.loads(input_path.read_text(encoding="utf-8"))["records"]
    answers = json.loads(answer_path.read_text(encoding="utf-8"))["records"]
    answer_by_id = {row["case_id"]: row for row in answers}
    records = []
    for row in inputs:
        answer = answer_by_id.get(row["case_id"], {})
        records.append(
            {
                **row,
                "human_reference": {
                    "raw_offense_label": answer.get("offense", "UNKNOWN"),
                    "expected_route": "PENDING_REVIEW",
                    "criminal_act": "PENDING_REVIEW",
                    "victim_present": "PENDING_REVIEW",
                    "intake_nature": "PENDING_REVIEW",
                    "case_number_present": "PENDING_REVIEW",
                    "expected_offenses": [],
                    "alternative_offenses": [],
                    "excluded_offenses": [],
                    "review_status": "PENDING_REVIEW",
                    "reviewer_note": "",
                },
            }
        )
    payload = {
        "purpose": "synthetic/de-identified human review dataset; local use only",
        "record_count": len(records),
        "records": records,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(records)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    count = build(
        root / "data" / "cleaned" / "line_training_input.json",
        root / "data" / "cleaned" / "line_answer_key.json",
        root / "data" / "cleaned" / "line_review_dataset.json",
    )
    print(count)
