# Redis + RabbitMQ Installation Script for Bybit Strategy Tester
# Автоматическая установка Redis и RabbitMQ на Windows

param(
    [switch]$SkipRedis,
    [switch]$SkipRabbitMQ
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  REDIS + RABBITMQ INSTALLATION" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Проверка прав администратора
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "WARNING: Administrator rights needed for service installation!" -ForegroundColor Yellow
    Write-Host "Please restart PowerShell as Administrator" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ============================================
# REDIS INSTALLATION
# ============================================
if (-not $SkipRedis) {
    Write-Host "[1/2] Installing Redis..." -ForegroundColor Yellow
    Write-Host ""
    
    # Проверка существующей установки
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisService) {
        Write-Host "OK: Redis already installed (service found)" -ForegroundColor Green
        Write-Host "   Status: $($redisService.Status)" -ForegroundColor Gray
    }
    else {
        Write-Host "Downloading Redis 7.2.4 for Windows..." -ForegroundColor Cyan
        
        $redisUrl = "https://github.com/tporadowski/redis/releases/download/v7.2.4/Redis-7.2.4-Windows-x64-with-Service.zip"
        $redisZip = "$env:TEMP\redis.zip"
        $redisPath = "C:\Redis"
        
        try {
            # Скачивание
            Invoke-WebRequest -Uri $redisUrl -OutFile $redisZip -UseBasicParsing
            
            # Распаковка
            Write-Host "Extracting to $redisPath..." -ForegroundColor Cyan
            if (Test-Path $redisPath) {
                Remove-Item $redisPath -Recurse -Force
            }
            Expand-Archive -Path $redisZip -DestinationPath $redisPath -Force
            
            # Установка как сервис
            Write-Host "Installing service..." -ForegroundColor Cyan
            Set-Location $redisPath
            & .\redis-server.exe --service-install redis.windows.conf --loglevel verbose
            
            # Запуск сервиса
            Write-Host "Starting Redis..." -ForegroundColor Cyan
            & .\redis-server.exe --service-start
            
            # Добавление в PATH
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            if ($currentPath -notlike "*$redisPath*") {
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$redisPath", "Machine")
                Write-Host "OK: Redis added to PATH" -ForegroundColor Green
            }
            
            # Очистка
            Remove-Item $redisZip -Force
            
            Write-Host ""
            Write-Host "OK: Redis successfully installed!" -ForegroundColor Green
            Write-Host "   Path: $redisPath" -ForegroundColor Gray
            Write-Host "   Port: 6379" -ForegroundColor Gray
        }
        catch {
            Write-Host "ERROR: Redis installation failed: $_" -ForegroundColor Red
            exit 1
        }
    }
    
    # Проверка подключения
    Write-Host ""
    Write-Host "Checking Redis connection..." -ForegroundColor Cyan
    try {
        $redisCliPath = "C:\Redis\redis-cli.exe"
        if (Test-Path $redisCliPath) {
            $pingResult = & $redisCliPath ping
            if ($pingResult -eq "PONG") {
                Write-Host "OK: Redis is working correctly!" -ForegroundColor Green
            }
            else {
                Write-Host "WARNING: Redis started but not responding to PING" -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host "WARNING: Could not check Redis: $_" -ForegroundColor Yellow
    }
}

# ============================================
# RABBITMQ INSTALLATION
# ============================================
if (-not $SkipRabbitMQ) {
    Write-Host ""
    Write-Host "[2/2] RabbitMQ Setup..." -ForegroundColor Yellow
    Write-Host ""
    
    # Проверка существующей установки
    $rabbitService = Get-Service -Name "RabbitMQ" -ErrorAction SilentlyContinue
    if ($rabbitService) {
        Write-Host "OK: RabbitMQ already installed (service found)" -ForegroundColor Green
        Write-Host "   Status: $($rabbitService.Status)" -ForegroundColor Gray
    }
    else {
        Write-Host "WARNING: RabbitMQ requires manual installation" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Instructions:" -ForegroundColor White
        Write-Host "1. Install Erlang OTP 26:" -ForegroundColor Gray
        Write-Host "   https://www.erlang.org/downloads" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "2. Install RabbitMQ 3.13:" -ForegroundColor Gray
        Write-Host "   https://www.rabbitmq.com/install-windows.html" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "3. Enable Management Plugin:" -ForegroundColor Gray
        Write-Host "   rabbitmq-plugins enable rabbitmq_management" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "4. Create user:" -ForegroundColor Gray
        Write-Host '   rabbitmqctl add_user bybit bybitpassword' -ForegroundColor Cyan
        Write-Host '   rabbitmqctl set_user_tags bybit administrator' -ForegroundColor Cyan
        Write-Host '   rabbitmqctl set_permissions -p / bybit ".*" ".*" ".*"' -ForegroundColor Cyan
        Write-Host ""
        
        $continue = Read-Host "Is RabbitMQ already installed? (y/n)"
        if ($continue -ne "y") {
            Write-Host "ERROR: Please install RabbitMQ manually and re-run this script" -ForegroundColor Red
            exit 1
        }
    }
    
    # Проверка Management UI
    Write-Host ""
    Write-Host "Checking RabbitMQ Management UI..." -ForegroundColor Cyan
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:15672" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "OK: RabbitMQ Management UI available: http://localhost:15672" -ForegroundColor Green
            Write-Host "   Default login: guest / guest" -ForegroundColor Gray
        }
    }
    catch {
        Write-Host "WARNING: Management UI not available (plugin may not be enabled)" -ForegroundColor Yellow
    }
}

