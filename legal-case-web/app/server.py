from __future__ import annotations

import json
import re
import secrets
import time
from copy import deepcopy
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlparse

from .config import (
    APP_ORIGIN,
    AUTH_DATABASE_PATH,
    AUTH_REQUIRED,
    DATABASE_PATH,
    HOST,
    MAX_BODY_BYTES,
    PORT,
    QUESTION_BANK_PATH,
    REGISTRATION_INVITE_CODE,
    RENDER_HOSTNAME,
    STATIC_DIR,
)
from .accounts import AccountStore
from .documents import DocumentError, brief_docx, brief_text, checked_interview_docx
from .ai import ai_configured, external_ai_enabled
from .rules import RuleError, load_bank
from .storage import CaseNotFound, EphemeralCaseStore, RevisionConflict
from .workflow import WorkflowError, apply_action, create_case, public_case, validate_case_id


def _runtime_source_mtime() -> int:
    root = Path(__file__).resolve().parents[1]
    source_files = [
        *root.joinpath("app").glob("*.py"),
        *root.joinpath("app", "static").glob("*.js"),
        *root.joinpath("app", "static").glob("*.html"),
        root / "data" / "question_bank.json",
    ]
    return int(max(path.stat().st_mtime for path in source_files if path.is_file()))


RUNTIME_SOURCE_MTIME = _runtime_source_mtime()


