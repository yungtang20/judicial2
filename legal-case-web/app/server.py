from __future__ import annotations

import json
import os
import re
import secrets
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import (
    APP_ORIGIN,
    DATABASE_PATH,
    HOST,
    MAX_BODY_BYTES,
    PORT,
    QUESTION_BANK_PATH,
    STATIC_DIR,
)
from .documents import DocumentError, brief_docx, brief_text, checked_interview_docx
from .rules import RuleError, load_bank
from .storage import CaseNotFound, CaseStore, RevisionConflict
from .workflow import WorkflowError, apply_action, create_case, public_case, validate_case_id


SESSION_TOKEN = secrets.token_urlsafe(32)
BANK = load_bank(QUESTION_BANK_PATH)
STORE = CaseStore(DATABASE_PATH)
CASE_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})$")
ACTION_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/actions$")
DOC_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/documents/(victim|suspect|transfer)/(interview|brief)$")
BRIEF_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/brief/(victim|suspect|transfer)$")
ALLOWED_HOSTS = {f"{HOST}:{PORT}", HOST, "localhost", f"localhost:{PORT}", "127.0.0.1", f"127.0.0.1:{PORT}"}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def _safe_error_message(message: str) -> str:
    """把內部錯誤訊息轉成通用化文字，避免洩漏間接案情資訊。

    保留常見的業務驗證提示（這些是使用者需要的行為指引），
    隱藏包含具體 ID、題號、帳戶等細節的訊息。
    """
    # 不需轉換的通用業務驗證提示
    allowed_prefixes = (
        "目前不可", "請先", "至少由人工", "所有問句", "缺少 Gate 1", "Gate 1 必須",
        "Gate 2 必須", "尚未確認候選罪章", "包含未知罪章", "不支援的", "年籍資料",
        "詢問時間", "身分與目前", "回答格式", "包含未知題號", "案號格式",
        "缺少必要案號", "只有完成", "有被害人案件", "無被害人案件", "只有已完成",
        "AI 分析無法使用", "案情摘要", "候選方向最多", "必須是文字", "不得為空白",
        "必須是文字陣列", "facts 必須是", "案件狀態無效", "未知操作", "未知文件",
        "缺少受詢問人", "缺少詢問起訖", "尚未完成", "問句未作答", "找不到",
        "缺少", "輸出不是", "DOCX 內部", "文件殘留", "文件實際排版",
        "找不到本機 LibreOffice", "LibreOffice 無法",
    )
    if any(message.startswith(prefix) for prefix in allowed_prefixes):
        return message
    # 其餘以通用訊息取代，避免洩漏
    return "操作未完成，請確認輸入內容或稍後再試"