# ============================================
# UPDATE .env
# ============================================
Write-Host ""
Write-Host "Updating .env configuration..." -ForegroundColor Yellow

$envPath = Join-Path $scriptPath ".env"
$envExample = Join-Path $scriptPath ".env.example"

# Создать .env если его нет
if (-not (Test-Path $envPath)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envPath
        Write-Host "OK: Created .env from .env.example" -ForegroundColor Green
    }
    else {
        New-Item -Path $envPath -ItemType File -Force | Out-Null
        Write-Host "OK: Created empty .env" -ForegroundColor Green
    }
}

# Добавить параметры Redis и RabbitMQ
$envContent = Get-Content $envPath -Raw -ErrorAction SilentlyContinue

$redisConfig = @'

# Redis Configuration (added by install_redis_rabbitmq.ps1)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

'@

$rabbitmqConfig = @'

# RabbitMQ Configuration (added by install_redis_rabbitmq.ps1)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=bybit
RABBITMQ_PASS=bybitpassword
RABBITMQ_VHOST=/

'@

if ($envContent -notmatch "REDIS_HOST") {
    Add-Content -Path $envPath -Value $redisConfig
    Write-Host "OK: Added Redis parameters to .env" -ForegroundColor Green
}

if ($envContent -notmatch "RABBITMQ_HOST") {
    Add-Content -Path $envPath -Value $rabbitmqConfig
    Write-Host "OK: Added RabbitMQ parameters to .env" -ForegroundColor Green
}

# ============================================
# FINAL INFO
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Summary:" -ForegroundColor White
Write-Host ""

if (-not $SkipRedis) {
    Write-Host "Redis:" -ForegroundColor Cyan
    Write-Host "  OK: Installed and running" -ForegroundColor Green
    Write-Host "  Address: localhost:6379" -ForegroundColor Gray
    Write-Host "  Password: not set" -ForegroundColor Gray
    Write-Host "  Test: redis-cli ping" -ForegroundColor Gray
    Write-Host ""
}

if (-not $SkipRabbitMQ) {
    Write-Host "RabbitMQ:" -ForegroundColor Cyan
    Write-Host "  AMQP: localhost:5672" -ForegroundColor Gray
    Write-Host "  Management UI: http://localhost:15672" -ForegroundColor Gray
    Write-Host "  Login: bybit / bybitpassword" -ForegroundColor Gray
    Write-Host "  Test: curl http://localhost:15672" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Install Python dependencies:" -ForegroundColor Gray
Write-Host "     .venv\Scripts\python.exe -m pip install redis==5.0.1 celery==5.3.4" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Run integration tests:" -ForegroundColor Gray
Write-Host "     .venv\Scripts\python.exe -m pytest tests\backend\test_redis_integration.py -v" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Start Celery workers:" -ForegroundColor Gray
Write-Host "     Follow instructions in docs/CELERY_SETUP.md" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to finish"
