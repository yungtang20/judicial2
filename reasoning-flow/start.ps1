# reasoning-flow 本機啟動腳本
# 啟動含 LLM 端點（/api/llm）的本機伺服器。
#   工作台   http://127.0.0.1:8797/web/
#   M1 原型  http://127.0.0.1:8797/prototype/
# 停止服務：Ctrl + C

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$port = 8797
$url  = "http://127.0.0.1:$port/web/"

Write-Host "reasoning-flow 本機服務" -ForegroundColor Cyan
Write-Host "  工作台  : $url" -ForegroundColor Green
Write-Host "  M1 原型 : http://127.0.0.1:$port/prototype/" -ForegroundColor Green
Write-Host "  LLM 端點: POST /api/llm（需 opencode CLI）" -ForegroundColor DarkGray
Write-Host "  停止服務: Ctrl + C" -ForegroundColor DarkGray
Write-Host ""

Start-Sleep -Milliseconds 700
Start-Process $url

py -3 (Join-Path $root "tools\serve.py") $port
