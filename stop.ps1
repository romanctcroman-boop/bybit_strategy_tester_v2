#!/usr/bin/env pwsh
# Stop all services: Frontend, Backend, PostgreSQL, Redis

param(
    [switch]$Db,
    [switch]$All
)

# UTF-8 console
try { chcp 65001 | Out-Null } catch {}
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
}
catch {}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   BYBIT STRATEGY TESTER v2" -ForegroundColor Cyan
Write-Host "   STOP ALL SERVICES" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# If -All flag is set, also stop databases
if ($All) {
    $Db = $true
}

# Stop MCP Server (Perplexity AI Bridge)
Write-Host "Stopping MCP Server..." -ForegroundColor Yellow
$mcpPidFile = Join-Path $PSScriptRoot '.mcp.pid'
if (Test-Path $mcpPidFile) {
    try {
        $mcpPid = Get-Content $mcpPidFile
        $p = Get-Process -Id $mcpPid -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $mcpPid -Force -ErrorAction Stop
            Write-Host "    MCP Server: STOPPED (PID $mcpPid)" -ForegroundColor Green
        }
        else {
            Write-Host "    MCP Server: Not running (PID $mcpPid)" -ForegroundColor Yellow
        }
    }
    catch { Write-Host "    Failed to stop MCP Server: $($_.Exception.Message)" -ForegroundColor Red }
    Remove-Item $mcpPidFile -ErrorAction SilentlyContinue
}
else {
    Write-Host "    No .mcp.pid found (MCP Server may not be running)" -ForegroundColor DarkGray
}

# Stop frontend (Vite)
Write-Host "`nStopping Frontend..." -ForegroundColor Yellow
$vitePidFile = Join-Path $PSScriptRoot '.vite.pid'
if (Test-Path $vitePidFile) {
    try {
        $vitePid = Get-Content $vitePidFile
        $p = Get-Process -Id $vitePid -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $vitePid -Force -ErrorAction Stop
            Write-Host "    Frontend: STOPPED (PID $vitePid)" -ForegroundColor Green
        }
        else {
            Write-Host "    Frontend: Not running (PID $vitePid)" -ForegroundColor Yellow
        }
    }
    catch { Write-Host "    Failed to stop Frontend: $($_.Exception.Message)" -ForegroundColor Red }
    Remove-Item $vitePidFile -ErrorAction SilentlyContinue
}
else {
    Write-Host "    No .vite.pid found (frontend may not be running)" -ForegroundColor DarkGray
}

# Stop backend (uvicorn)
Write-Host "`nStopping Backend..." -ForegroundColor Yellow
$uvicornScript = Join-Path $PSScriptRoot 'scripts/start_uvicorn.ps1'
if (Test-Path $uvicornScript) {
    & $uvicornScript stop | Write-Output
}
else {
    Write-Host "start_uvicorn.ps1 not found; skipping backend stop" -ForegroundColor Yellow
}

# Stop Docker services (PostgreSQL + Redis)
if ($Db) {
    Write-Host "`nStopping Docker services (PostgreSQL + Redis)..." -ForegroundColor Yellow
    try {
        # Try docker compose v2
        $null = & docker compose down 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    PostgreSQL: STOPPED" -ForegroundColor Green
            Write-Host "    Redis: STOPPED" -ForegroundColor Green
        }
        else {
            # Fallback to docker-compose v1
            $null = & docker-compose down 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    PostgreSQL: STOPPED" -ForegroundColor Green
                Write-Host "    Redis: STOPPED" -ForegroundColor Green
            }
            else {
                Write-Host "    WARNING: Docker Compose failed" -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host "    ERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
}
else {
    Write-Host "`nSkipping Docker services (use -Db or -All flag to stop)" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   ALL SERVICES STOPPED" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "   Stopped services:" -ForegroundColor Yellow
Write-Host "      MCP Server (Perplexity AI)" -ForegroundColor DarkGray
Write-Host "      Frontend (Vite)" -ForegroundColor DarkGray
Write-Host "      Backend (FastAPI)" -ForegroundColor DarkGray
if ($Db) {
    Write-Host "      PostgreSQL (Docker)" -ForegroundColor DarkGray
    Write-Host "      Redis (Docker)" -ForegroundColor DarkGray
}

Write-Host "`n   To start again:" -ForegroundColor Cyan
Write-Host "     .\start.ps1" -ForegroundColor White
Write-Host ""
