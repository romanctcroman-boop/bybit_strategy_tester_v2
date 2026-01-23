<#
.SYNOPSIS
  Start/stop/status for the Kline Database Service.

.DESCRIPTION
  Manages the Kline DB Service which handles all database operations
  for market data in a separate process.

.EXAMPLE
  .\start_kline_db_service.ps1 start
  .\start_kline_db_service.ps1 status
  .\start_kline_db_service.ps1 stop
#>

param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'start',
    
    [string]$PidFile = '.kline_db.pid',
    [string]$LogFile = 'logs/kline_db_service.log'
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path $scriptDirectory -Parent
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pidFilePath = Join-Path $projectRoot $PidFile
$logFilePath = Join-Path $projectRoot $LogFile

function Initialize-LogsDir {
    $dir = Split-Path $logFilePath -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

function Get-ServicePid {
    if (Test-Path $pidFilePath) {
        $servicePid = Get-Content $pidFilePath -ErrorAction SilentlyContinue
        if ($servicePid -and (Get-Process -Id $servicePid -ErrorAction SilentlyContinue)) {
            return [int]$servicePid
        }
        Remove-Item $pidFilePath -ErrorAction SilentlyContinue
    }
    return $null
}

switch ($Action) {
    'start' {
        Initialize-LogsDir
        
        $existingPid = Get-ServicePid
        if ($existingPid) {
            Write-Host "[OK] Kline DB Service already running (PID: $existingPid)" -ForegroundColor Green
            exit 0
        }
        
        Write-Host "[INFO] Starting Kline DB Service..." -ForegroundColor Cyan
        
        # Start the service in background
        $serviceModule = "backend.services.kline_db_service"
        
        $proc = Start-Process -FilePath $venvPython `
            -ArgumentList "-m", $serviceModule `
            -WorkingDirectory $projectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logFilePath `
            -RedirectStandardError ($logFilePath -replace '\.log$', '.err.log') `
            -PassThru
        
        if ($proc) {
            $proc.Id | Out-File $pidFilePath -Encoding ASCII
            Write-Host "[OK] Kline DB Service started (PID: $($proc.Id))" -ForegroundColor Green
            Write-Host "     Log file: $logFilePath" -ForegroundColor White
        }
        else {
            Write-Host "[ERROR] Failed to start Kline DB Service" -ForegroundColor Red
            exit 1
        }
    }
    
    'stop' {
        $existingPid = Get-ServicePid
        if (-not $existingPid) {
            Write-Host "[INFO] Kline DB Service is not running" -ForegroundColor Yellow
            exit 0
        }
        
        Write-Host "[INFO] Stopping Kline DB Service (PID: $existingPid)..." -ForegroundColor Cyan
        Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
        Remove-Item $pidFilePath -ErrorAction SilentlyContinue
        Write-Host "[OK] Kline DB Service stopped" -ForegroundColor Green
    }
    
    'status' {
        $existingPid = Get-ServicePid
        if ($existingPid) {
            $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
            Write-Host "[OK] Kline DB Service is running" -ForegroundColor Green
            Write-Host "     PID: $existingPid" -ForegroundColor White
            Write-Host "     Memory: $([math]::Round($proc.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor White
            Write-Host "     CPU Time: $($proc.TotalProcessorTime)" -ForegroundColor White
        }
        else {
            Write-Host "[INFO] Kline DB Service is not running" -ForegroundColor Yellow
        }
    }
}
