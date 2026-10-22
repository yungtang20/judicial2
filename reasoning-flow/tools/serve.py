# -*- coding: utf-8 -*-
"""reasoning-flow 本機伺服器：提供靜態檔案，並代理 LLM 呼叫。

端點：
  GET  /            → 靜態檔案（web/、prototype/、data/、tools/）
  POST /api/llm     → 以本機 opencode CLI 呼叫 LLM
                      請求：{"prompt": "..."}
                      回應：{"ok": true, "text": "..."} 或 {"ok": false, "error": "..."}

LLM 失敗時，前端應退回規則版分析（由前端自行處理）。
金鑰不經此服務傳遞：opencode 沿用使用者本機既有認證。

用法：
    py -3 reasoning-flow/tools/serve.py [port]
"""
import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.environ.get("LB_MODEL", "opencode/minimax-m3.1-flash-free")
TIMEOUT = int(os.environ.get("LB_TIMEOUT_MS", "120000"))
RETRIES = int(os.environ.get("LB_RETRIES", "2"))


def opencode_exe():
    exe = os.environ.get("LB_OPENCODE")
    if exe:
        return exe
    if os.name == "nt":
        cand = os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming", "npm",
            "node_modules", "@opencode", "cli", "bin", "opencode.exe",
        )
        if os.path.exists(cand):
            return cand
    return "opencode"


def call_llm(prompt):
    """回傳 (ok, text_or_error)。逾時會重試。"""
    exe = opencode_exe()
    last_err = "未執行"
    for _ in range(RETRIES + 1):
        try:
            proc = subprocess.run(
                [exe, "run", "--format", "json", "--model", MODEL, prompt],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=TIMEOUT, cwd=ROOT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            last_err = "LLM 逾時"
            continue
        except FileNotFoundError:
            return False, "找不到 opencode 執行檔（請安裝 opencode CLI）"
        if proc.returncode != 0:
            last_err = "opencode 結束碼 %d：%s" % (proc.returncode, (proc.stderr or "")[-300:])
            continue
        parts = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "text" and isinstance(ev.get("part"), dict):
                t = ev["part"].get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif ev.get("type") == "error":
                err = ev.get("error") or {}
                last_err = err.get("message") or "LLM 回傳錯誤"
        text = "".join(parts).strip()
        if text:
            return True, text
        last_err = "LLM 未回傳文字內容"
    return False, last_err


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/llm":
            self.send_error(404, "unknown endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            prompt = body.get("prompt") or ""
            if not prompt:
                raise ValueError("缺少 prompt")
        except Exception as exc:
            self._json(400, {"ok": False, "error": "請求格式錯誤：" + str(exc)})
            return
        ok, result = call_llm(prompt)
        self._json(200, {"ok": ok, "text" if ok else "error": result, "model": MODEL})

    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8797
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("reasoning-flow 本機伺服器")
    print("  工作台   http://127.0.0.1:%d/web/" % port)
    print("  M1 原型  http://127.0.0.1:%d/prototype/" % port)
    print("  LLM 端點 POST /api/llm（模型 %s）" % MODEL)
    print("  停止服務：Ctrl + C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
