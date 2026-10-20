from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from app import server as server_module
from app.storage import CaseStore
from tests.helpers import intake


ROOT = Path(__file__).parents[1]


@pytest.fixture()
def local_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "STORE", CaseStore(tmp_path / "http.sqlite3"))
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


def request(port, method, path, *, headers=None, body=None, may_retry=False):
    # Windows ThreadingHTTPServer teardown 偶發 ConnectionAbortedError（socket race）
    # → 重試一次；非 GET 只在呼叫端聲明「重試不會造成副作用」時才重試
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            data = response.read()
            result = response.status, dict(response.getheaders()), data
            connection.close()
            return result
        except OSError as exc:  # ConnectionAborted/Reset/timeout 都是 OSError 子類
            last_error = exc
            connection.close()
            if attempt == 1 or (method != "GET" and not may_retry):
                raise
    raise last_error  # pragma: no cover


def test_api_requires_session_token_and_no_store(local_server):
    status, headers, _ = request(local_server, "GET", "/api/cases")
    assert status == 401
    assert headers["Cache-Control"] == "no-store, max-age=0"
    assert "Access-Control-Allow-Origin" not in headers


def test_invalid_host_and_origin_are_rejected(local_server):
    status, _, _ = request(local_server, "GET", "/", headers={"Host": "attacker.invalid"})
    assert status == 400
    headers = {
        "Host": f"127.0.0.1:{local_server}",
        "X-Session-Token": server_module.SESSION_TOKEN,
        "Content-Type": "application/json",
    }
    raw = json.dumps(intake(), ensure_ascii=False).encode("utf-8")
    headers["Content-Length"] = str(len(raw))
    # Origin 缺席時 origin 檢查在建立案件前即以 403 拒絕，重試無副作用
    status, _, _ = request(
        local_server, "POST", "/api/cases", headers=headers, body=raw, may_retry=True
    )
    assert status == 403


def test_hosted_environment_does_not_disable_host_and_origin_checks(local_server, monkeypatch):
    monkeypatch.setenv("RENDER", "1")
    host = "attacker.onrender.com"
    status, _, _ = request(local_server, "GET", "/", headers={"Host": host})
    assert status == 400

    headers = {
        "Host": host,
        "X-Session-Token": server_module.SESSION_TOKEN,
        "Origin": f"https://{host}",
        "Content-Type": "application/json",
    }
    headers["Host"] = f"127.0.0.1:{local_server}"
    headers["Content-Length"] = "0"
    status, _, _ = request(local_server, "POST", "/api/cases", headers=headers, may_retry=True)
    assert status == 403


def test_port_environment_keeps_default_listener_on_loopback():
    env = os.environ.copy()
    env.pop("HOST", None)
    env["PORT"] = "8787"
    env["RENDER"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import HOST; print(HOST)"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "127.0.0.1"


def test_valid_same_origin_request_and_csp(local_server):
    base_headers = {
        "Host": f"127.0.0.1:{local_server}",
        "X-Session-Token": server_module.SESSION_TOKEN,
        "Origin": f"http://127.0.0.1:{local_server}",
        "Content-Type": "application/json",
    }
    raw = json.dumps(intake(), ensure_ascii=False).encode("utf-8")
    base_headers["Content-Length"] = str(len(raw))
    status, headers, body = request(local_server, "POST", "/api/cases", headers=base_headers, body=raw)
    assert status == 201
    assert json.loads(body)["state"] == "GATE1_REVIEW"
    assert "default-src 'self'" in headers["Content-Security-Policy"]


def test_static_path_traversal_is_not_served(local_server):
    status, _, _ = request(
        local_server,
        "GET",
        "/../data/question_bank.json",
        headers={"Host": f"127.0.0.1:{local_server}"},
    )
    assert status == 404



def test_error_messages_are_sanitized_for_unknown_payloads(local_server):
    headers = {
        "Host": f"127.0.0.1:{local_server}",
        "X-Session-Token": server_module.SESSION_TOKEN,
        "Origin": f"http://127.0.0.1:{local_server}",
        "Content-Type": "application/json",
    }
    # 意圖帶攻擊性內容的 payload；錯誤訊息不應回顯輸入
    raw = json.dumps({"summary": "x" * 10, "unexpected_field": "內部機密字串"}, ensure_ascii=False).encode("utf-8")
    headers["Content-Length"] = str(len(raw))
    status, _, body = request(local_server, "POST", "/api/cases", headers=headers, body=raw)
    text = body.decode("utf-8")
    # 不應把輸入內容原樣回顯
    assert "內部機密字串" not in text

def test_safe_error_message_allows_known_business_hints():
    from app.server import _safe_error_message
    assert _safe_error_message("目前不可選擇候選罪章") == "目前不可選擇候選罪章"
    assert _safe_error_message("某未知內部訊息-ID-12345") == "操作未完成，請確認輸入內容或稍後再試"
@pytest.fixture()
def auth_server(tmp_path, monkeypatch):
    from app.accounts import AccountStore

    monkeypatch.setattr(server_module, "AUTH_REQUIRED", True)
    monkeypatch.setattr(server_module, "ACCOUNT_STORE", AccountStore(tmp_path / "accounts.sqlite3"))
    monkeypatch.setattr(server_module, "REGISTRATION_INVITE_CODE", "invite-code-for-private-test-0123456789")
    monkeypatch.setattr(server_module, "AUTH_SESSIONS", {})
    monkeypatch.setattr(server_module, "LOGIN_FAILURES", {})
    instance = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
    port = instance.server_address[1]
    host = f"127.0.0.1:{port}"
    monkeypatch.setattr(server_module, "ALLOWED_HOSTS", {host})
    monkeypatch.setattr(server_module, "APP_ORIGIN", f"http://{host}")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=3)


