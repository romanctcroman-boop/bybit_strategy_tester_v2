# ============================================
# Bybit Strategy Tester - Full Startup Script
# ============================================
# This script starts all required services:
# 1. Redis (optional - for caching/WebSocket)
# 2. Kline DB Service (Database server for market data)
# 3. DB Maintenance Server (Auto-update tasks)
# 4. MCP Server (AI integration)
# 5. Uvicorn Server (FastAPI backend)
# 6. AI Agent Service
# ============================================

param(
    [switch]$SkipCheck = $false,
    [switch]$SkipRedis = $false,
    [switch]$SkipCacheClean = $false,
    [switch]$FastStart = $false
)

# Set UTF-8 encoding for proper emoji display in PowerShell
# Change console code page to UTF-8
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

# Use .venv first (has CuPy/GPU support), then fall back to .venv314
$VenvPythonGPU = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvPython314 = Join-Path $ProjectRoot ".venv314\Scripts\python.exe"
if (Test-Path $VenvPythonGPU) {
    $VenvPython = $VenvPythonGPU
}
elseif (Test-Path $VenvPython314) {
    $VenvPython = $VenvPython314
}
else {
    Write-Host "[ERROR] No virtual environment found!" -ForegroundColor Red
    exit 1
}

# Set PYTHONPATH for correct module imports
$env:PYTHONPATH = $ProjectRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester - Full Startup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python venv exists
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at: $VenvPython" -ForegroundColor Red
    Write-Host "Please create virtual environment first: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Using Python: $VenvPython" -ForegroundColor Green

# =============================================================================
# STEP 0: LOAD ENVIRONMENT & CLEANUP
# =============================================================================

# Load .env file into environment variables
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Write-Host "[INFO] Loading environment from .env..." -ForegroundColor Cyan
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "[OK] Environment loaded (DATABASE_URL, API keys, etc.)" -ForegroundColor Green
}
else {
    Write-Host "[WARNING] .env file not found at $envFile" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[STEP 0] Cleaning up old processes and cache..." -ForegroundColor Cyan

# Clean Python cache to prevent stale .pyc issues (optional - can be slow)
if (-not $SkipCacheClean -and -not $FastStart) {
    Write-Host "[INFO] Clearing Python cache (__pycache__)..." -ForegroundColor Yellow
    $cacheDirs = Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
    if ($cacheDirs) {
        $cacheCount = ($cacheDirs | Measure-Object).Count
        $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Cleared $cacheCount __pycache__ directories" -ForegroundColor Green
    }
    else {
        Write-Host "[OK] No Python cache to clear" -ForegroundColor Green
    }
}
else {
    Write-Host "[SKIP] Python cache cleanup skipped (-SkipCacheClean or -FastStart)" -ForegroundColor Gray
}

# Stop old processes
$stopScript = Join-Path $ProjectRoot "stop_all.ps1"
if (Test-Path $stopScript) {
    Write-Host "[INFO] Running stop_all.ps1 to ensure clean state..." -ForegroundColor Yellow
    & $stopScript
}

# Function to check if port is in use (ignore TIME_WAIT connections)
function Test-Port {
    param([int]$Port)
    # Only check for LISTENING connections - TIME_WAIT are harmless
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

# Function to kill process on port (only LISTEN state, ignore TIME_WAIT)
function Stop-PortProcess {
    param([int]$Port)
    $maxRetries = 5
    $retry = 0
    
    while ($retry -lt $maxRetries) {
        # Only check LISTENING connections - TIME_WAIT will expire on their own
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $connections) {
            return # Port is free for binding
        }

        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process -and $process.Id -ne 0) {
                Write-Host "[INFO] Stopping process on port $Port (PID: $($process.Id), Name: $($process.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 1
        $retry++
    }
    
    # Final check - only LISTENING matters
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "[WARNING] Failed to free port $Port after $maxRetries attempts." -ForegroundColor Red
    }
}

# Step 1: Check and free port 8000 (Double check after stop_all)
Write-Host ""
Write-Host "[STEP 1] Verifying port 8000 is free..." -ForegroundColor Cyan
if (Test-Port -Port 8000) {
    Write-Host "[WARNING] Port 8000 is still in use, forcing kill..." -ForegroundColor Yellow
    Stop-PortProcess -Port 8000
}

