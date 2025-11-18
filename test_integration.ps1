# PowerShell script для запуска integration теста

Write-Host "🧪 Running Integration Test..." -ForegroundColor Cyan

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

# Run test
Write-Host "🎯 Executing test_queue_integration.py..." -ForegroundColor Cyan
python test_queue_integration.py
