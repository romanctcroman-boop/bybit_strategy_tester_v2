# PowerShell script для запуска API с активацией venv

Write-Host "🚀 Starting Backend API..." -ForegroundColor Cyan

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

# Start uvicorn
Write-Host "🌐 Starting uvicorn on http://localhost:8000" -ForegroundColor Cyan
uvicorn backend.api.app:app --reload --port 8000
