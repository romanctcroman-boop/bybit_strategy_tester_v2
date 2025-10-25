#!/usr/bin/env pwsh
# Stop backend/frontend, optional Postgres

param(
    [switch]$Db
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
Write-Host "STOP SERVICES" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Stop frontend (Vite)
$vitePidFile = Join-Path $PSScriptRoot '.vite.pid'
if (Test-Path $vitePidFile) {
    try {
        $vitePid = Get-Content $vitePidFile
        $p = Get-Process -Id $vitePid -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $vitePid -Force -ErrorAction Stop
            Write-Host "Stopped Frontend (PID $vitePid)" -ForegroundColor Green
        }
        else {
            Write-Host "Frontend PID $vitePid not running" -ForegroundColor Yellow
        }
    }
    catch { Write-Host "Failed to stop Frontend: $($_.Exception.Message)" -ForegroundColor Red }
    Remove-Item $vitePidFile -ErrorAction SilentlyContinue
}
else {
    Write-Host "No .vite.pid found (frontend may not be running)" -ForegroundColor Yellow
}

# Stop backend (uvicorn)
$uvicornScript = Join-Path $PSScriptRoot 'scripts/start_uvicorn.ps1'
if (Test-Path $uvicornScript) {
    & $uvicornScript stop | Write-Output
}
else {
    Write-Host "start_uvicorn.ps1 not found; skipping backend stop" -ForegroundColor Yellow
}

# Optional: stop Postgres container
if ($Db) {
    $composeFile = Join-Path $PSScriptRoot 'docker-compose.postgres.yml'
    if (Test-Path $composeFile) {
        Write-Host "Stopping Postgres (docker compose down)..." -ForegroundColor Yellow
        docker compose -f $composeFile down --volumes --remove-orphans
    }
    else {
        Write-Host "docker-compose.postgres.yml not found; skipping DB stop" -ForegroundColor Yellow
    }
}

Write-Host "`nDone." -ForegroundColor Green
