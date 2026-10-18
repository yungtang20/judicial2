from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SUPPLEMENTAL_BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "supplemental_question_bank.json"


def load_supplemental_questions(path: Path | None = None) -> dict[str, Any]:
    source = path or SUPPLEMENTAL_BANK_PATH
    if not source.is_file():
        return {"schema_version": "1.0", "review_status": "HUMAN_REVIEW_REQUIRED", "packs": []}
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise ValueError("補充問句庫必須維持人工審查狀態")
    return data


def supplemental_questions_for(
    role: str,
    offense_id: str,
    existing_questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """回傳已核准路由的補充問句，不改變正式題庫與法律結論。"""
    seen = {item.get("text") for item in existing_questions}
    result: list[dict[str, Any]] = []
    for pack in load_supplemental_questions().get("packs", []):
        if offense_id not in pack.get("route_ids", []) or pack.get("status") != "HUMAN_REVIEW_REQUIRED":
            continue
        for item in pack.get("questions", {}).get(role, []):
            if item.get("text") in seen:
                continue
            question = deepcopy(item)
            question.update({
                "kind": "supplemental",
                "role": role,
                "offense_id": offense_id,
                "offense_name": pack.get("offense_name", offense_id),
                "priority": 2,
                "status": "PENDING",
                "answer": "",
                "source": {
                    "label": pack.get("source_label", f"supplemental:{pack['pack_id']}"),
                    "status": "HUMAN_REVIEW_REQUIRED",
                },
                "meta": {
                    "supplemental_pack_id": pack["pack_id"],
                    "fact_categories": item.get("fact_categories", []),
                    "fact_target": item.get("fact_target", ""),
                    "target_elements": item.get("target_elements", []),
                    "machine_effects": [],
                },
            })
            result.append(question)
            seen.add(item.get("text"))
    return result
