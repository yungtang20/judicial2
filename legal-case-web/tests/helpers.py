from __future__ import annotations

from copy import deepcopy

from app.config import QUESTION_BANK_PATH
from app.rules import load_bank
from app.workflow import apply_action, create_case


BANK = load_bank(QUESTION_BANK_PATH)


def intake(*, summary: str = "有人未經同意拿走店內物品。", has_victim: bool = True) -> dict:
    return {
        "event_kind": "發生",
        "event_time": "2026-10-10T10:30",
        "location": "測試地點",
        "summary": summary,
        "has_victim": has_victim,
        "victim_identifier": "測試代號" if has_victim else "",
        "victim_is_code": False,
        "station": "測試所",
        "officer": "測試員警",
        "report_time": "2026-10-10T11:00" if has_victim else "",
        "jurisdiction": "測試管轄",
    }


def completed_case(role: str = "victim", offense: str = "theft") -> dict:
    case = create_case(intake(has_victim=role != "transfer"), BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": [offense], "role": role}, BANK)
    answers = {question["id"]: "測試回答" for question in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True}, BANK)
    numbers = {"proof": "Z123456789", "women_child": "", "case_165": ""}
    if offense == "fraud":
        numbers["case_165"] = "1234567890"
    case = apply_action(case, "save_case_numbers", {"case_numbers": numbers}, BANK)
    case["revision"] = 1
    return deepcopy(case)

