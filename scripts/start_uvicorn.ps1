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
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $ProjectRoot ".run"
$PidFile = Join-Path $RunDir "uvicorn.pid"
$LogFile = Join-Path $RunDir "uvicorn.log"

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
            if ($proc) {
                return $proc
            }
        }
    }
    # Fallback: check port 8000
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
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

    # Start Uvicorn in a new window
    $startInfo = @{
        FilePath         = $VenvPython
        ArgumentList     = "-m", "uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"
        WorkingDirectory = $ProjectRoot
        PassThru         = $true
        WindowStyle      = "Minimized"
    }

    try {
        $process = Start-Process @startInfo
        
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
        
        # Check if responding
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -TimeoutSec 5 -ErrorAction Stop
            Write-Host "[OK] Server responding: $($response.status)" -ForegroundColor Green
        }
        catch {
            Write-Host "[WARN] Server not responding to health check" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[INFO] Uvicorn is not running" -ForegroundColor Gray
    }
}

# Execute action
switch ($Action) {
    "start" { Start-UvicornServer }
    "stop" { Stop-UvicornServer }
    "status" { Get-UvicornStatus }
}