# Ensure cache directory exists to prevent "degraded" health status
$cacheDir = Join-Path $ProjectRoot "cache\bybit_klines"
if (-not (Test-Path $cacheDir)) {
    Write-Host "[INFO] Creating cache directory: $cacheDir" -ForegroundColor Gray
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
}


# Step 1.5: Start Redis (Optional)
Write-Host ""
Write-Host "[STEP 1.5] Checking Redis (optional)..." -ForegroundColor Cyan
$redisScript = Join-Path $ProjectRoot "scripts\start_redis.ps1"
if (-not $SkipRedis -and (Test-Path $redisScript)) {
    & $redisScript start
}
else {
    Write-Host "[SKIP] Redis skipped (use -SkipRedis:$false to enable)" -ForegroundColor Gray
}

# Step 2: Start Kline DB Service
Write-Host ""
Write-Host "[STEP 2] Starting Kline DB Service..." -ForegroundColor Cyan
$klineDbScript = Join-Path $ProjectRoot "scripts\start_kline_db_service.ps1"
if (Test-Path $klineDbScript) {
    & $klineDbScript start
    Write-Host "[OK] Kline DB Service started" -ForegroundColor Green
}
else {
    Write-Host "[WARNING] Kline DB Service script not found, skipping..." -ForegroundColor Yellow
}

# Step 2.5: Start DB Maintenance Server
Write-Host ""
Write-Host "[STEP 2.5] Starting DB Maintenance Server..." -ForegroundColor Cyan
$dbMaintScript = Join-Path $ProjectRoot "scripts\start_db_maintenance.ps1"
if (Test-Path $dbMaintScript) {
    & $dbMaintScript start
    Write-Host "[OK] DB Maintenance Server started (API: http://localhost:8001)" -ForegroundColor Green
}
else {
    Write-Host "[WARNING] DB Maintenance script not found, skipping..." -ForegroundColor Yellow
}

# Step 2.7: Update Market Data (check freshness of all symbols in DB)
Write-Host ""
Write-Host "[STEP 2.7] Updating Market Data (checking freshness of all symbols)..." -ForegroundColor Cyan
$updateDataScript = Join-Path $ProjectRoot "scripts\update_market_data.py"
if (Test-Path $updateDataScript) {
    try {
        & $VenvPython $updateDataScript --verbose
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Market data update completed" -ForegroundColor Green
        }
        else {
            Write-Host "[WARNING] Market data update finished with warnings" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "[WARNING] Market data update failed: $_" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[WARNING] Market data update script not found, skipping..." -ForegroundColor Yellow
}

# Step 2.8: Start MCP Server (OPTIONAL - may have unresolved dependencies)
Write-Host ""
Write-Host "[STEP 2.8] Starting MCP Server (optional)..." -ForegroundColor Cyan
$mcpScript = Join-Path $ProjectRoot "scripts\start_mcp_server.ps1"
if (Test-Path $mcpScript) {
    try {
        & $mcpScript start 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] MCP Server starting..." -ForegroundColor Green
        }
        else {
            Write-Host "[SKIP] MCP Server failed to start (optional service)" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "[SKIP] MCP Server not available (optional service)" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[SKIP] MCP Server script not found (optional service)" -ForegroundColor Gray
}

# Step 3: Start Uvicorn Server
Write-Host ""
Write-Host "[STEP 3] Starting Uvicorn Server..." -ForegroundColor Cyan

$uvicornScript = Join-Path $ProjectRoot "scripts\start_uvicorn.ps1"
if (Test-Path $uvicornScript) {
    # Start in background with UTF-8 encoding for emoji support
    # Using 1 worker to avoid multiprocessing issues on Windows with long-running SSE
    $uvicornEnv = if ($FastStart) { "`$env:SKIP_CACHE_WARMUP = '1'; " } else { "" }
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "chcp 65001 | Out-Null; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $uvicornEnv& '$uvicornScript' start -AppModule 'backend.api.app:app' -BindHost '0.0.0.0' -Port 8000 -Workers 1" -WindowStyle Normal
    Write-Host "[OK] Uvicorn server starting..." -ForegroundColor Green
}
else {
    # Fallback: direct uvicorn command
    Write-Host "[INFO] Using direct uvicorn command..." -ForegroundColor Yellow
    $uvicornCmd = "`$env:PYTHONPATH = '$ProjectRoot'; cd '$ProjectRoot'; & '$VenvPython' -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --workers 1"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $uvicornCmd -WindowStyle Normal
    Write-Host "[OK] Uvicorn server starting..." -ForegroundColor Green
}

# Wait for server to start (HTTP Health Check)
Write-Host "[INFO] Waiting for server to start (checking /api/v1/health)..." -ForegroundColor Yellow
Write-Host "[INFO] This may take 30-60 seconds during cache warmup..." -ForegroundColor Gray
$maxWait = 120
$waited = 0
$serverReady = $false

while ($waited -lt $maxWait) {
    try {
        # First check if port is listening
        $listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listening) {
            # Port is open, try health check
            $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
            if ($response.status -eq "healthy" -or $response.status -eq "ok" -or $response.status -eq "degraded") {
                $serverReady = $true
                break
            }
        }
    }
    catch {
        # Show error every 30 seconds for debugging
        if ($waited % 30 -eq 0 -and $waited -gt 0) {
            Write-Host ""
            Write-Host "[DEBUG] Still waiting... Error: $($_.Exception.Message)" -ForegroundColor Gray
        }
    }
    
    Start-Sleep -Seconds 2
    $waited += 2
    Write-Host "." -NoNewline
}
Write-Host ""

