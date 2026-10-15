from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NODE_TEST = PROJECT_ROOT / "tests" / "test_frontend_api_errors.mjs"


def test_frontend_api_error_behavior():
    try:
        subprocess.run(
            ["node", "--test", str(NODE_TEST)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"Node 行為測試失敗 (exit={exc.returncode})\n"
            f"stdout:\n{exc.stdout}\n"
            f"stderr:\n{exc.stderr}"
        ) from exc
