from __future__ import annotations

from app.workflow import create_case, apply_action
from app.rules import candidate_offenses
from tests.helpers import BANK


def test_line_case_drunk_driving_no_victim_flow():
    """吳興酒駕自摔案：無被害人、移送分支完整流轉"""
    intake = {
        "event_time": "115年06月07日06時39分",
        "location": "臺北市信義區吳興街262號",
        "summary": "本所警員於勤務中查獲詹男騎乘普重機酒駕自摔，測得吐氣酒測值0.52mg/L，依公共危險現行犯逮捕移送。",
        "has_victim": False,
        "station": "吳興所",
        "officer": "王俊翔",
    }
    case = create_case(intake, BANK)
    assert case["intake"]["has_victim"] is False
    assert case["question_role"] == "transfer"

    # Gate 1
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    assert case["state"] == "GATE2_QA"

    # Offenses
    cands = candidate_offenses(intake["summary"], BANK)
    assert any(c["id"] == "public_danger" for c in cands)

    case = apply_action(case, "set_offenses", {"offense_ids": ["public_danger"], "legal_route_ids": [], "route_review_confirmed": True, "role": "transfer"}, BANK)
    assert len(case["questions"]) > 0

    # Answers & Gate 2
    answers = {q["id"]: "現場查獲屬實，坦承不諱" for q in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers, "role": "transfer"}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True, "role": "transfer"}, BANK)

    # Numbers
    case = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "北市警證字第1150001號"}}, BANK)
    assert case["state"] == "OUTPUT_READY"


def test_line_case_theft_caught_victim_to_suspect_flow():
    """三張威秀竊盜現行犯案：被害人完成後續辦涉嫌人筆錄"""
    intake = {
        "event_time": "115年01月23日17時55分",
        "location": "臺北市信義區松仁路58號10樓(松仁威秀)",
        "summary": "報案人稱Mia C'bon店內有小偷在現場竊取商品未結帳，警方獲報立即前往查處，當場查獲嫌疑人並起出遭竊商品，依竊盜罪現行犯帶案偵辦。",
        "has_victim": True,
        "station": "三張所",
        "officer": "李文祥",
    }
    case = create_case(intake, BANK)
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)

    answers = {q["id"]: "商品遭竊未結帳屬實" for q in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": answers, "role": "victim"}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True, "role": "victim"}, BANK)
    case = apply_action(case, "save_case_numbers", {"case_numbers": {"proof": "北市警證字第1150003號"}}, BANK)
    assert case["state"] == "OUTPUT_READY"

    # 涉嫌人續辦
    case = apply_action(case, "start_interview", {"role": "suspect"}, BANK)
    assert case["state"] == "GATE2_QA"
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "suspect"}, BANK)
    s_answers = {q["id"]: "坦承行竊，深感後悔" for q in case["questions"]}
    case = apply_action(case, "save_answers", {"answers": s_answers, "role": "suspect"}, BANK)
    case = apply_action(case, "approve_gate2", {"confirmed": True, "role": "suspect"}, BANK)
    assert case["state"] == "OUTPUT_READY"
    assert "victim:default" in case["interviews"]
    assert "suspect:default" in case["interviews"]