if ($serverReady) {
    Write-Host "[OK] Uvicorn server is running and healthy! (took $waited seconds)" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Server failed to start within $maxWait seconds." -ForegroundColor Red
    Write-Host "Please check the Uvicorn terminal window for errors." -ForegroundColor Yellow
    exit 1
}

# Step 4: Start AI Agent Service
Write-Host ""
Write-Host "[STEP 4] Starting AI Agent Service..." -ForegroundColor Cyan

# Note: Agent service outputs to stderr for logging, which PowerShell treats as errors
# We redirect stderr to stdout to prevent false error exit codes
# UTF-8 encoding for emoji support in agent logs
$agentCmd = @"
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONUTF8 = '1'
`$ErrorActionPreference = 'SilentlyContinue'
cd '$ProjectRoot'
& '$VenvPython' -m backend.agents.agent_background_service 2>&1 | ForEach-Object { Write-Host `$_ }
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $agentCmd -WindowStyle Normal
Write-Host "[OK] AI Agent Service starting..." -ForegroundColor Green

# Step 5: Health Check (Completed)
Write-Host ""
Write-Host "[STEP 5] Health check passed during startup." -ForegroundColor Cyan


# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  STARTUP COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  - Redis:                Optional (port 6379 - for caching/WebSocket)" -ForegroundColor Gray
Write-Host "  - Kline DB Service:     Running in background (market data)" -ForegroundColor White
Write-Host "  - DB Maintenance:       http://localhost:8001 (auto-update tasks)" -ForegroundColor White
Write-Host "  - MCP Server:           Optional (AI integration - may require fixes)" -ForegroundColor Gray
Write-Host "  - Uvicorn Server:       http://localhost:8000" -ForegroundColor White
Write-Host "  - AI Agent Service:     Running in background" -ForegroundColor White
Write-Host ""
Write-Host "Web Interfaces:" -ForegroundColor White
Write-Host "  - API Documentation:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Dashboard:            http://localhost:8000/frontend/dashboard.html" -ForegroundColor White
Write-Host "  - Market Charts:        http://localhost:8000/frontend/market-chart.html" -ForegroundColor White
Write-Host "  - DB Maintenance API:   http://localhost:8001/status" -ForegroundColor White
Write-Host ""
Write-Host "AI Agent System (NEW!):" -ForegroundColor Magenta
Write-Host "  - Advanced Agents API:  http://localhost:8000/docs#/agents-advanced" -ForegroundColor Magenta
Write-Host "  - Real LLM Deliberation (DeepSeek + Perplexity)" -ForegroundColor Magenta
Write-Host "  - AI Backtest Analysis, Optimization Insights" -ForegroundColor Magenta
Write-Host "  - MCP Tools: RSI, MACD, BB, ATR, Position Sizing" -ForegroundColor Magenta
Write-Host ""
Write-Host "To stop all services, close the terminal windows or run:" -ForegroundColor Yellow
Write-Host "  .\stop_all.ps1" -ForegroundColor Yellow
Write-Host ""

# Open browser automatically
Write-Host "[INFO] Opening dashboard in browser..." -ForegroundColor Cyan
cmd /c start "" "http://localhost:8000/frontend/dashboard.html"
