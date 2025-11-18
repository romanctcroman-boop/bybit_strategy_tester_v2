# PowerShell script для запуска Workers с активацией venv

param(
    [int]$Workers = 4
)

Write-Host "🚀 Starting $Workers Redis Queue Workers..." -ForegroundColor Cyan

# Activate venv
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# Check if activated
if ($env:VIRTUAL_ENV) {
    Write-Host "✅ Virtual environment activated: $env:VIRTUAL_ENV" -ForegroundColor Green
}
else {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Start workers
Write-Host "👷 Starting $Workers workers..." -ForegroundColor Cyan
python -m backend.queue.worker_cli --workers $Workers
