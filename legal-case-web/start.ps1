$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command py -ErrorAction Stop).Source
$url = "http://127.0.0.1:8787/"

$sourceFiles = @(
    Get-ChildItem -LiteralPath (Join-Path $root "app") -Filter "*.py" -File
    Get-ChildItem -LiteralPath (Join-Path $root "app\static") -Include "*.js", "*.html" -File
    Get-Item -LiteralPath (Join-Path $root "data\question_bank.json")
)
$latestSource = $sourceFiles | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$expectedSourceMtime = [int64][math]::Floor(($latestSource.LastWriteTimeUtc - [datetime]"1970-01-01").TotalSeconds)

$existingHealth = $null
try {
    $existingHealth = Invoke-RestMethod -Uri "${url}api/health" -TimeoutSec 1
} catch {
    # 沒有既有服務時，直接啟動目前版本。
}

if ($existingHealth -and [int64]$existingHealth.source_mtime -ne $expectedSourceMtime) {
    $listener = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
    $ownerIds = @($listener.OwningProcess | Sort-Object -Unique)
    if ($ownerIds.Count -ne 1) {
        throw "8787 連接埠已有無法辨識的服務，請先關閉後再重試。"
    }
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($ownerIds[0])"
    if (-not $owner -or $owner.CommandLine -notmatch "(?i)-m\s+app\.server(?:\s|$)") {
        throw "8787 連接埠不是本專案服務，未自動終止該程序。"
    }
    Stop-Process -Id $owner.ProcessId -Force
    foreach ($attempt in 1..20) {
        if (-not (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) {
            break
        }
        Start-Sleep -Milliseconds 100
    }
}

if ($existingHealth -and [int64]$existingHealth.source_mtime -eq $expectedSourceMtime) {
    Start-Process $url
    Write-Output "法律案件工作台已啟動：$url"
    exit 0
}

Start-Process `
    -FilePath $python `
    -ArgumentList "-3", "-m", "app.server" `
    -WorkingDirectory $root `
    -WindowStyle Hidden

$ready = $false
foreach ($attempt in 1..30) {
    Start-Sleep -Milliseconds 200
    try {
        $health = Invoke-RestMethod -Uri "${url}api/health" -TimeoutSec 1
        if ($health.status -eq "ok" -and [int64]$health.source_mtime -eq $expectedSourceMtime) {
            $ready = $true
            break
        }
    } catch {
        # The bounded readiness loop reports failure below.
    }
}
if (-not $ready) {
    throw "本機服務未能在時限內載入目前版本。"
}
Start-Process $url
Write-Output "法律案件工作台已啟動：$url"
