# ============================================
# Bybit Strategy Tester - Simple Reliable Startup
# ============================================
# Single-script startup that handles everything reliably
# Usage: .\start_simple.ps1
# ============================================

param(
    [switch]$NoBrowser = $false
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# Set UTF-8 encoding for proper emoji/unicode support in logs
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
chcp 65001 | Out-Null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester - Quick Start  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# STEP 1: Validate environment
# =============================================================================
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Python venv found" -ForegroundColor Green

# =============================================================================
# STEP 2: Load .env file
# =============================================================================
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "[OK] Environment loaded from .env" -ForegroundColor Green
}

# =============================================================================
# STEP 3: Kill ALL Python processes and free port 8000
# =============================================================================
Write-Host ""
Write-Host "[STEP 1] Cleaning up..." -ForegroundColor Cyan

# Kill all Python processes from this project
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -and ($cmdLine -like "*bybit_strategy_tester*" -or $cmdLine -like "*uvicorn*" -or $cmdLine -like "*backend*")) {
            Write-Host "  Stopping: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    catch {}
}

# Force kill anything on port 8000
$maxAttempts = 3
for ($i = 0; $i -lt $maxAttempts; $i++) {
    $conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
    if ($conn) {
        $procId = $conn.OwningProcess
        Write-Host "  Killing process on port 8000 (PID: $procId)" -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    else {
        break
    }
}

# Final check
Start-Sleep -Seconds 1
$portCheck = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($portCheck) {
    Write-Host "[ERROR] Port 8000 still occupied! Please close it manually." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Port 8000 is free" -ForegroundColor Green

# =============================================================================
# STEP 4: Ensure cache directories exist
# =============================================================================
$cacheDir = Join-Path $ProjectRoot "cache\bybit_klines"
if (-not (Test-Path $cacheDir)) {
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
}

# =============================================================================
# STEP 5: Start Uvicorn server
# =============================================================================
Write-Host ""
Write-Host "[STEP 2] Starting Uvicorn server..." -ForegroundColor Cyan

# Set working directory
Set-Location $ProjectRoot

# Start uvicorn in background job
$uvicornJob = Start-Job -ScriptBlock {
    param($python, $projectRoot)
    Set-Location $projectRoot
    & $python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 2>&1
} -ArgumentList $VenvPython, $ProjectRoot

Write-Host "[OK] Uvicorn starting (Job ID: $($uvicornJob.Id))..." -ForegroundColor Green

# =============================================================================
# STEP 6: Wait for server to be ready
# =============================================================================
Write-Host ""
Write-Host "[STEP 3] Waiting for server..." -ForegroundColor Cyan
$maxWait = 30
$waited = 0
$ready = $false

while ($waited -lt $maxWait) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($response.status) {
            $ready = $true
            break
        }
    }
    catch {
        # Server not ready yet
    }
    
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 1
    $waited++
}
Write-Host ""

if ($ready) {
    Write-Host "[OK] Server is running!" -ForegroundColor Green
}
else {
    Write-Host "[WARNING] Server may still be starting..." -ForegroundColor Yellow
    # Show last job output
    $output = Receive-Job -Job $uvicornJob -ErrorAction SilentlyContinue
    if ($output) {
        Write-Host "Server output:" -ForegroundColor Gray
        $output | Select-Object -Last 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
}

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SERVER READY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  API:        http://localhost:8000" -ForegroundColor White
Write-Host "  Docs:       http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Dashboard:  http://localhost:8000/frontend/dashboard.html" -ForegroundColor White
Write-Host "  Charts:     http://localhost:8000/frontend/market-chart.html" -ForegroundColor White
Write-Host ""

# Open browser
if (-not $NoBrowser) {
    Write-Host "[INFO] Opening browser..." -ForegroundColor Cyan
    Start-Process "http://localhost:8000/frontend/market-chart.html"
}

Write-Host ""
Write-Host "Press Ctrl+C to stop the server, or run: .\stop_all.ps1" -ForegroundColor Yellow
Write-Host ""

# Keep script running and show server output
Write-Host "Server logs:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray

try {
    while ($true) {
        $output = Receive-Job -Job $uvicornJob -ErrorAction SilentlyContinue
        if ($output) {
            $output | ForEach-Object { Write-Host $_ }
        }
        
        # Check if job is still running
        if ($uvicornJob.State -eq 'Completed' -or $uvicornJob.State -eq 'Failed') {
            Write-Host ""
            Write-Host "[WARNING] Server stopped unexpectedly!" -ForegroundColor Red
            $output = Receive-Job -Job $uvicornJob -ErrorAction SilentlyContinue
            if ($output) { $output | ForEach-Object { Write-Host $_ } }
            break
        }
        
        Start-Sleep -Milliseconds 500
    }
}
finally {
    # Cleanup on exit
    Write-Host ""
    Write-Host "[INFO] Stopping server..." -ForegroundColor Yellow
    Stop-Job -Job $uvicornJob -ErrorAction SilentlyContinue
    Remove-Job -Job $uvicornJob -Force -ErrorAction SilentlyContinue
    
    # Kill any remaining process on port 8000
    $conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
    if ($conn) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "[OK] Server stopped" -ForegroundColor Green
}
