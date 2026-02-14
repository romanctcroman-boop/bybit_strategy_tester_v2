# ============================================
# Bybit Strategy Tester - Start All Services
# ============================================
# Usage:
#   .\start_all.ps1           - Full start (stops existing, updates data)
#   .\start_all.ps1 -FastStart - Skip data update for faster startup
# ============================================

param(
    [switch]$FastStart = $false,
    [switch]$NoBrowser = $false
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# Set UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
chcp 65001 | Out-Null

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester - Start All" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# STEP 0: Validate environment
# =============================================================================
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Python venv found" -ForegroundColor Green

# =============================================================================
# STEP 1: Load .env file
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
# STEP 2: Stop existing services
# =============================================================================
Write-Host ""
Write-Host "[INFO] Stopping existing services..." -ForegroundColor Yellow
$stopScript = Join-Path $ProjectRoot "stop_all.ps1"
if (Test-Path $stopScript) {
    & $stopScript
    $global:LASTEXITCODE = 0
}
Start-Sleep -Seconds 2

# =============================================================================
# STEP 3: Start Redis (optional)
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting Redis..." -ForegroundColor Cyan
$redisScript = Join-Path $ProjectRoot "scripts\start_redis.ps1"
if (Test-Path $redisScript) {
    & $redisScript start
    $global:LASTEXITCODE = 0
    Start-Sleep -Seconds 1
}

# =============================================================================
# STEP 4: Start Kline DB Service
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting Kline DB Service..." -ForegroundColor Cyan
$klineDbScript = Join-Path $ProjectRoot "scripts\start_kline_db_service.ps1"
if (Test-Path $klineDbScript) {
    & $klineDbScript start
    $global:LASTEXITCODE = 0
    Start-Sleep -Seconds 2
}

# =============================================================================
# STEP 5: Start DB Maintenance Server
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting DB Maintenance Server..." -ForegroundColor Cyan
$dbMaintScript = Join-Path $ProjectRoot "scripts\start_db_maintenance.ps1"
if (Test-Path $dbMaintScript) {
    & $dbMaintScript start
    $global:LASTEXITCODE = 0
    Start-Sleep -Seconds 2
}

# =============================================================================
# STEP 6: Market data update — REMOVED (2026-02-08)
# Data is synced on-demand when user selects a ticker in Properties panel.
# Startup sync duplicated this and added 15-60s delay to boot time.
# =============================================================================
Write-Host ""
Write-Host "[OK] Market data sync: on-demand (when ticker selected in UI)" -ForegroundColor Green

# =============================================================================
# STEP 7: Start MCP Server (if exists)
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting MCP Server..." -ForegroundColor Cyan
$mcpScript = Join-Path $ProjectRoot "scripts\start_mcp_server.ps1"
if (Test-Path $mcpScript) {
    & $mcpScript start
    $global:LASTEXITCODE = 0
    Start-Sleep -Seconds 1
}

# =============================================================================
# STEP 8: Start Uvicorn (FastAPI)
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting Uvicorn server..." -ForegroundColor Cyan

# Enable FAST_DEV_MODE for faster startup (skip warmup)
$env:FAST_DEV_MODE = "1"

# Skip API health checks (no DeepSeek/Perplexity calls when not using agents)
$env:AGENT_SKIP_API_HEALTHCHECK = "1"

$uvicornScript = Join-Path $ProjectRoot "scripts\start_uvicorn.ps1"
if (Test-Path $uvicornScript) {
    & $uvicornScript start
    $global:LASTEXITCODE = 0
}

# =============================================================================
# STEP 9: Wait for server to be ready
# =============================================================================
Write-Host ""
Write-Host "[INFO] Waiting for server to be ready..." -ForegroundColor Cyan

$maxWait = 60  # seconds (reduced - server should start in ~12s with FAST_DEV_MODE)
$waited = 0
$serverReady = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1  # Check every 1 second for faster response
    $waited += 1
    
    # Try lightweight /healthz first (K8s startup probe)
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -TimeoutSec 5 -ErrorAction Stop
        if ($response.status -eq "ok") {
            $serverReady = $true
            break
        }
    }
    catch {
        # Try alternative endpoint
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/healthz" -TimeoutSec 5 -ErrorAction Stop
            if ($response.status -eq "ok") {
                $serverReady = $true
                break
            }
        }
        catch {
            # Server not ready yet
        }
    }
    
    # Show progress every 3 seconds
    if ($waited % 3 -eq 0) {
        Write-Host "  Waiting... ($waited/$maxWait seconds)" -ForegroundColor Gray
    }
}

if ($serverReady) {
    Write-Host "[OK] Server is ready!" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Server failed to start within $maxWait seconds." -ForegroundColor Red
    Write-Host "Please check the Uvicorn terminal window for errors." -ForegroundColor Yellow
}

# =============================================================================
# STEP 10: Start AI Agent Service (optional)
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting AI Agent Service..." -ForegroundColor Cyan
$agentScript = Join-Path $ProjectRoot "scripts\start_agent_service.ps1"
if (Test-Path $agentScript) {
    # Start agent in separate window (non-blocking)
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $agentScript, "start" -WindowStyle Normal
    Start-Sleep -Seconds 1
    Write-Host "[OK] AI Agent Service started in separate window" -ForegroundColor Green
}

# =============================================================================
# STEP 11: Open browser (unless -NoBrowser)
# =============================================================================
if (-not $NoBrowser -and $serverReady) {
    Write-Host ""
    Write-Host "[INFO] Opening browser..." -ForegroundColor Cyan
    Start-Process "http://localhost:8000"
}

# =============================================================================
# FINAL STATUS
# =============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($serverReady) {
    Write-Host "  ALL SERVICES STARTED" -ForegroundColor Green
    Write-Host "  Dashboard: http://localhost:8000" -ForegroundColor White
}
else {
    Write-Host "  STARTUP INCOMPLETE" -ForegroundColor Yellow
    Write-Host "  Check logs in .run\ folder" -ForegroundColor White
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Reset $LASTEXITCODE to prevent child script errors from propagating
cmd /c "exit 0"
