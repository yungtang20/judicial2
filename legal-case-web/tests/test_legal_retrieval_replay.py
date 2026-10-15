import copy
import json
from pathlib import Path

import pytest

from app.legal_retrieval_replay import (
    ReplayCorpusError,
    load_replay_corpus,
    run_replay_suite,
    validate_replay_corpus,
)


CORPUS_PATH = Path(__file__).parent / "fixtures" / "legal_retrieval_replay.json"
JID = "KSDM,100,簡,5635,20111130,1"


def test_golden_replay_suite_passes_without_exposing_fixture_inputs(tmp_path):
    corpus = load_replay_corpus(CORPUS_PATH)
    report = run_replay_suite(corpus, tmp_path / "replay")
    assert report["all_passed"] is True
    assert report["scenario_count"] == 4
    assert report["passed_count"] == 4
    assert report["failed_count"] == 0
    assert len(report["suite_evidence_sha256"]) == 64
    serialized = json.dumps(report, ensure_ascii=False)
    assert JID not in serialized
    assert "synthetic removal fixture" not in serialized
    assert "query_text" not in serialized
    assert "traceback" not in serialized.lower()


def test_expected_projection_drift_is_reported_as_fail(tmp_path):
    corpus = load_replay_corpus(CORPUS_PATH)
    changed = copy.deepcopy(corpus)
    changed["scenarios"][0]["expected"]["record_count"] = 99
    report = run_replay_suite(changed, tmp_path / "replay")
    assert report["all_passed"] is False
    assert report["failed_count"] == 1
    assert report["results"][0]["status"] == "FAIL"


def test_corpus_rejects_forbidden_fixture_case_fields():
    corpus = load_replay_corpus(CORPUS_PATH)
    changed = copy.deepcopy(corpus)
    changed["scenarios"][0]["operations"][0]["fixture"]["summary"] = "不得存在"
    errors = validate_replay_corpus(changed)
    assert any("禁止欄位" in error for error in errors)


def test_corpus_rejects_unknown_expected_error_type():
    corpus = load_replay_corpus(CORPUS_PATH)
    changed = copy.deepcopy(corpus)
    changed["scenarios"][2]["expected"]["error_type"] = "ArbitraryError"
    errors = validate_replay_corpus(changed)
    assert any("error_type 不支援" in error for error in errors)


def test_corpus_rejects_invalid_jid_timestamp_and_contradictory_expected():
    corpus = load_replay_corpus(CORPUS_PATH)
    changed = copy.deepcopy(corpus)
    changed["scenarios"][1]["operations"][1]["requested_jid"] = "bad-jid"
    changed["scenarios"][1]["observed_at"] = "2026-10-15"
    changed["scenarios"][1]["expected"]["error_type"] = "FixtureContractError"
    errors = validate_replay_corpus(changed)
    assert any("requested_jid 格式錯誤" in error for error in errors)
    assert any("UTC ISO timestamp" in error for error in errors)
    assert any("REPORT expected 狀態矛盾" in error for error in errors)


def test_existing_scratch_cache_is_never_overwritten(tmp_path):
    corpus = load_replay_corpus(CORPUS_PATH)
    scratch = tmp_path / "replay"
    scratch.mkdir()
    existing = scratch / "store_dry_run.json"
    existing.write_text("do-not-overwrite", encoding="utf-8")
    with pytest.raises(ReplayCorpusError, match="拒絕覆寫"):
        run_replay_suite(corpus, scratch)
    assert existing.read_text(encoding="utf-8") == "do-not-overwrite"


def test_corpus_file_is_strict_json_contract():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert validate_replay_corpus(corpus) == []
