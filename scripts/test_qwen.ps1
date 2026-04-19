# QWEN Configuration Test Script
# Updates environment variables and runs test

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "QWEN Configuration Test" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Set environment variables for current session
Write-Host "`nSetting environment variables..." -ForegroundColor Yellow
$env:QWEN_MODEL = "qwen3-max"
$env:QWEN_MODEL_FAST = "qwen-plus"
$env:QWEN_TEMPERATURE = "0.3"
$env:QWEN_ENABLE_THINKING = "true"

Write-Host "  QWEN_MODEL=$env:QWEN_MODEL"
Write-Host "  QWEN_MODEL_FAST=$env:QWEN_MODEL_FAST"
Write-Host "  QWEN_TEMPERATURE=$env:QWEN_TEMPERATURE"
Write-Host "  QWEN_ENABLE_THINKING=$env:QWEN_ENABLE_THINKING"

# Run Python test
Write-Host "`nRunning Python test..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe scripts\test_qwen_config.py