class Handler(BaseHTTPRequestHandler):
    server_version = "JudicialLocal/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Do not write paths, query strings, case IDs, or request bodies to logs.
        return

    def _security_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        if os.environ.get("RENDER") or ".onrender.com" in host or host.startswith("0.0.0.0"):
            return True
        return host in ALLOWED_HOSTS or host.split(":")[0] in ALLOWED_HOSTS

    def _token_allowed(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Session-Token", ""), SESSION_TOKEN)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        if not origin:
            return False
        if os.environ.get("RENDER") or ".onrender.com" in origin:
            return True
        return origin == APP_ORIGIN or origin == f"http://localhost:{PORT}" or origin == f"http://127.0.0.1:{PORT}"
    def _begin(self, status: int, content_type: str, length: int = 0, **headers: str) -> None:
        self.send_response(status)
        self._security_headers(content_type)
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def _json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._begin(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)



    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": code, "message": _safe_error_message(message)})

    def _guard(self, *, token: bool = False, mutation: bool = False) -> bool:
        if not self._host_allowed():
            self._error(HTTPStatus.BAD_REQUEST, "INVALID_HOST", "拒絕非 loopback Host")
            return False
        if token and not self._token_allowed():
            self._error(HTTPStatus.UNAUTHORIZED, "INVALID_SESSION", "本機工作階段無效")
            return False
        if mutation and not self._origin_allowed():
            self._error(HTTPStatus.FORBIDDEN, "INVALID_ORIGIN", "拒絕非同源變更請求")
            return False
        return True

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not raw_length.isdigit():
            raise WorkflowError("缺少有效 Content-Length")
        length = int(raw_length)
        if length <= 0 or length > MAX_BODY_BYTES:
            raise WorkflowError("請求內容大小不符限制")
        if self.headers.get_content_type() != "application/json":
            raise WorkflowError("只接受 application/json")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError("JSON 格式錯誤") from exc
        if not isinstance(value, dict):
            raise WorkflowError("JSON 最外層必須是物件")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not self._guard(token=path.startswith("/api/") and path != "/api/health"):
            return
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok", "mode": "LOCAL_ONLY", "external_ai": False})
            return
        if path == "/api/cases":
            self._json(HTTPStatus.OK, {"cases": STORE.list_cases_meta()})
            return
        if path == "/api/question-bank":
            self._json(HTTPStatus.OK, {
                "library_version": BANK["library_version"],
                "review_status": BANK["review_status"],
                "legal_route_crosswalk_version": BANK["legal_route_crosswalk_version"],
                "offenses": [{
                    "id": item["id"],
                    "name": item["name"],
                    "source": item["source"],
                    "route_type": item["route_type"],
                    "selection_policy": item["selection_policy"],
                    "legal_routes": [{"id": route["id"], "name": route["name"]} for route in item["legal_routes"]],
                } for item in BANK["offenses"]],
            })
            return
        match = CASE_ROUTE.fullmatch(path)
        if match:
            try:
                self._json(HTTPStatus.OK, public_case(STORE.get(validate_case_id(match.group(1)))))
            except CaseNotFound:
                self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到案件")
            return
        match = DOC_ROUTE.fullmatch(path)
        if match:
            self._document(*match.groups())
            return
        match = BRIEF_ROUTE.fullmatch(path)
        if match:
            try:
                case = STORE.get(validate_case_id(match.group(1)))
                if case["state"] != "OUTPUT_READY":
                    raise DocumentError("案件尚未完成必要 Gate")
                self._json(HTTPStatus.OK, {"text": brief_text(case, match.group(2))})
            except CaseNotFound:
                self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到案件")
            except DocumentError as exc:
                self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "DOCUMENT_BLOCKED", str(exc))
            return
        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            source = STATIC_DIR / name
            if not source.is_file() or source.parent != STATIC_DIR:
                self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到檔案")
                return
            raw = source.read_bytes()
            if name == "index.html":
                raw = raw.replace(b"__SESSION_TOKEN__", SESSION_TOKEN.encode("ascii"))
            self._begin(HTTPStatus.OK, content_type, len(raw))
            self.wfile.write(raw)
            return
        self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到資源")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._guard(token=True, mutation=True):
            return
        try:
            payload = self._read_json()
            if path == "/api/cases":
                case = STORE.create(create_case(payload, BANK))
                self._json(HTTPStatus.CREATED, public_case(case))
                return
            match = ACTION_ROUTE.fullmatch(path)
            if match:
                case_id = validate_case_id(match.group(1))
                expected_revision = payload.get("revision")
                if not isinstance(expected_revision, int):
                    raise WorkflowError("缺少案件 revision")
                case = STORE.get(case_id)
                if case["revision"] != expected_revision:
                    raise RevisionConflict("案件版本衝突")
                updated = apply_action(
                    deepcopy(case),
                    str(payload.get("action", "")),
                    payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
                    BANK,
                )
                STORE.save(updated, expected_revision)
                self._json(HTTPStatus.OK, public_case(updated))
                return
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到資源")
        except CaseNotFound:
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到案件")
        except RevisionConflict as exc:
            self._error(HTTPStatus.CONFLICT, "REVISION_CONFLICT", str(exc))
        except (WorkflowError, RuleError) as exc:
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", str(exc))
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "本機服務無法完成操作")

    def _document(self, case_id: str, role: str, kind: str) -> None:
        try:
            from .document_validation import validate_document_output
            case = STORE.get(validate_case_id(case_id))
            if case["state"] != "OUTPUT_READY":
                raise DocumentError("案件尚未完成必要 Gate")
            # 完整性驗證（spec Phase 7）：有缺失即阻擋下載
            problems = validate_document_output(case, role, kind)
            if problems:
                raise DocumentError("；".join(problems))
            if kind == "brief":
                data = brief_docx(case, role)
                filename = f"case-{case_id[:8]}-{role}-brief.docx"
                pages = "UNKNOWN"
            else:
                data, page_count = checked_interview_docx(case, role)
                filename = f"case-{case_id[:8]}-{role}-interview.docx"
                pages = str(page_count)
            self._begin(
                HTTPStatus.OK,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                len(data),
                Content_Disposition=f'attachment; filename="{filename}"',
                X_Document_Pages=pages,
            )
            self.wfile.write(data)
        except CaseNotFound:
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到案件")
        except DocumentError as exc:
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "DOCUMENT_BLOCKED", str(exc))
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "DOCUMENT_ERROR", "文件產製或頁數驗證失敗")

    def do_OPTIONS(self) -> None:
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "不啟用 CORS")


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"本機法律案件工作台：http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
