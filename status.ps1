#!/usr/bin/env pwsh
# Bybit Strategy Tester v2 - Universal Launcher
# Usage: 
#   .\status.ps1 start    - Start all services
#   .\status.ps1 stop     - Stop all services
#   .\status.ps1 status   - Check status
#   Press F5 in VS Code   - Auto-start if services are down

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "")]
    [string]$Action = ""
)

$ApiHost = "127.0.0.1"
$ApiPort = 8000
$FrontendPort = 5173

# Auto-detect: if sourced (F5) and services down → start
if ($Action -eq "" -or $Action -eq "status") {
    $backendRunning = $false
    $frontendRunning = $false
    
    if (Test-Path "$PSScriptRoot\.backend.pid") {
        $backendPid = Get-Content "$PSScriptRoot\.backend.pid"
        if (Get-Process -Id $backendPid -ErrorAction SilentlyContinue) {
            $backendRunning = $true
        }
    }
    
    if (Test-Path "$PSScriptRoot\.frontend.pid") {
        $frontendPid = Get-Content "$PSScriptRoot\.frontend.pid"
        if (Get-Process -Id $frontendPid -ErrorAction SilentlyContinue) {
            $frontendRunning = $true
        }
    }
    
    # If both down and no explicit action → auto-start (F5 behavior)
    if (-not $backendRunning -and -not $frontendRunning -and $Action -eq "") {
        $Action = "start"
    }
    elseif ($Action -eq "") {
        $Action = "status"
    }
}

function Show-Banner {
    Write-Host ""
    Write-Host "" -ForegroundColor Cyan
    Write-Host "     BYBIT STRATEGY TESTER v2 " -ForegroundColor Green
    Write-Host "" -ForegroundColor Cyan
    Write-Host ""
}

function Start-AllServices {
    Show-Banner
    Write-Host " Starting Full Stack.." -ForegroundColor Cyan
    Write-Host ""
    
    # Check Redis
    Write-Host " Checking Redis..." -ForegroundColor Yellow
    $redisProcess = Get-Process redis-server -ErrorAction SilentlyContinue
    if ($redisProcess) {
        Write-Host "   Redis: Already running (PID $($redisProcess.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "   Redis: Not running - attempting to start..." -ForegroundColor Yellow
        # Try to start Redis if installed
        $redisPath = Get-Command redis-server -ErrorAction SilentlyContinue
        if ($redisPath) {
            Start-Process redis-server -WindowStyle Hidden
            Start-Sleep -Seconds 2
            Write-Host "   Redis: Started" -ForegroundColor Green
        }
        else {
            Write-Host "   Redis: Not installed - install with: winget install Redis.Redis" -ForegroundColor Yellow
        }
    }
    
    # Check PostgreSQL
    Write-Host " Checking PostgreSQL..." -ForegroundColor Yellow
    $pgProcess = Get-Process postgres -ErrorAction SilentlyContinue
    if ($pgProcess) {
        Write-Host "   PostgreSQL: Already running" -ForegroundColor Green
    }
    else {
        Write-Host "   PostgreSQL: Not running (optional for full features)" -ForegroundColor Yellow
    }
    
    # Backend
    Write-Host " Starting Backend..." -ForegroundColor Yellow
    $backendCmd = "cd '$PSScriptRoot'; `$env:PYTHONPATH='$PSScriptRoot'; .\.venv\Scripts\Activate.ps1; python -m uvicorn backend.api.app:app --host $ApiHost --port $ApiPort --reload"
    $backend = Start-Process powershell -PassThru -ArgumentList "-NoExit", "-Command", $backendCmd
    $backend.Id | Out-File "$PSScriptRoot\.backend.pid" -Encoding utf8
    Start-Sleep -Seconds 3
    Write-Host "   Backend PID: $($backend.Id)" -ForegroundColor Green
    
    # Frontend
    Write-Host " Starting Frontend..." -ForegroundColor Yellow
    $frontendCmd = "cd '$PSScriptRoot\frontend'; npm run dev"
    $frontend = Start-Process powershell -PassThru -ArgumentList "-NoExit", "-Command", $frontendCmd
    $frontend.Id | Out-File "$PSScriptRoot\.frontend.pid" -Encoding utf8
    Start-Sleep -Seconds 2
    Write-Host "   Frontend PID: $($frontend.Id)" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "=" -ForegroundColor DarkGray
    Write-Host " Full Stack Started!" -ForegroundColor Green
    Write-Host "=" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host " Frontend:  http://localhost:$FrontendPort/" -ForegroundColor Cyan
    Write-Host " Backend:   http://${ApiHost}:${ApiPort}/metrics" -ForegroundColor Cyan
    Write-Host " API Docs:  http://${ApiHost}:${ApiPort}/docs" -ForegroundColor Cyan
    Write-Host ""
    
    # Wait for services to be ready
    Write-Host " Waiting for services to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Open browser
    Write-Host " Opening browser..." -ForegroundColor Green
    Start-Process "http://localhost:$FrontendPort/"
    
    Write-Host ""
    Write-Host " Run '.\status.ps1 status' to check health" -ForegroundColor Yellow
    Write-Host ""
}

