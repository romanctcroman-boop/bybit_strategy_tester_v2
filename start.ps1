#!/usr/bin/env pwsh
# BYBIT STRATEGY TESTER v2 - AUTO START

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "BYBIT STRATEGY TESTER v2" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# [1] Check Python
Write-Host "[1] Checking Python..." -ForegroundColor Yellow
# Prefer venv Python if available
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $pythonExe = $venvPy
}
else {
    $pythonExe = "python"
}

$pythonVersion = & $pythonExe --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "    $pythonVersion`n" -ForegroundColor Green
}
else {
    Write-Host "    ERROR: Python not found!`n" -ForegroundColor Red
    exit 1
}

# [2] Check Node.js
Write-Host "[2] Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version
if ($LASTEXITCODE -eq 0) {
    Write-Host "    $nodeVersion`n" -ForegroundColor Green
}
else {
    Write-Host "    ERROR: Node.js not found!`n" -ForegroundColor Red
    exit 1
}

# [3] Kill old processes
Write-Host "[3] Killing old processes..." -ForegroundColor Yellow
Get-Process python, node, npm -ErrorAction SilentlyContinue | Stop-Process -Force 2>$null
Start-Sleep -Seconds 2
Write-Host "    OK`n" -ForegroundColor Green

# [4] Env vars for backend
Write-Host "[4] Preparing environment..." -ForegroundColor Yellow
$env:PYTHONPATH = $PSScriptRoot
if (-not $env:DATABASE_URL) {
    # Default to local Postgres dev container (scripts/start_postgres_and_migrate.ps1 uses 5433)
    $env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/bybit"
}
# Avoid DB writes for Bybit klines on dev startup unless explicitly enabled
if (-not $env:BYBIT_PERSIST_KLINES) {
    $env:BYBIT_PERSIST_KLINES = "0"
}
Write-Host "    PYTHONPATH=$($env:PYTHONPATH)" -ForegroundColor DarkGray
Write-Host "    DATABASE_URL=$($env:DATABASE_URL)" -ForegroundColor DarkGray
Write-Host "    BYBIT_PERSIST_KLINES=$($env:BYBIT_PERSIST_KLINES)" -ForegroundColor DarkGray

# Enable Bybit WS manager (optional live feed to Redis)
if (-not $env:BYBIT_WS_ENABLED) { $env:BYBIT_WS_ENABLED = "1" }
if (-not $env:BYBIT_WS_SYMBOLS) { $env:BYBIT_WS_SYMBOLS = "BTCUSDT,ETHUSDT" }
if (-not $env:BYBIT_WS_INTERVALS) { $env:BYBIT_WS_INTERVALS = "1,5" }
Write-Host "    BYBIT_WS_ENABLED=$($env:BYBIT_WS_ENABLED)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_SYMBOLS=$($env:BYBIT_WS_SYMBOLS)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_INTERVALS=$($env:BYBIT_WS_INTERVALS)" -ForegroundColor DarkGray

# [5] Start Backend
Write-Host "[4] Starting Backend..." -ForegroundColor Yellow
$backendCmd = @"
& '$pythonExe' -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --reload
"@
$backendProcess = Start-Process -FilePath powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; $backendCmd" -PassThru
Write-Host "    Backend PID: $($backendProcess.Id)`n" -ForegroundColor Green
Start-Sleep -Seconds 5

# [6] Start Frontend
Write-Host "[6] Starting Frontend..." -ForegroundColor Yellow
$frontendCmd = @"
cd frontend; npm run dev
"@
$frontendProcess = Start-Process -FilePath powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; $frontendCmd" -PassThru
Write-Host "    Frontend PID: $($frontendProcess.Id)`n" -ForegroundColor Green
Start-Sleep -Seconds 8

# [7] Open browser (Yandex default)
Write-Host "[7] Opening browser..." -ForegroundColor Yellow
$url = "http://localhost:5173/#/"
Start-Process $url
Write-Host "    Default browser (Yandex) opening...`n" -ForegroundColor Green
Start-Sleep -Seconds 2

# Success message
Write-Host "========================================" -ForegroundColor Green
Write-Host "ALL SERVERS STARTED" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "`nOpen in browser:" -ForegroundColor Yellow
Write-Host "  http://localhost:5173/#/" -ForegroundColor Magenta
Write-Host "`nHome opens the Bots mock dashboard (стартовая страница макета)`n" -ForegroundColor Green
