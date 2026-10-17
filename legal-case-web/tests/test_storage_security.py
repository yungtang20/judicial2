from __future__ import annotations


import sqlite3

import pytest
from cryptography.fernet import Fernet

from app.storage import CaseNotFound, CaseStore, EphemeralCaseStore, RevisionConflict


def test_ephemeral_store_keeps_only_current_case_without_database_file(tmp_path):
    store = EphemeralCaseStore()
    first = store.create({"case_id": "first", "state": "GATE1_REVIEW"})
    assert store.get("first")["revision"] == 1
    second = store.create({"case_id": "second", "state": "GATE1_REVIEW"})
    assert store.get("second")["revision"] == 1
    with pytest.raises(CaseNotFound):
        store.get("first")
    assert list(tmp_path.iterdir()) == []
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
    case = apply_action(case, "set_offenses", {"offense_ids": ["theft"], "legal_route_ids": [], "route_review_confirmed": True, "role": "victim"}, BANK)
    store.save(case, 1)
    rows = store.list_cases_meta()
    assert rows[0]["has_offenses"] is True


def test_linux_fernet_roundtrip_when_not_windows(monkeypatch, tmp_path):
    import app.security as sec
    monkeypatch.setattr(sec, "_use_linux_crypto", lambda: True)
    key = Fernet.generate_key()
    monkeypatch.setenv(sec._LINUX_KEY_ENV, key.decode("ascii"))
    payload = {"k": "值"}
    blob = sec.protect_json(payload)
    assert sec.unprotect_json(blob) == payload


def test_linux_key_persists_to_file(monkeypatch, tmp_path):
    import app.security as sec
    monkeypatch.delenv(sec._LINUX_KEY_ENV, raising=False)
    monkeypatch.setattr(sec, "_PERSISTENT_KEY_FILE", str(tmp_path / ".encryption_key"))
    key1 = sec._get_linux_fernet_key()
    key2 = sec._get_linux_fernet_key()
    assert key1 == key2



def _stored_case(tmp_path, name):
    """建一筆含 case_id 的完整案件（走 workflow.create_case）。"""
    from tests.helpers import intake
    from app.workflow import create_case
    from tests.helpers import BANK
    store = CaseStore(tmp_path / f"{name}.sqlite3")
    case = create_case(intake(), BANK)
    store.create(case)
    store.save(case, 1)
    return store


def test_list_cases_meta_flags_damaged_payload(tmp_path):
    """密文損壞的案件不得靜默標記為「未選罪章」——須標 damaged=True（spec §8.4 fail closed）。"""
    store = _stored_case(tmp_path, "damaged")
    import sqlite3
    with sqlite3.connect(tmp_path / "damaged.sqlite3") as conn:
        conn.execute("UPDATE cases SET payload = ?", (b"corrupted-bytes",))
    meta = store.list_cases_meta()
    assert len(meta) == 1
    assert meta[0]["damaged"] is True
    assert meta[0]["has_offenses"] is False


def test_list_cases_meta_healthy_case_not_damaged(tmp_path):
    store = _stored_case(tmp_path, "healthy")
    meta = store.list_cases_meta()
    assert meta[0]["damaged"] is False
