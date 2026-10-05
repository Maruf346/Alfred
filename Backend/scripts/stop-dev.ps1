$ErrorActionPreference = "Stop"

$BackendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeDir = Join-Path $BackendRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "backend-dev.pids.json"

if (-not (Test-Path $PidFile)) {
    Write-Host "No running backend dev stack PID file found."
    Write-Host "Expected PID file: $PidFile"
    exit 0
}

$processes = Get-Content $PidFile -Raw | ConvertFrom-Json
if ($processes -isnot [System.Array]) {
    $processes = @($processes)
}

foreach ($entry in $processes) {
    $pidValue = [int]$entry.pid
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue

    if ($process) {
        Write-Host "Stopping $($entry.name) (PID $pidValue)..."
        Stop-Process -Id $pidValue -Force
    } else {
        Write-Host "$($entry.name) (PID $pidValue) is not running."
    }
}

Remove-Item -LiteralPath $PidFile -Force
Write-Host "Backend dev stack stopped."
