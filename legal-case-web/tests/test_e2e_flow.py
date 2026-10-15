"""E2E 整合測試：真實 HTTP server 走完 Gate 1-5 + 文件下載。

流程依據：docs/QUESTION_DESIGN_AND_USE.md。
"""

from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from app import server as server_module
from app.storage import CaseStore
from tests.helpers import intake


@pytest.fixture()
def e2e_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "STORE", CaseStore(tmp_path / "e2e.sqlite3"))
    instance = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
    port = instance.server_address[1]
    monkeypatch.setattr(server_module, "ALLOWED_HOSTS", {f"127.0.0.1:{port}"})
    monkeypatch.setattr(server_module, "APP_ORIGIN", f"http://127.0.0.1:{port}")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=3)


def _request(port, method, path, *, headers=None, body=None):
    # Windows ThreadingHTTPServer teardown socket race → GET 重試一次
    for attempt in range(2):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            result = resp.status, dict(resp.getheaders()), data
            conn.close()
            return result
        except (ConnectionAbortedError, ConnectionResetError):
            conn.close()
            if method != "GET" or attempt == 1:
                raise
    raise RuntimeError("unreachable")  # pragma: no cover


def _headers(port, token=True):
    h = {
        "Host": f"127.0.0.1:{port}",
        "Content-Type": "application/json",
    }
    if token:
        h["X-Session-Token"] = server_module.SESSION_TOKEN
    return h


def test_question_bank_exposes_legal_route_selection_contract(e2e_server):
    status, _, body = _request(e2e_server, "GET", "/api/question-bank", headers=_headers(e2e_server))
    assert status == 200
    bank = json.loads(body)
    assert bank["legal_route_crosswalk_version"]
    theft = next(item for item in bank["offenses"] if item["id"] == "theft")
    assert theft["selection_policy"] == "OPTIONAL"
    assert {item["id"] for item in theft["legal_routes"]} >= {"theft_320_1_movable"}


def test_e2e_full_gate_flow_with_question_metadata_and_document(e2e_server):
    port = e2e_server
    # 1. 建案
    h = _headers(port)
    h["Origin"] = f"http://127.0.0.1:{port}"
    raw = json.dumps(intake(), ensure_ascii=False).encode("utf-8")
    h["Content-Length"] = str(len(raw))
    status, _, body = _request(port, "POST", "/api/cases", headers=h, body=raw)
    assert status == 201
    case = json.loads(body)
    case_id = case["case_id"]
    revision = case["revision"]

    def _act(action, payload):
        nonlocal revision
        h = _headers(port)
        h["Origin"] = f"http://127.0.0.1:{port}"
        payload_full = {"revision": revision, "action": action, "payload": payload}
        raw = json.dumps(payload_full, ensure_ascii=False).encode("utf-8")
        h["Content-Length"] = str(len(raw))
        status, _, body = _request(port, "POST", f"/api/cases/{case_id}/actions", headers=h, body=raw)
        assert status == 200, f"{action} 失敗：{body[:200]}"
        updated = json.loads(body)
        revision = updated["revision"]
        return updated

    # 2. Gate 1：結構化事實
    case = _act("update_gate1", {"gate1": {"events": ["被害人發現店內物品遭取走"], "people": ["不明行為人"]}})
    assert case["gate1"]["facts"], "gate1 facts 應存在"
    case = _act("approve_gate1", {"confirmed": True})
    assert case["state"] == "GATE2_QA"

    # 3. Gate 2：選罪章 → 問句含 metadata（docs/QUESTION_DESIGN_AND_USE.md §5）
    case = _act("set_offenses", {"offense_ids": ["theft"], "legal_route_ids": ["theft_320_1_movable"], "route_review_confirmed": True, "role": "victim"})
    questions = case["questions"]
    core_qs = [q for q in questions if q.get("kind") == "core"]
    assert core_qs, "應有 core 題"
    for q in core_qs:
        assert "meta" in q, f"core 題缺 metadata：{q['id']}"
        assert q["meta"]["purpose"], f"core 題缺 purpose：{q['id']}"
    # 品質檢核紀錄（docs/QUESTION_DESIGN_AND_USE.md §8）
    assert case["candidates"][0]["source"]["status"] == "VERIFIED_CURRENT"

    # 4. 作答
    answers = {q["id"]: "測試回答" for q in questions}
    case = _act("save_answers", {"answers": answers})
    # 回答驅動重評估（spec §7.4）
    assert "candidates" in case

    # 5. 年籍 + Gate 2 核准
    case = _act("save_profile", {
        "profile": {"name": "測試", "national_id": "A123456789"},
        "session": {"start_time": "2026-10-12T10:00", "end_time": "2026-10-12T11:00", "location": "測試所"},
    })
    case = _act("approve_gate2", {"confirmed": True})

    # 6. 案號
    numbers = {"proof": "Z123456789", "women_child": "", "case_165": ""}
    case = _act("save_case_numbers", {"case_numbers": numbers})
    assert case["state"] == "OUTPUT_READY"

    # 7. 文件下載（含完整性驗證，spec Phase 7）
    h = _headers(port)
    status, headers, data = _request(port, "GET", f"/api/cases/{case_id}/documents/victim/interview", headers=h)
    assert status == 200
    assert data.startswith(b"PK")
    assert "X-Document-Pages" in headers

    # 8. 條陳
    status, _, body = _request(port, "GET", f"/api/cases/{case_id}/brief/victim", headers=h)
    assert status == 200
    brief = json.loads(body)
    assert len(case["brief_summary"]) <= 500
    assert f"案情摘要：{case['brief_summary']}" in brief["text"]


