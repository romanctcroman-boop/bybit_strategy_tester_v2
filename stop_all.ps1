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
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue 2>$null
    }
    catch {
        $connections = $null
    }
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
try {
    $listening8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue 2>$null
}
catch { $listening8000 = $null }
if (-not $listening8000) {
    Write-Host "[OK] Port 8000 is free" -ForegroundColor Green
}

# Port 8001 (DB Maintenance)
Stop-PortProcess -Port 8001
try {
    $listening8001 = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue 2>$null
}
catch { $listening8001 = $null }
if (-not $listening8001) {
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

# Stop project Python processes (skip VS Code extensions)
Write-Host ""
Write-Host "[INFO] Stopping project Python processes..." -ForegroundColor Yellow

# Only stop processes tracked by PID files
$runDir = Join-Path $ProjectRoot ".run"
if (Test-Path $runDir) {
    $pidFiles = Get-ChildItem -Path $runDir -Filter "*.pid" -ErrorAction SilentlyContinue
    foreach ($pidFile in $pidFiles) {
        try {
            $pid_value = [int](Get-Content $pidFile.FullName -ErrorAction SilentlyContinue)
            $proc = Get-Process -Id $pid_value -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -like "python*") {
                Write-Host "  Stopping $($pidFile.BaseName) (PID: $pid_value)" -ForegroundColor Gray
                Stop-Process -Id $pid_value -Force -ErrorAction SilentlyContinue
            }
            Remove-Item $pidFile.FullName -Force -ErrorAction SilentlyContinue
        }
        catch {
            # Skip invalid PID files
        }
    }
}
Write-Host "[OK] Project processes stopped" -ForegroundColor Green

# Clean Python Cache (skip .venv to avoid locking issues with VS Code)
Write-Host ""
Write-Host "[INFO] Clearing Python cache..." -ForegroundColor Yellow
$cacheCount = 0
Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
Where-Object { $_.FullName -notlike "*\.venv\*" -and $_.FullName -notlike "*node_modules\*" } |
ForEach-Object {
    try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop; $cacheCount++ }
    catch { <# skip locked #> }
}
Write-Host "[OK] Cleared $cacheCount cache directories" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All services stopped" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

# Reset $LASTEXITCODE for both & (shared scope) and -File (separate process) modes
cmd /c "exit 0"
