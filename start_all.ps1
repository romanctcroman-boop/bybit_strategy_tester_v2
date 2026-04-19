# ============================================
# Bybit Strategy Tester - Start All Services
# ============================================
# Usage:
#   .\start_all.ps1             - Full start (stops existing services first)
#   .\start_all.ps1 -FastStart  - Skip heavy startup steps
#   .\start_all.ps1 -NoBrowser  - Don't open browser after startup
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

# ---------------------------------------------------------------------------
# Helper: start an optional sub-script; logs a warning if not found.
# ---------------------------------------------------------------------------
function Start-Service {
    param(
        [string]$Label,
        [string]$ScriptPath,
        [int]$WaitSeconds = 1
    )
    Write-Host ""
    Write-Host "[INFO] Starting $Label..." -ForegroundColor Cyan
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "[WARN] $Label script not found: $ScriptPath" -ForegroundColor Yellow
        return
    }
    & $ScriptPath start
    if ($WaitSeconds -gt 0) { Start-Sleep -Seconds $WaitSeconds }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester - Start All" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
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
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "[OK] Environment loaded from .env" -ForegroundColor Green
}

# =============================================================================
# STEP 3: Stop all existing services before (re)starting
# =============================================================================
Write-Host ""
Write-Host "[INFO] Stopping all existing services..." -ForegroundColor Yellow
$stopScript = Join-Path $ProjectRoot "stop_all.ps1"
if (Test-Path $stopScript) {
    & $stopScript
    Write-Host "[OK] All services stopped." -ForegroundColor Green
} else {
    Write-Host "[WARN] stop_all.ps1 not found, skipping." -ForegroundColor Yellow
}
Start-Sleep -Seconds 2

# =============================================================================
# STEP 4: Start background services
# =============================================================================
Start-Service "Redis"              (Join-Path $ProjectRoot "scripts\start_redis.ps1")           -WaitSeconds 1
Start-Service "Kline DB Service"   (Join-Path $ProjectRoot "scripts\start_kline_db_service.ps1") -WaitSeconds 2
Start-Service "DB Maintenance"     (Join-Path $ProjectRoot "scripts\start_db_maintenance.ps1")   -WaitSeconds 2
Start-Service "MCP Server"         (Join-Path $ProjectRoot "scripts\start_mcp_server.ps1")       -WaitSeconds 1

Write-Host ""
Write-Host "[OK] Market data sync: on-demand (when ticker selected in UI)" -ForegroundColor Green

# =============================================================================
# STEP 5: Start FastAPI (Uvicorn)
# =============================================================================
Write-Host ""
Write-Host "[INFO] Starting Uvicorn server..." -ForegroundColor Cyan

$env:FAST_DEV_MODE = "1"              # Skip warmup for faster startup
$env:AGENT_SKIP_API_HEALTHCHECK = "1" # Skip DeepSeek/Perplexity health checks

$uvicornScript = Join-Path $ProjectRoot "scripts\start_uvicorn.ps1"
if (Test-Path $uvicornScript) {
    & $uvicornScript start
}

# =============================================================================
# STEP 6: Wait for server to be ready
# =============================================================================
Write-Host ""
Write-Host "[INFO] Waiting for server to be ready..." -ForegroundColor Cyan

$maxWait = 60
$waited = 0
$serverReady = $false
$healthEndpoints = @(
    "http://localhost:8000/healthz",
    "http://localhost:8000/api/v1/health/healthz"
)

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++

    foreach ($url in $healthEndpoints) {
        try {
            $response = Invoke-RestMethod -Uri $url -TimeoutSec 5 -ErrorAction Stop
            if ($response.status -eq "ok") {
                $serverReady = $true
                break
            }
        } catch { }
    }

    if ($serverReady) { break }

    if ($waited % 3 -eq 0) {
        Write-Host "  Waiting... ($waited/$maxWait seconds)" -ForegroundColor Gray
    }
}

if ($serverReady) {
    Write-Host "[OK] Server is ready!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Server failed to start within $maxWait seconds." -ForegroundColor Red
    Write-Host "Check the Uvicorn terminal window for errors." -ForegroundColor Yellow
}

# =============================================================================
# STEP 7: Start AI Agent Service (in separate window, non-blocking)
# =============================================================================
$agentScript = Join-Path $ProjectRoot "scripts\start_agent_service.ps1"
if (Test-Path $agentScript) {
    Write-Host ""
    Write-Host "[INFO] Starting AI Agent Service..." -ForegroundColor Cyan
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $agentScript, "start" -WindowStyle Normal
    Start-Sleep -Seconds 1
    Write-Host "[OK] AI Agent Service started in separate window" -ForegroundColor Green
}

# =============================================================================
# STEP 8: Open browser
# =============================================================================
if (-not $NoBrowser -and $serverReady) {
    Write-Host ""
    Write-Host "[INFO] Opening browser..." -ForegroundColor Cyan
    Start-Process "http://localhost:8000/frontend/dashboard.html"
}

# =============================================================================
# FINAL STATUS
# =============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($serverReady) {
    Write-Host "  ALL SERVICES STARTED" -ForegroundColor Green
    Write-Host "  Dashboard: http://localhost:8000" -ForegroundColor White
} else {
    Write-Host "  STARTUP INCOMPLETE" -ForegroundColor Yellow
    Write-Host "  Check logs in .run\ folder" -ForegroundColor White
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
