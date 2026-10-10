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


def request(port, method, path, *, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    result = response.status, dict(response.getheaders()), data
    connection.close()
    return result


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
    status, _, _ = request(local_server, "POST", "/api/cases", headers=headers, body=raw)
    assert status == 403


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