def test_e2e_incomplete_case_blocks_document(e2e_server):
    """未完成流程的案件，文件下載必須被擋（spec Phase 7 fail closed）。"""
    port = e2e_server
    h = _headers(port)
    h["Origin"] = f"http://127.0.0.1:{port}"
    raw = json.dumps(intake(), ensure_ascii=False).encode("utf-8")
    h["Content-Length"] = str(len(raw))
    status, _, body = _request(port, "POST", "/api/cases", headers=h, body=raw)
    case = json.loads(body)
    case_id = case["case_id"]

    # GATE1_REVIEW 狀態直接要求文件 → 應被 DocumentError 擋下
    h = _headers(port)
    status, _, body = _request(port, "GET", f"/api/cases/{case_id}/documents/victim/interview", headers=h)
    assert status == 422
    body_json = json.loads(body)
    assert body_json["error"] == "DOCUMENT_BLOCKED"


def test_e2e_max_selected_offenses_enforced(e2e_server):
    """>3 罪章應被擋下（8 頁防線：97 題容量，core 不可裁，spec §7.5）。"""
    port = e2e_server
    h = _headers(port)
    h["Origin"] = f"http://127.0.0.1:{port}"
    raw = json.dumps(intake(), ensure_ascii=False).encode("utf-8")
    h["Content-Length"] = str(len(raw))
    status, _, body = _request(port, "POST", "/api/cases", headers=h, body=raw)
    case = json.loads(body)
    case_id, revision = case["case_id"], case["revision"]

    h = _headers(port)
    h["Origin"] = f"http://127.0.0.1:{port}"
    payload = {
        "revision": revision,
        "action": "approve_gate1",
        "payload": {"confirmed": True},
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h["Content-Length"] = str(len(raw))
    status, _, body = _request(port, "POST", f"/api/cases/{case_id}/actions", headers=h, body=raw)
    assert status == 200
    revision = json.loads(body)["revision"]

    payload = {
        "revision": revision,
        "action": "set_offenses",
        "payload": {"offense_ids": ["theft", "fraud", "injury", "damage"], "role": "victim"},
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h["Content-Length"] = str(len(raw))
    status, _, body = _request(port, "POST", f"/api/cases/{case_id}/actions", headers=h, body=raw)
    assert status == 422
    assert "最多選擇" in json.loads(body)["message"]
