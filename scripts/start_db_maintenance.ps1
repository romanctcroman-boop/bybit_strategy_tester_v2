<#
.SYNOPSIS
    Start/Stop/Status for DB Maintenance Server
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ServiceScript = Join-Path $ProjectRoot "backend\services\db_maintenance_server.py"
$PidFile = Join-Path $ProjectRoot "logs\db_maintenance.pid"
$LogDir = Join-Path $ProjectRoot "logs"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Get-ServicePid {
    if (Test-Path $PidFile) {
        $content = Get-Content $PidFile -Raw
        if ($content) {
            return [int]$content.Trim()
        }
    }
    return $null
}

function Test-ServiceRunning {
    $servicePid = Get-ServicePid
    if ($servicePid) {
        try {
            $proc = Get-Process -Id $servicePid -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -like "*python*") {
                return $true
            }
        }
        catch { }
    }
    return $false
}

function Start-MaintenanceService {
    if (Test-ServiceRunning) {
        Write-Host "DB Maintenance Server is already running (PID: $(Get-ServicePid))" -ForegroundColor Yellow
        return
    }

    Write-Host "Starting DB Maintenance Server..." -ForegroundColor Cyan

    $proc = Start-Process -FilePath $VenvPython -ArgumentList $ServiceScript, "--port", "8001" -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru

    $proc.Id | Out-File -FilePath $PidFile -NoNewline

    Start-Sleep -Seconds 2

    if (Test-ServiceRunning) {
        Write-Host "DB Maintenance Server started (PID: $($proc.Id))" -ForegroundColor Green
        Write-Host "  API: http://localhost:8001" -ForegroundColor Gray
    }
    else {
        Write-Host "Failed to start DB Maintenance Server" -ForegroundColor Red
    }
}

function Stop-MaintenanceService {
    $servicePid = Get-ServicePid
    if (-not $servicePid) {
        Write-Host "DB Maintenance Server is not running" -ForegroundColor Yellow
        return
    }

    Write-Host "Stopping DB Maintenance Server (PID: $servicePid)..." -ForegroundColor Cyan

    try {
        Stop-Process -Id $servicePid -Force -ErrorAction SilentlyContinue
    }
    catch { }

    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force
    }

    Write-Host "DB Maintenance Server stopped" -ForegroundColor Green
}

function Show-MaintenanceStatus {
    Write-Host ""
    Write-Host "DB MAINTENANCE SERVER STATUS" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan

    if (Test-ServiceRunning) {
        Write-Host "Status: RUNNING (PID: $(Get-ServicePid))" -ForegroundColor Green
        Write-Host "API: http://localhost:8001" -ForegroundColor Gray
    }
    else {
        Write-Host "Status: STOPPED" -ForegroundColor Red
    }
    Write-Host ""
}

switch ($Action) {
    "start" { Start-MaintenanceService }
    "stop" { Stop-MaintenanceService }
    "status" { Show-MaintenanceStatus }
    "restart" {
        Stop-MaintenanceService
        Start-Sleep -Seconds 2
        Start-MaintenanceService
    }
}
