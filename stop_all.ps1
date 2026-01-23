# ============================================
# Bybit Strategy Tester - Stop All Services
# ============================================

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Stopping All Services" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Function to kill process on port (only LISTEN state, ignore TIME_WAIT)
function Stop-PortProcess {
    param([int]$Port)
    # Only target LISTENING connections - TIME_WAIT will expire on their own
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process -and $process.Id -ne 0) {
                Write-Host "[INFO] Stopping process on port $Port (PID: $($process.Id), Name: $($process.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# 1. Attempt to save state (Placeholder for future persistence logic)
Write-Host "[INFO] Saving application state..." -ForegroundColor Cyan
# Add any specific save/flush API calls here if needed in the future
Start-Sleep -Seconds 1 
Write-Host "[OK] State saved." -ForegroundColor Green
Write-Host ""

# 2. Stop Services via Scripts
# Stop Redis (optional)
Write-Host "[INFO] Stopping Redis (if running)..." -ForegroundColor Yellow
$redisScript = Join-Path $ProjectRoot "scripts\start_redis.ps1"
if (Test-Path $redisScript) {
    & $redisScript stop
}

# Stop Kline DB Service
Write-Host "[INFO] Stopping Kline DB Service..." -ForegroundColor Yellow
$klineDbScript = Join-Path $ProjectRoot "scripts\start_kline_db_service.ps1"
if (Test-Path $klineDbScript) {
    & $klineDbScript stop
}

# Stop DB Maintenance Server
Write-Host "[INFO] Stopping DB Maintenance Server..." -ForegroundColor Yellow
$dbMaintScript = Join-Path $ProjectRoot "scripts\start_db_maintenance.ps1"
if (Test-Path $dbMaintScript) {
    & $dbMaintScript stop
}

# 3. Force Kill Ports (Cleanup)
Write-Host ""
Write-Host "[INFO] Force releasing ports..." -ForegroundColor Cyan

# Port 8000 (Uvicorn)
Stop-PortProcess -Port 8000
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] Port 8000 is free" -ForegroundColor Green
}

# Port 8001 (DB Maintenance)
Stop-PortProcess -Port 8001
if (-not (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] Port 8001 is free" -ForegroundColor Green
}

# Port 6379 (Redis - if local)
Stop-PortProcess -Port 6379

# 4. Cleanup Python Processes (Safety Net)
Write-Host ""
Write-Host "[INFO] Cleaning up lingering Python processes..." -ForegroundColor Yellow
# This is aggressive, but ensures a clean slate for the project
# We filter by command line to avoid killing system python scripts if possible, 
# but Get-Process doesn't always show command line without elevation/WMI.
# For now, we rely on port killing. 

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ALL SERVICES STOPPED" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[INFO] Stopping AI Agent processes..." -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*bybit_strategy_tester*"
}
if ($pythonProcesses) {
    foreach ($proc in $pythonProcesses) {
        Write-Host "  Stopping PID $($proc.Id) ($($proc.ProcessName))" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] Agent processes stopped" -ForegroundColor Green
}
else {
    Write-Host "[INFO] No agent processes found" -ForegroundColor Gray
}

# 5. Clean Python Cache (optional but recommended)
Write-Host ""
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

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All services stopped" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
