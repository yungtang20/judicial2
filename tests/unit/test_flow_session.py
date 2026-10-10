import pytest

from pipeline.flow.session import AnswerError, FlowSession, FlowStateError


TEMPLATES = {("虛構所別", "受理報告")}


def _intake():
    return {
        "station": "虛構所別",
        "document_type": "受理報告",
        "reception_type": "受理",
        "event_time": "2099-01-01 10:00",
        "location": "虛構地點乙",
        "summary": "虛構角色甲陳述虛構事件。",
    }


def _gate1(route="A"):
    return {"route": route, "warnings": [], "units": {}, "procedure_facts": {}}


def _gate2():
    return {
        "victim_questions": [{"unit_id": "V-STUB-001", "候選罪章": "虛構候選", "核心問句": ["請說明事件經過"]}],
        "procedure_questions": [],
        "warnings": [],
    }


def _to_answering():
    session = FlowSession()
    session.submit_intake(_intake(), available_templates=TEMPLATES)
    session.accept_gate1(_gate1())
    session.accept_gate2(_gate2())
    ids = session.begin_answering()
    return session, ids


def test_t23_states_cannot_be_skipped():
    session = FlowSession()
    with pytest.raises(FlowStateError):
        session.accept_gate2(_gate2())


def test_t24_route_a_reaches_final_summary_not_gate3():
    session, ids = _to_answering()
    session.submit_answers({ids[0]: "虛構回答"})
    session.begin_final_summary()
    session.accept_final_summary({"gate": "G2-FINAL", "final_summary": "虛構最終摘要", "warnings": []})
    assert session.state == "COMPLETED"


def test_route_b_stops_pending_gate3():
    session = FlowSession()
    session.submit_intake(_intake(), available_templates=TEMPLATES)
    session.accept_gate1(_gate1("B"))
    assert session.state == "DONE_ROUTE_B_PENDING_GATE3"


def test_unknown_route_stays_at_gate1_for_supplement():
    session = FlowSession()
    session.submit_intake(_intake(), available_templates=TEMPLATES)
    session.accept_gate1(_gate1("UNKNOWN"))
    assert session.state == "GATE1"


def test_t25_sessions_do_not_share_state():
    first = FlowSession()
    second = FlowSession()
    first.submit_intake(_intake(), available_templates=TEMPLATES)
    assert first.case_id != second.case_id
    assert second.state == "NEW"


def test_t26_same_gate_supplement_keeps_version():
    session = FlowSession()
    session.submit_intake(_intake(), available_templates=TEMPLATES)
    session.accept_gate1(_gate1("UNKNOWN"))
    session.supplement_current_gate("G1", _gate1("A"))
    assert session.version == "v1"


def test_previous_gate_fact_opens_new_version():
    session, _ids = _to_answering()
    session.restart_from_gate1()
    assert session.version == "v2"
    assert session.state == "INTAKE"


def test_answer_at_unicode_limit_is_accepted():
    session, ids = _to_answering()
    session.submit_answers({ids[0]: "字" * 20_000})


def test_answer_over_unicode_limit_is_rejected_without_truncation():
    session, ids = _to_answering()
    with pytest.raises(AnswerError, match="20000"):
        session.submit_answers({ids[0]: "字" * 20_001})
    assert session.answers == {}
