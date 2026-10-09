"""Small local HTTP adapter for the Gate 1 -> Gate 3 pipeline.

It is intentionally model-agnostic.  A browser or a local AI host can send
already-structured Gate 1 fields.  This server never forwards case text,
does not log request bodies, and keeps legal lookup in the local SQLite table.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pipeline import gate1, gate2, gate3
from pipeline.model_provider import extract_fields


_UI_PATH = Path(__file__).with_name("web_ui.html")


def execute_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("request must be a JSON object")
    source: Any = payload.get("record", payload.get("source", payload))
    if not isinstance(source, (str, dict)):
        raise TypeError("source must be text or a record object")
    if payload.get("use_model") is True:
        if isinstance(source, str):
            source = {"summary": source}
        if source.get("gate1_fields") is not None:
            raise ValueError("gate1_fields and use_model cannot be supplied together")
        source = dict(source)
        source["gate1_fields"] = extract_fields(str(source.get("summary", "")))
    first = gate1.run(source)
    second = gate2.run(first)
    third = gate3.run(second)
    return {"gate1": first, "gate2": second, "gate3": third}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            encoded = _UI_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if self.path == "/health":
            self._send(200, {"status": "ok", "external_calls": 0})
            return
        self._send(404, {"error": "not_found"})

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(_UI_PATH.stat().st_size))
            self.end_headers()
            return
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/gates":
            self._send(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._send(200, execute_payload(payload))
        except (ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})

    def log_message(self, _format: str, *_args: Any) -> None:
        # Never log URLs or request bodies because they can contain case data.
        return


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), _Handler).serve_forever()


if __name__ == "__main__":
    serve()
