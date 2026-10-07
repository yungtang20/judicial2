#!/bin/bash
# serve.sh — 本機伺服器啟動腳本
# 用途：解決 file:// 開啟時 fetch 失敗的問題
# 啟動：bash 03_轉換工具/serve.sh [埠]
# 開啟：http://localhost:8000/02_網站/index.html

PORT=${1:-8000}
cd "$(dirname "$0")/.."
echo "啟動本機伺服器於 http://localhost:${PORT}/"
echo "按 Ctrl+C 停止"
python3 -m http.server "${PORT}" 2>/dev/null || python -m http.server "${PORT}"
