"""Local batch evaluator for the cleaned input and human answer key.

This module never sends case data outside the process.  It reports only
aggregate metrics and keeps the answer key separate from runtime inference.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline import gate1, gate2, gate3
from pipeline.label_normalizer import normalize_offense_label


def evaluate(
    input_path: Path, answer_path: Path, review_path: Path | None = None
) -> dict[str, Any]:
    inputs = json.loads(input_path.read_text(encoding="utf-8"))["records"]
    answers = json.loads(answer_path.read_text(encoding="utf-8"))["records"]
    answer_by_id = {row["case_id"]: row for row in answers}
    review_by_id: dict[str, dict[str, Any]] = {}
    if review_path and review_path.exists():
        review_payload = json.loads(review_path.read_text(encoding="utf-8"))
        review_by_id = {row["case_id"]: row for row in review_payload["records"]}
    routes: Counter[str] = Counter()
    gates: Counter[str] = Counter()
    comparisons: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    reviewed_metrics: Counter[str] = Counter()

    for record in inputs:
        g1 = gate1.run(record)
        g2 = gate2.run(g1)
        g3 = gate3.run(g2)
        routes[g1["route"]] += 1
        gates[f"gate2_{g2['status']}"] += 1
        gates[f"gate3_{g3['status']}"] += 1
        for warning in g3.get("warnings", []):
            warnings[warning] += 1
        expected = answer_by_id.get(record["case_id"], {}).get("offense", "UNKNOWN")
        actual = [c.get("offense") for c in g2.get("candidates", [])]
        coverage["explicit_article_facts"] += len(g1.get("facts", []))
        coverage["candidates"] += len(actual)
        coverage["catalog_only_candidates"] += sum(
            c.get("source_status") == "CATALOG_ONLY" for c in g2.get("candidates", [])
        )
        if expected == "UNKNOWN":
            comparisons["gold_unknown"] += 1
        elif expected in actual:
            comparisons["exact_match"] += 1
        elif not actual:
            comparisons["no_candidate"] += 1
        else:
            comparisons["offense_mismatch"] += 1
        normalized_expected = normalize_offense_label(expected)
        normalized_actual = {normalize_offense_label(str(item)) for item in actual}
        if expected != "UNKNOWN" and normalized_expected in normalized_actual:
            comparisons["normalized_label_match"] += 1

        reference = review_by_id.get(record["case_id"], {}).get("human_reference", {})
        if reference.get("review_status") == "APPROVED":
            reviewed_metrics["approved_records"] += 1
            expected_route = reference.get("expected_route")
            if expected_route == g1["route"]:
                reviewed_metrics["route_match"] += 1
            expected_offenses = set(reference.get("expected_offenses", []))
            if expected_offenses:
                if actual and actual[0] in expected_offenses:
                    reviewed_metrics["top1_match"] += 1
                if expected_offenses.intersection(actual[:3]):
                    reviewed_metrics["top3_match"] += 1
        elif review_by_id:
            reviewed_metrics["pending_records"] += 1

    return {
        "record_count": len(inputs),
        "routes": dict(routes),
        "gate_status": dict(gates),
        "offense_comparison": dict(comparisons),
        "coverage": dict(coverage),
        "human_review_metrics": dict(reviewed_metrics),
        "warning_counts": dict(warnings),
        "privacy": {"external_calls": 0, "raw_text_in_report": False},
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = evaluate(
        root / "data" / "cleaned" / "line_training_input.json",
        root / "data" / "cleaned" / "line_answer_key.json",
        root / "data" / "cleaned" / "line_review_dataset.json",
    )
    report_path = root / "data" / "cleaned" / "evaluation_report.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
