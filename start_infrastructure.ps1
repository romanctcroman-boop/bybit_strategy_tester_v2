# Bybit Strategy Tester - Infrastructure Manager
# Manages Redis, RabbitMQ, Celery, and FastAPI services

param(
    [switch]$StopAll,
    [switch]$StatusOnly
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester - Infrastructure Manager" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# STOP ALL
if ($StopAll) {
    Write-Host "Stopping all processes..." -ForegroundColor Yellow
    Write-Host ""
    
    Get-Process | Where-Object { $_.ProcessName -eq "celery" } | ForEach-Object {
        Write-Host "  [Celery] Stopping PID: $($_.Id)" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force
    }
    
    Get-Process | Where-Object { $_.ProcessName -eq "python" } | ForEach-Object {
        Write-Host "  [Python] Stopping PID: $($_.Id)" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force
    }
    
    Write-Host ""
    Write-Host "[OK] All processes stopped" -ForegroundColor Green
    Write-Host ""
    exit 0
}

# STATUS CHECK
if ($StatusOnly) {
    Write-Host "Infrastructure Status:" -ForegroundColor Cyan
    Write-Host ""
    
    $redis = Get-Service Redis -ErrorAction SilentlyContinue
    if ($redis -and $redis.Status -eq "Running") {
        Write-Host "[OK] Redis: Running (port 6379)" -ForegroundColor Green
    }
    else {
        Write-Host "[X]  Redis: Not running" -ForegroundColor Red
    }
    
    $rabbitmq = Get-Service RabbitMQ -ErrorAction SilentlyContinue
    if ($rabbitmq -and $rabbitmq.Status -eq "Running") {
        Write-Host "[OK] RabbitMQ: Running (port 5672)" -ForegroundColor Green
        Write-Host "     Management: http://localhost:15672" -ForegroundColor Gray
    }
    else {
        Write-Host "[X]  RabbitMQ: Not running" -ForegroundColor Red
    }
    
    $celery = Get-Process -Name celery -ErrorAction SilentlyContinue
    if ($celery) {
        Write-Host "[OK] Celery: Running (PID: $($celery.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "[X]  Celery: Not running" -ForegroundColor Red
    }
    
    try {
        Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 | Out-Null
        Write-Host "[OK] FastAPI: Running (port 8000)" -ForegroundColor Green
        Write-Host "     Docs: http://localhost:8000/docs" -ForegroundColor Gray
    }
    catch {
        Write-Host "[X]  FastAPI: Not running" -ForegroundColor Red
    }
    
    $wsworker = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*bybit_ws_worker*" } | Select-Object -First 1
    if ($wsworker) {
        Write-Host "[OK] Bybit WS Worker: Running (PID: $($wsworker.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "[X]  Bybit WS Worker: Not running" -ForegroundColor Red
    }
    
    Write-Host ""
    exit 0
}

# START INFRASTRUCTURE
Write-Host "[1/5] Redis..." -ForegroundColor Cyan
$redis = Get-Service Redis -ErrorAction SilentlyContinue
if ($redis -and $redis.Status -eq "Running") {
    Write-Host "   [OK] Already running" -ForegroundColor Green
}
else {
    Write-Host "   [!] Not running - start manually" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[2/5] RabbitMQ..." -ForegroundColor Cyan
$rabbitmq = Get-Service RabbitMQ -ErrorAction SilentlyContinue
if ($rabbitmq -and $rabbitmq.Status -eq "Running") {
    Write-Host "   [OK] Already running" -ForegroundColor Green
}
else {
    Write-Host "   [X] Not running!" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "[3/5] Celery Worker..." -ForegroundColor Cyan
$celery = Get-Process -Name celery -ErrorAction SilentlyContinue
if ($celery) {
    Write-Host "   [!] Already running (PID: $($celery.Id))" -ForegroundColor Yellow
}
else {
    $proc = Start-Process -FilePath ".venv\Scripts\celery.exe" -ArgumentList "-A", "backend.celery_app", "worker", "-Q", "optimization,backtest", "-P", "solo", "--loglevel=info" -WindowStyle Hidden -PassThru
    Write-Host "   [OK] Started (PID: $($proc.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 3
}
Write-Host ""

Write-Host "[4/5] FastAPI Server..." -ForegroundColor Cyan
try {
    Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 | Out-Null
    Write-Host "   [!] Already running" -ForegroundColor Yellow
}
catch {
    $proc = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" -WindowStyle Hidden -PassThru
    Write-Host "   [OK] Started (PID: $($proc.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 5
}
Write-Host ""

Write-Host "[5/5] Bybit WebSocket Worker..." -ForegroundColor Cyan
$wsworker = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*bybit_ws_worker*" } | Select-Object -First 1
if ($wsworker) {
    Write-Host "   [!] Already running (PID: $($wsworker.Id))" -ForegroundColor Yellow
}
else {
    $proc = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m", "backend.workers.bybit_ws_worker", "--symbols", "BTCUSDT,ETHUSDT,SOLUSDT", "--timeframes", "1,5,15" -WindowStyle Hidden -PassThru
    Write-Host "   [OK] Started (PID: $($proc.Id))" -ForegroundColor Green
    Write-Host "        Symbols: BTCUSDT, ETHUSDT, SOLUSDT" -ForegroundColor Gray
    Write-Host "        Timeframes: 1m, 5m, 15m" -ForegroundColor Gray
    Start-Sleep -Seconds 3
}
Write-Host ""

Write-Host "==================================================" -ForegroundColor Green
Write-Host "  INFRASTRUCTURE READY!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Links:" -ForegroundColor Cyan
Write-Host "   Swagger UI:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   RabbitMQ UI: http://localhost:15672" -ForegroundColor White
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "   Stop all:    .\start_infrastructure.ps1 -StopAll" -ForegroundColor Yellow
Write-Host "   Status:      .\start_infrastructure.ps1 -StatusOnly" -ForegroundColor Yellow
Write-Host ""
