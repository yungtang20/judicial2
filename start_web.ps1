$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$url = "http://127.0.0.1:8787/"

if (-not (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) {
    $python = (Get-Command python -ErrorAction Stop).Source
    Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "pipeline.web" `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $projectRoot "pipeline\web.stdout.log") `
        -RedirectStandardError (Join-Path $projectRoot "pipeline\web.stderr.log")

    $ready = $false
    foreach ($attempt in 1..20) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri "${url}health" -TimeoutSec 1
            if ($health.status -eq "ok") {
                $ready = $true
                break
            }
        } catch {
            # Retry until the bounded startup window expires.
        }
    }
    if (-not $ready) {
        throw "JUDICIAL2 web service did not become ready. Check pipeline\web.stderr.log."
    }
}

Start-Process $url
Write-Output "JUDICIAL2 web is ready: $url"