SESSION_TOKEN = secrets.token_urlsafe(32)
BANK = load_bank(QUESTION_BANK_PATH)
STORE = EphemeralCaseStore()
ACCOUNT_STORE = AccountStore(AUTH_DATABASE_PATH) if AUTH_REQUIRED else None
AUTH_SESSIONS: dict[str, float] = {}
AUTH_LOCK = RLock()
LOGIN_FAILURES: dict[str, list[float]] = {}
SESSION_TTL_SECONDS = 12 * 60 * 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
CASE_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})$")
ACTION_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/actions$")
DOC_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/documents/(victim|suspect|transfer)/(interview|brief)$")
BRIEF_ROUTE = re.compile(r"^/api/cases/([0-9a-f-]{36})/brief/(victim|suspect|transfer)$")
ALLOWED_HOSTS = {
    f"{HOST}:{PORT}", HOST, "localhost", f"localhost:{PORT}",
    "127.0.0.1", f"127.0.0.1:{PORT}",
}
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.add(RENDER_HOSTNAME)
if urlparse(APP_ORIGIN).netloc:
    ALLOWED_HOSTS.add(urlparse(APP_ORIGIN).netloc)
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/login": ("auth.html", "text/html; charset=utf-8"),
    "/auth.js": ("auth.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/auth.css": ("auth.css", "text/css; charset=utf-8"),
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

def _session_token(headers: Any) -> str:
    cookie = SimpleCookie()
    try:
        cookie.load(headers.get("Cookie", ""))
    except Exception:
        return ""
    morsel = cookie.get("case_session")
    token = morsel.value if morsel else ""
    if not token:
        return ""
    expires = AUTH_SESSIONS.get(token, 0)
    if expires <= time.time():
        AUTH_SESSIONS.pop(token, None)
        return ""
    return token


def _new_session() -> str:
    token = secrets.token_urlsafe(32)
    with AUTH_LOCK:
        now = time.time()
        for existing, expiry in list(AUTH_SESSIONS.items()):
            if expiry <= now:
                AUTH_SESSIONS.pop(existing, None)
        AUTH_SESSIONS[token] = now + SESSION_TTL_SECONDS
    return token


def _session_cookie(token: str, *, clear: bool = False) -> str:
    max_age = 0 if clear else SESSION_TTL_SECONDS
    secure = "; Secure" if AUTH_REQUIRED else ""
    return f"case_session={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict{secure}"


def _login_is_locked(username: str) -> bool:
    now = time.time()
    failures = LOGIN_FAILURES.get(username.casefold(), [])
    recent = [stamp for stamp in failures if now - stamp < LOGIN_LOCKOUT_SECONDS]
    LOGIN_FAILURES[username.casefold()] = recent
    return len(recent) >= LOGIN_FAILURE_LIMIT


def _record_login_failure(username: str) -> None:
    LOGIN_FAILURES.setdefault(username.casefold(), []).append(time.time())


def _request_authenticated(handler: BaseHTTPRequestHandler) -> bool:
    if not AUTH_REQUIRED:
        return True
    return bool(_session_token(handler.headers))


def _account_store_ready() -> bool:
    return ACCOUNT_STORE is not None and len(REGISTRATION_INVITE_CODE) >= 32


def _serve_static(handler: BaseHTTPRequestHandler, path: str) -> bool:
    entry = STATIC_FILES.get(path)
    if not entry:
        return False
    name, content_type = entry
    source = STATIC_DIR / name
    if not source.is_file() or source.parent != STATIC_DIR:
        handler._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到檔案")
        return True
    raw = source.read_bytes()
    if name == "index.html" and not AUTH_REQUIRED:
        raw = raw.replace(b"__SESSION_TOKEN__", SESSION_TOKEN.encode("ascii"))
    handler._begin(HTTPStatus.OK, content_type, len(raw))
    handler.wfile.write(raw)
    return True
 


def _auth_error(handler: BaseHTTPRequestHandler) -> None:
    handler._error(HTTPStatus.UNAUTHORIZED, "LOGIN_REQUIRED", "請先登入")

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
        if AUTH_REQUIRED:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        return host in ALLOWED_HOSTS or host.split(":")[0] in ALLOWED_HOSTS

    def _token_allowed(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Session-Token", ""), SESSION_TOKEN)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        if not origin:
            return False
        return origin == APP_ORIGIN or origin == f"http://localhost:{PORT}" or origin == f"http://127.0.0.1:{PORT}"
    def _begin(self, status: int, content_type: str, length: int = 0, **headers: str) -> None:
        self.send_response(status)
        self._security_headers(content_type)
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def _json(self, status: int, payload: Any, **headers: str) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._begin(status, "application/json; charset=utf-8", len(raw), **headers)
        self.wfile.write(raw)

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": code, "message": _safe_error_message(message)})

    def _guard(
        self, *, token: bool = False, mutation: bool = False, session: bool = False
    ) -> bool:
        if not self._host_allowed():
            self._error(HTTPStatus.BAD_REQUEST, "INVALID_HOST", "拒絕非 loopback Host")
            return False
        if session and not _request_authenticated(self):
            self._error(HTTPStatus.UNAUTHORIZED, "LOGIN_REQUIRED", "請先登入")
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
        if not self._guard():
            return
        authenticated = _request_authenticated(self)
        if path == "/api/health":
            self._json(HTTPStatus.OK, {
                "status": "ok",
                "mode": "SINGLE_USER_AUTH" if AUTH_REQUIRED else "LOCAL_ONLY",
                "external_ai": ai_configured(),
                "external_ai_enabled": external_ai_enabled(),
                "source_mtime": RUNTIME_SOURCE_MTIME,
            })
            return
        if path == "/api/auth/status":
            self._json(HTTPStatus.OK, {
                "auth_required": AUTH_REQUIRED,
                "authenticated": authenticated,
                "registration_available": bool(
                    AUTH_REQUIRED and _account_store_ready()
                    and ACCOUNT_STORE is not None and not ACCOUNT_STORE.has_account()
                ),
            })
            return
        if path == "/login":
            if authenticated:
                _serve_static(self, "/")
            else:
                _serve_static(self, "/login")
            return
        if AUTH_REQUIRED and not authenticated:
            if path in {"/", "/index.html"}:
                _serve_static(self, "/login")
                return
            if path not in {"/styles.css", "/auth.css", "/auth.js"}:
                _auth_error(self)
                return
        if path.startswith("/api/") and path not in {"/api/health", "/api/auth/status"}:
            if not self._guard(token=not AUTH_REQUIRED, session=AUTH_REQUIRED):
                return
        if path == "/api/cases":
            self._json(HTTPStatus.OK, {"cases": [], "mode": "EPHEMERAL_SINGLE_CASE"})
            return
        if path == "/api/question-bank":
            self._json(HTTPStatus.OK, {
                "library_version": BANK["library_version"],
                "review_status": BANK["review_status"],
                "legal_route_crosswalk_version": BANK["legal_route_crosswalk_version"],
                "external_ai_enabled": external_ai_enabled(),
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
        if _serve_static(self, path):
            return
        self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到資源")


    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._guard(mutation=True):
            return
        try:
            payload = self._read_json()
            if path in {"/api/auth/register", "/api/auth/login", "/api/auth/logout"}:
                if not AUTH_REQUIRED or ACCOUNT_STORE is None:
                    self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "找不到資源")
                    return
                if path == "/api/auth/register":
                    username = payload.get("username", "")
                    password = payload.get("password", "")
                    invite_code = payload.get("invite_code", "")
                    if not all(isinstance(value, str) for value in (username, password, invite_code)):
                        self._error(HTTPStatus.BAD_REQUEST, "INVALID_CREDENTIALS", "註冊資料格式不正確")
                        return
                    if not _account_store_ready() or ACCOUNT_STORE.has_account():
                        self._error(HTTPStatus.CONFLICT, "REGISTRATION_CLOSED", "註冊目前未開放")
                        return
                    if not ACCOUNT_STORE.register(username, password, invite_code, REGISTRATION_INVITE_CODE):
                        self._error(HTTPStatus.BAD_REQUEST, "REGISTRATION_REJECTED", "註冊資料或邀請碼不正確")
                        return
                    token = _new_session()
                    self._json(
                        HTTPStatus.CREATED, {"ok": True},
                        Set_Cookie=_session_cookie(token),
                    )
                    return
                if path == "/api/auth/login":
                    username = payload.get("username", "")
                    password = payload.get("password", "")
                    if (
                        not isinstance(username, str)
                        or not isinstance(password, str)
                        or not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username)
                    ):
                        self._error(HTTPStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "帳號或密碼錯誤")
                        return
                    if _login_is_locked(username):
                        self._error(HTTPStatus.TOO_MANY_REQUESTS, "LOGIN_THROTTLED", "登入暫時鎖定，請稍後再試")
                        return
                    if not ACCOUNT_STORE.authenticate(username, password):
                        _record_login_failure(username)
                        self._error(HTTPStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "帳號或密碼錯誤")
                        return
                    LOGIN_FAILURES.pop(username.casefold(), None)
                    token = _new_session()
                    self._json(
                        HTTPStatus.OK, {"ok": True},
                        Set_Cookie=_session_cookie(token),
                    )
                    return
                token = _session_token(self.headers)
                if token:
                    AUTH_SESSIONS.pop(token, None)
                self._json(
                    HTTPStatus.OK, {"ok": True},
                    Set_Cookie=_session_cookie("", clear=True),
                )
                return
            if not self._guard(token=not AUTH_REQUIRED, session=AUTH_REQUIRED):
                return
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
                updated = STORE.save(updated, expected_revision)
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
    if AUTH_REQUIRED and ACCOUNT_STORE is not None:
        if not ACCOUNT_STORE.has_account() and len(REGISTRATION_INVITE_CODE) < 32:
            raise RuntimeError("首次帳號註冊前必須設定至少 32 字元的 REGISTRATION_INVITE_CODE")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"法律案件工作台：http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
