from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "app" / "static"
DATA_DIR = ROOT / "data"
QUESTION_BANK_PATH = DATA_DIR / "question_bank.json"
DATABASE_PATH = Path(os.environ.get("CASE_DATABASE_PATH", DATA_DIR / "cases.sqlite3"))

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))
MAX_BODY_BYTES = 256_000
MAX_TEXT_LENGTH = 20_000
MAX_SUMMARY_LENGTH = 500
MAX_DOCX_PAGES = 8
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
KOYEB_PUBLIC_DOMAIN = os.environ.get("KOYEB_PUBLIC_DOMAIN", "")
APP_ORIGIN = os.environ.get(
    "APP_ORIGIN",
    f"https://{KOYEB_PUBLIC_DOMAIN}" if KOYEB_PUBLIC_DOMAIN else f"http://{HOST}:{PORT}",
)
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "false").strip().lower() == "true"
AUTH_DATABASE_PATH = Path(os.environ.get(
    "AUTH_DATABASE_PATH",
    "/tmp/accounts.sqlite3" if KOYEB_PUBLIC_DOMAIN else DATA_DIR / "accounts.sqlite3",
))
REGISTRATION_INVITE_CODE = os.environ.get("REGISTRATION_INVITE_CODE", "")
