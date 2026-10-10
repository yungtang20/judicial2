$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command py -ErrorAction Stop).Source

Start-Process `
    -FilePath $python `
    -ArgumentList "-3", "-m", "app.server" `
    -WorkingDirectory $root `
    -WindowStyle Hidden

$url = "http://127.0.0.1:8787/"
$ready = $false
foreach ($attempt in 1..30) {
    Start-Sleep -Milliseconds 200
    try {
        $health = Invoke-RestMethod -Uri "${url}api/health" -TimeoutSec 1
        if ($health.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        # The bounded readiness loop reports failure below.
    }
}
if (-not $ready) {
    throw "本機服務未能在時限內啟動。"
}
Start-Process $url
Write-Output "法律案件工作台已啟動：$url"