function Stop-AllServices {
    Show-Banner
    Write-Host " Stopping All Services.." -ForegroundColor Yellow
    Write-Host ""
    
    if (Test-Path "$PSScriptRoot\.backend.pid") {
        $backendPid = Get-Content "$PSScriptRoot\.backend.pid"
        Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue
        Write-Host "   Backend stopped" -ForegroundColor Green
        Remove-Item "$PSScriptRoot\.backend.pid" -Force
    }
    
    if (Test-Path "$PSScriptRoot\.frontend.pid") {
        $frontendPid = Get-Content "$PSScriptRoot\.frontend.pid"
        Stop-Process -Id $frontendPid -Force -ErrorAction SilentlyContinue
        Write-Host "   Frontend stopped" -ForegroundColor Green
        Remove-Item "$PSScriptRoot\.frontend.pid" -Force
    }
    
    Write-Host ""
    Write-Host " All services stopped" -ForegroundColor Green
}

function Show-Status {
    Show-Banner
    Write-Host " System Status" -ForegroundColor Cyan
    Write-Host ""
    
    # Check Backend
    if (Test-Path "$PSScriptRoot\.backend.pid") {
        $backendPid = Get-Content "$PSScriptRoot\.backend.pid"
        if (Get-Process -Id $backendPid -ErrorAction SilentlyContinue) {
            Write-Host "   Backend:     RUNNING (PID $backendPid)" -ForegroundColor Green
        }
        else {
            Write-Host "   Backend:     STOPPED" -ForegroundColor Red
        }
    }
    else {
        Write-Host "   Backend:     NOT RUNNING" -ForegroundColor Red
    }
    
    # Check Frontend
    if (Test-Path "$PSScriptRoot\.frontend.pid") {
        $frontendPid = Get-Content "$PSScriptRoot\.frontend.pid"
        if (Get-Process -Id $frontendPid -ErrorAction SilentlyContinue) {
            Write-Host "   Frontend:    RUNNING (PID $frontendPid)" -ForegroundColor Green
        }
        else {
            Write-Host "   Frontend:    STOPPED" -ForegroundColor Red
        }
    }
    else {
        Write-Host "   Frontend:    NOT RUNNING" -ForegroundColor Red
    }
    
    # Check Redis
    $redisProcess = Get-Process redis-server -ErrorAction SilentlyContinue
    if ($redisProcess) {
        Write-Host "   Redis:       RUNNING (PID $($redisProcess.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "   Redis:       NOT RUNNING" -ForegroundColor Yellow
    }
    
    # Check PostgreSQL
    $pgProcess = Get-Process postgres -ErrorAction SilentlyContinue
    if ($pgProcess) {
        Write-Host "   PostgreSQL:  RUNNING" -ForegroundColor Green
    }
    else {
        Write-Host "   PostgreSQL:  NOT RUNNING" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "=" -ForegroundColor DarkGray
    Write-Host " Health Checks:" -ForegroundColor Cyan
    Write-Host ""
    
    # Backend health checks
    try {
        Invoke-WebRequest -Uri "http://${ApiHost}:${ApiPort}/metrics" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "   Backend /metrics:        OK" -ForegroundColor Green
    }
    catch {
        Write-Host "   Backend /metrics:        OFFLINE" -ForegroundColor Red
    }
    
    try {
        Invoke-WebRequest -Uri "http://${ApiHost}:${ApiPort}/api/v1/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "   Backend /health:         OK" -ForegroundColor Green
    }
    catch {
        Write-Host "   Backend /health:         OFFLINE" -ForegroundColor Red
    }
    
    try {
        Invoke-WebRequest -Uri "http://${ApiHost}:${ApiPort}/api/dashboard/kpi" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "   Dashboard KPI:           OK" -ForegroundColor Green
    }
    catch {
        Write-Host "   Dashboard KPI:           OFFLINE" -ForegroundColor Red
    }
    
    # Frontend health check
    try {
        Invoke-WebRequest -Uri "http://localhost:$FrontendPort/" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "   Frontend HTTP:           OK" -ForegroundColor Green
    }
    catch {
        Write-Host "   Frontend HTTP:           OFFLINE" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "=" -ForegroundColor DarkGray
    Write-Host " Quick Links:" -ForegroundColor Cyan
    Write-Host "  Frontend:    http://localhost:$FrontendPort/" -ForegroundColor Magenta
    Write-Host "  API Docs:    http://${ApiHost}:${ApiPort}/docs" -ForegroundColor Magenta
    Write-Host "  Metrics:     http://${ApiHost}:${ApiPort}/metrics" -ForegroundColor Magenta
    Write-Host "  Health:      http://${ApiHost}:${ApiPort}/api/v1/health" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "=" -ForegroundColor DarkGray
    Write-Host " Commands:" -ForegroundColor Yellow
    Write-Host "  .\status.ps1 start    " -NoNewline -ForegroundColor White
    Write-Host "- Start all services" -ForegroundColor DarkGray
    Write-Host "  .\status.ps1 stop     " -NoNewline -ForegroundColor White
    Write-Host "- Stop all services" -ForegroundColor DarkGray
    Write-Host "  Press F5 in VS Code   " -NoNewline -ForegroundColor White
    Write-Host "- Auto-start if down" -ForegroundColor DarkGray
    Write-Host ""
}

# Main
switch ($Action) {
    "start" { Start-AllServices }
    "stop" { Stop-AllServices }
    "restart" { Stop-AllServices; Start-Sleep 2; Start-AllServices }
    default { Show-Status }
}
