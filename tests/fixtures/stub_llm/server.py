"""Fixed-response OpenAI-compatible server for synthetic tests only."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator


FIXTURE_DIR = Path(__file__).resolve().parent


class StubServer(ThreadingHTTPServer):
    request_count = 0


class StubHandler(BaseHTTPRequestHandler):
    server: StubServer

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        self.server.request_count += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        fixture_name = self.headers.get("X-Stub-Fixture", "")
        if not fixture_name or "/" in fixture_name or "\\" in fixture_name:
            self.send_error(400)
            return
        path = FIXTURE_DIR / f"{fixture_name}.json"
        if not path.is_file():
            self.send_error(404)
            return
        fixture = json.loads(path.read_text(encoding="utf-8"))
        content = fixture.get("content")
        if not isinstance(content, str):
            content = json.dumps(fixture, ensure_ascii=False)
        response = {
            "_stub": True,
            "model": "stub-fixed",
            "choices": [{"message": {"role": "assistant", "content": content}}],
        }
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def running_stub() -> Iterator[tuple[str, StubServer]]:
    server = StubServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
