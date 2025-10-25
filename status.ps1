#!/usr/bin/env pwsh
# Status report for backend/frontend

param(
    [string]$ApiHost = '127.0.0.1',
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173
)

# UTF-8 console
try { chcp 65001 | Out-Null } catch {}
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
}
catch {}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "BYBIT STRATEGY TESTER v2" -ForegroundColor Cyan
Write-Host "STATUS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Backend PID
$pidFile = Join-Path $PSScriptRoot '.uvicorn.pid'
if (Test-Path $pidFile) {
    $backendPid = Get-Content $pidFile
    $bp = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
    if ($bp) {
        Write-Host "Backend: running (PID $backendPid)" -ForegroundColor Green
    }
    else {
        Write-Host "Backend: not running (stale PID $backendPid)" -ForegroundColor Yellow
    }
}
else {
    Write-Host "Backend: no PID file" -ForegroundColor Yellow
}

# Frontend PID
$vitePidFile = Join-Path $PSScriptRoot '.vite.pid'
if (Test-Path $vitePidFile) {
    $vitePid = Get-Content $vitePidFile
    $vp = Get-Process -Id $vitePid -ErrorAction SilentlyContinue
    if ($vp) {
        Write-Host "Frontend: running (PID $vitePid)" -ForegroundColor Green
    }
    else {
        Write-Host "Frontend: not running (stale PID $vitePid)" -ForegroundColor Yellow
    }
}
else {
    Write-Host "Frontend: no PID file" -ForegroundColor Yellow
}

# API health
try {
    $h = Invoke-RestMethod -Uri "http://${ApiHost}:${ApiPort}/api/v1/healthz" -TimeoutSec 4 -ErrorAction Stop
    Write-Host "API Health: $($h.status)" -ForegroundColor Green
}
catch { Write-Host "API Health: ERROR $($_.Exception.Message)" -ForegroundColor Red }

# Exchange probe
try {
    $x = Invoke-RestMethod -Uri "http://${ApiHost}:${ApiPort}/api/v1/exchangez" -TimeoutSec 6 -ErrorAction Stop
    $lat = ('{0:N1}' -f ($x.latency_ms))
    Write-Host "Exchange: $($x.status) (latency ${lat} ms)" -ForegroundColor Green
}
catch { Write-Host "Exchange: ERROR $($_.Exception.Message)" -ForegroundColor Red }

# Frontend HTTP check
try {
    $rootResp = Invoke-WebRequest -Uri "http://localhost:${FrontendPort}/" -TimeoutSec 6 -ErrorAction Stop
    Write-Host "Frontend: OK (HTTP $($rootResp.StatusCode))" -ForegroundColor Green
}
catch { Write-Host "Frontend: starting or down - $($_.Exception.Message)" -ForegroundColor Yellow }

Write-Host "\nEndpoints:" -ForegroundColor Yellow
Write-Host ("  Backend:  http://{0}:{1}" -f $ApiHost, $ApiPort) -ForegroundColor Magenta
Write-Host ("  Frontend: http://localhost:{0}" -f $FrontendPort) -ForegroundColor Magenta