def test_invite_account_gates_app_api_and_logout(auth_server):
    host = f"127.0.0.1:{auth_server}"
    headers = {"Host": host}

    status, _, body = request(auth_server, "GET", "/", headers=headers)
    assert status == 200
    assert b"PRIVATE" in body
    status, _, body = request(auth_server, "GET", "/api/question-bank", headers=headers)
    assert status == 401
    assert json.loads(body)["error"] == "LOGIN_REQUIRED"

    status, _, body = request(auth_server, "GET", "/api/auth/status", headers=headers)
    assert status == 200
    assert json.loads(body)["registration_available"] is True

    base_headers = {
        "Host": host,
        "Origin": f"http://{host}",
        "Content-Type": "application/json",
    }
    register = json.dumps({
        "username": "owner",
        "password": "correct-horse-battery-staple",
        "invite_code": "invite-code-for-private-test-0123456789",
    })
    status, response_headers, _ = request(
        auth_server, "POST", "/api/auth/register",
        headers={**base_headers, "Content-Length": str(len(register))},
        body=register,
    )
    assert status == 201
    cookie = response_headers["Set-Cookie"].split(";", 1)[0]
    assert "HttpOnly" in response_headers["Set-Cookie"]
    assert "SameSite=Strict" in response_headers["Set-Cookie"]
    assert "Secure" in response_headers["Set-Cookie"]

    status, _, body = request(
        auth_server, "GET", "/api/question-bank",
        headers={"Host": host, "Cookie": cookie},
    )
    assert status == 200
    assert json.loads(body)["review_status"] == "HUMAN_REVIEW_REQUIRED"

    status, _, body = request(auth_server, "GET", "/api/auth/status", headers=headers)
    assert status == 200
    assert json.loads(body)["registration_available"] is False

    logout = "{}"
    status, response_headers, _ = request(
        auth_server, "POST", "/api/auth/logout",
        headers={**base_headers, "Cookie": cookie, "Content-Length": str(len(logout))},
        body=logout,
    )
    assert status == 200
    assert "Max-Age=0" in response_headers["Set-Cookie"]
    status, _, _ = request(
        auth_server, "GET", "/api/question-bank",
        headers={"Host": host, "Cookie": cookie},
    )
    assert status == 401

    login = json.dumps({"username": "owner", "password": "wrong-password"})
    status, _, _ = request(
        auth_server, "POST", "/api/auth/login",
        headers={**base_headers, "Content-Length": str(len(login))},
        body=login,
    )
    assert status == 401
    login = json.dumps({"username": "owner", "password": "correct-horse-battery-staple"})
    status, response_headers, _ = request(
        auth_server, "POST", "/api/auth/login",
        headers={**base_headers, "Content-Length": str(len(login))},
        body=login,
    )
    assert status == 200
    new_cookie = response_headers["Set-Cookie"].split(";", 1)[0]
    status, _, _ = request(
        auth_server, "GET", "/api/question-bank",
        headers={"Host": host, "Cookie": new_cookie},
    )
    assert status == 200
