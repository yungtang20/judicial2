from __future__ import annotations

import sqlite3

import pytest

from app.storage import CaseStore, RevisionConflict
from app.workflow import create_case
from tests.helpers import BANK, intake


def test_database_does_not_contain_plaintext_case_payload(tmp_path):
    path = tmp_path / "cases.sqlite3"
    store = CaseStore(path)
    case = create_case(intake(summary="SENSITIVE_SENTINEL_8492"), BANK)
    store.create(case)
    assert b"SENSITIVE_SENTINEL_8492" not in path.read_bytes()
    assert store.get(case["case_id"])["intake"]["summary"] == "SENSITIVE_SENTINEL_8492"


def test_optimistic_revision_conflict_is_fail_closed(tmp_path):
    store = CaseStore(tmp_path / "cases.sqlite3")
    case = store.create(create_case(intake(), BANK))
    updated = dict(case)
    updated["state"] = "GATE2_QA"
    store.save(updated, 1)
    with pytest.raises(RevisionConflict):
        store.save(dict(case), 1)
    assert store.get(case["case_id"])["state"] == "GATE2_QA"


def test_corrupted_ciphertext_never_becomes_empty_case(tmp_path):
    store = CaseStore(tmp_path / "cases.sqlite3")
    case = store.create(create_case(intake(), BANK))
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE cases SET payload = ? WHERE case_id = ?", (b"broken", case["case_id"]))
    with pytest.raises(Exception):
        store.get(case["case_id"])



def test_list_cases_meta_flags_offense_selection(tmp_path):
    from app.storage import CaseStore
    from tests.helpers import intake
    from app.workflow import create_case, apply_action

    store = CaseStore(tmp_path / "meta.sqlite3")
    bank_case = create_case(intake(), BANK)
    store.create(bank_case)
    rows = store.list_cases_meta()
    assert rows[0]["has_offenses"] is False
    assert "payload" not in rows[0]

    case = store.get(rows[0]["case_id"])
    case = apply_action(case, "approve_gate1", {"confirmed": True}, BANK)
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "role": "victim"}, BANK)
    store.save(case, 1)
    rows = store.list_cases_meta()
    assert rows[0]["has_offenses"] is True
