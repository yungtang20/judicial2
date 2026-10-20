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
APP_ORIGIN = os.environ.get("APP_ORIGIN", f"http://{HOST}:{PORT}")
