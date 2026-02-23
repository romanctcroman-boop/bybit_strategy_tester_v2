# ============================================
# Uvicorn Server Management Script
# ============================================
# Usage:
#   .\start_uvicorn.ps1 start  - Start server
#   .\start_uvicorn.ps1 stop   - Stop server
#   .\start_uvicorn.ps1 status - Check status
# ============================================

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "tail")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $ProjectRoot ".run"
$PidFile = Join-Path $RunDir "uvicorn.pid"
$LogFile = Join-Path $RunDir "uvicorn.log"
$LogFileErr = Join-Path $RunDir "uvicorn_err.log"

# Ensure .run directory exists
if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
}

function Get-UvicornProcess {
    $procId = $null
    if (Test-Path $PidFile) {
        $pidContent = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pidContent) {
            $procId = [int]$pidContent
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            # Verify it's actually a python/uvicorn process, not a reused PID
            if ($proc -and $proc.ProcessName -like "python*") {
                return $proc
            }
            # PID file is stale — remove it
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    }
    # Fallback: check port 8000
    try {
        $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue 2>$null
    }
    catch { $conn = $null }
    if ($conn) {
        return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    }
    return $null
}

function Start-UvicornServer {
    $existing = Get-UvicornProcess
    if ($existing) {
        Write-Host "[INFO] Uvicorn already running (PID: $($existing.Id))" -ForegroundColor Yellow
        return
    }

    Write-Host "[INFO] Starting Uvicorn server..." -ForegroundColor Cyan

    # Clear old log file
    if (Test-Path $LogFile) {
        try {
            Remove-Item $LogFile -Force -ErrorAction Stop
        }
        catch {
            # File might be locked, try to clear content
            try {
                Set-Content $LogFile -Value "" -Force -ErrorAction Stop
            }
            catch {
                # Use temp file as fallback
                $LogFile = Join-Path $env:TEMP "bybit_uvicorn.log"
                Write-Host "[WARN] Using temp log file: $LogFile" -ForegroundColor Yellow
            }
        }
    }

    # Start Uvicorn with output redirected to log files via bat wrapper
    # (bat file handles >> redirection reliably on Windows)
    $stdoutLog = $LogFile
    $stderrLog = $LogFileErr
    $batFile = Join-Path $PSScriptRoot "run_uvicorn.bat"

    # Clear old logs
    Set-Content $stdoutLog -Value "" -Force -ErrorAction SilentlyContinue
    Set-Content $stderrLog -Value "" -Force -ErrorAction SilentlyContinue

    try {
        $process = Start-Process -FilePath $batFile `
            -ArgumentList "`"$VenvPython`"", "`"$ProjectRoot`"", "`"$stdoutLog`"", "`"$stderrLog`"" `
            -WorkingDirectory $ProjectRoot `
            -PassThru `
            -WindowStyle Hidden
        
        # Wait a moment for process to start
        Start-Sleep -Seconds 2
        
        # Save PID
        if ($process -and $process.Id) {
            Set-Content -Path $PidFile -Value $process.Id -Force
            Write-Host "[OK] Uvicorn started (PID: $($process.Id))" -ForegroundColor Green
            Write-Host "     Log file: $LogFile" -ForegroundColor Gray
        }
        else {
            Write-Host "[ERROR] Failed to start Uvicorn" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "[ERROR] Failed to start Uvicorn: $_" -ForegroundColor Red
    }
}

function Stop-UvicornServer {
    $proc = Get-UvicornProcess
    if ($proc) {
        Write-Host "[INFO] Stopping Uvicorn (PID: $($proc.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        
        # Verify stopped
        $check = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        if (-not $check) {
            Write-Host "[OK] Uvicorn stopped" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] Process may still be running" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[INFO] Uvicorn is not running" -ForegroundColor Gray
    }
    
    # Clean up PID file
    if (Test-Path $PidFile) {
        try {
            Remove-Item $PidFile -Force -ErrorAction Stop
        }
        catch {
            Set-Content $PidFile -Value "" -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-UvicornStatus {
    $proc = Get-UvicornProcess
    if ($proc) {
        Write-Host "[OK] Uvicorn is running (PID: $($proc.Id))" -ForegroundColor Green
        Write-Host "     stdout log: $LogFile" -ForegroundColor Gray
        Write-Host "     stderr log: $LogFileErr" -ForegroundColor Gray

        # Check if responding
        try {
            $null = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 5 -ErrorAction Stop
            Write-Host "[OK] Server responding" -ForegroundColor Green
        }
        catch {
            Write-Host "[WARN] Server not responding to health check" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[INFO] Uvicorn is not running" -ForegroundColor Gray
    }
}

function Get-UvicornLogs {
    param([int]$Lines = 100)
    Write-Host "=== STDOUT ($LogFile) ===" -ForegroundColor Cyan
    if (Test-Path $LogFile) { Get-Content $LogFile -Tail $Lines } else { Write-Host "(no file)" -ForegroundColor Gray }
    Write-Host "=== STDERR ($LogFileErr) ===" -ForegroundColor Yellow
    if (Test-Path $LogFileErr) { Get-Content $LogFileErr -Tail $Lines } else { Write-Host "(no file)" -ForegroundColor Gray }
}

# Execute action
switch ($Action) {
    "start" { Start-UvicornServer }
    "stop" { Stop-UvicornServer }
    "status" { Get-UvicornStatus }
    "tail" { Get-UvicornLogs -Lines 200 }
}
