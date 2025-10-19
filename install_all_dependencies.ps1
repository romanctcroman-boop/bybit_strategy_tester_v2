# ===============================================================================
# ПОЛНАЯ УСТАНОВКА ВСЕХ ЗАВИСИМОСТЕЙ: Bybit Strategy Tester v2.0
# ===============================================================================
# Дата: 16 октября 2025
# Назначение: Автоматическая установка ВСЕХ зависимостей и расширений
# ===============================================================================

param(
    [switch]$SkipPostgreSQL = $false,
    [switch]$SkipRedis = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = "Continue"

Write-Host "`n===============================================================================" -ForegroundColor Cyan
Write-Host "  ПОЛНАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ" -ForegroundColor Cyan
Write-Host "===============================================================================`n" -ForegroundColor Cyan

# ===============================================================================
# ФУНКЦИЯ: Проверка установки программы
# ===============================================================================

function Test-ProgramInstalled {
    param([string]$ProgramName, [string]$Command)
    
    try {
        $result = & $Command --version 2>&1
        return $true
    } catch {
        return $false
    }
}

# ===============================================================================
# ЭТАП 1: ПРОВЕРКА ОКРУЖЕНИЯ
# ===============================================================================

Write-Host "[1/7] Проверка системного окружения...`n" -ForegroundColor Yellow

# Python
if (Test-ProgramInstalled -ProgramName "Python" -Command "python") {
    $pyVersion = python --version
    Write-Host "  [OK] Python: $pyVersion" -ForegroundColor Green
} else {
    Write-Host "  [X] Python НЕ НАЙДЕН!" -ForegroundColor Red
    Write-Host "      Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Node.js
if (Test-ProgramInstalled -ProgramName "Node.js" -Command "node") {
    $nodeVersion = node --version
    Write-Host "  [OK] Node.js: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "  [X] Node.js НЕ НАЙДЕН!" -ForegroundColor Red
    exit 1
}

# Git
if (Test-ProgramInstalled -ProgramName "Git" -Command "git") {
    $gitVersion = git --version
    Write-Host "  [OK] Git: $gitVersion" -ForegroundColor Green
} else {
    Write-Host "  [!] Git не найден (не критично)" -ForegroundColor Yellow
}

Write-Host ""

# ===============================================================================
# ЭТАП 2: ПРОВЕРКА POSTGRESQL
# ===============================================================================

Write-Host "[2/7] Проверка PostgreSQL...`n" -ForegroundColor Yellow

$postgresInstalled = $false

if (-not $SkipPostgreSQL) {
    try {
        $pgVersion = & psql --version 2>&1
        if ($pgVersion -match "psql") {
            Write-Host "  [OK] PostgreSQL установлен: $pgVersion" -ForegroundColor Green
            $postgresInstalled = $true
            
            # Проверка TimescaleDB
            Write-Host "  [?] Проверка TimescaleDB..." -ForegroundColor Cyan
            $timescaleCheck = & psql -U postgres -c "\dx timescaledb" 2>&1
            if ($timescaleCheck -match "timescaledb") {
                Write-Host "  [OK] TimescaleDB установлен" -ForegroundColor Green
            } else {
                Write-Host "  [!] TimescaleDB НЕ НАЙДЕН" -ForegroundColor Yellow
                Write-Host "      Установите: https://docs.timescale.com/self-hosted/latest/install/" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "  [X] PostgreSQL НЕ УСТАНОВЛЕН" -ForegroundColor Red
        Write-Host "      Требуется для production и psycopg2-binary" -ForegroundColor Yellow
        Write-Host "      Download: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
        Write-Host "`n      УСТАНОВКА:" -ForegroundColor Cyan
        Write-Host "      1. Download PostgreSQL 16 installer" -ForegroundColor White
        Write-Host "      2. Запустить installer (password для postgres)" -ForegroundColor White
        Write-Host "      3. Добавить C:\Program Files\PostgreSQL\16\bin в PATH" -ForegroundColor White
        Write-Host "      4. Перезапустить PowerShell" -ForegroundColor White
        Write-Host "      5. Запустить этот скрипт снова`n" -ForegroundColor White
    }
} else {
    Write-Host "  [SKIP] PostgreSQL проверка пропущена (--SkipPostgreSQL)" -ForegroundColor Yellow
}

Write-Host ""

# ===============================================================================
# ЭТАП 3: ПРОВЕРКА REDIS
# ===============================================================================

Write-Host "[3/7] Проверка Redis...`n" -ForegroundColor Yellow

$redisInstalled = $false

if (-not $SkipRedis) {
    try {
        $redisVersion = & redis-server --version 2>&1
        if ($redisVersion -match "Redis") {
            Write-Host "  [OK] Redis установлен: $redisVersion" -ForegroundColor Green
            $redisInstalled = $true
            
            # Проверка запущен ли Redis
            try {
                $redisPing = & redis-cli ping 2>&1
                if ($redisPing -match "PONG") {
                    Write-Host "  [OK] Redis запущен и отвечает" -ForegroundColor Green
                } else {
                    Write-Host "  [!] Redis не отвечает - запустите вручную" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "  [!] Redis не отвечает - запустите вручную" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "  [X] Redis НЕ УСТАНОВЛЕН" -ForegroundColor Red
        Write-Host "      Опционально для development, нужен для production" -ForegroundColor Yellow
        Write-Host "      Download: https://github.com/tporadowski/redis/releases" -ForegroundColor Yellow
        Write-Host "`n      УСТАНОВКА:" -ForegroundColor Cyan
        Write-Host "      1. Download Redis-x64-5.0.14.1.msi" -ForegroundColor White
        Write-Host "      2. Установить как Windows Service" -ForegroundColor White
        Write-Host "      3. Port: 6379 (default)`n" -ForegroundColor White
    }
} else {
    Write-Host "  [SKIP] Redis проверка пропущена (--SkipRedis)" -ForegroundColor Yellow
}

Write-Host ""

# ===============================================================================
# ЭТАП 4: УСТАНОВКА BACKEND PYTHON ПАКЕТОВ
# ===============================================================================

Write-Host "[4/7] Установка Backend Python пакетов...`n" -ForegroundColor Yellow

$backendPath = "D:\bybit_strategy_tester_v2\backend"
Set-Location $backendPath

# Проверка venv
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "  [!] Virtual environment не найден - создаю..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "  [OK] Virtual environment создан" -ForegroundColor Green
}

# Активация venv и установка пакетов
Write-Host "  [~] Активация venv и установка пакетов..." -ForegroundColor Cyan
Write-Host "      Это может занять 5-10 минут...`n" -ForegroundColor Gray

$packages = @(
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "sqlalchemy==2.0.25",
    "alembic==1.13.0",
    "redis==5.0.1",
    "celery==5.3.4",
    "pandas==2.1.4",
    "numpy==1.26.2",
    "pybit==5.7.0",
    "python-jose[cryptography]==3.3.0",
    "python-dotenv==1.0.0",
    "loguru==0.7.2",
    "pytest==7.4.3",
    "pytest-asyncio==0.21.1",
    "httpx==0.26.0",
    "aiohttp==3.9.1",
    "websockets==12.0",
    "python-multipart==0.0.6"
)

# Если PostgreSQL установлен, добавить psycopg2-binary
if ($postgresInstalled) {
    $packages += "psycopg2-binary==2.9.9"
    $packages += "asyncpg==0.29.0"
}

# Установка через pip
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null

foreach ($pkg in $packages) {
    Write-Host "  [~] Установка $pkg..." -ForegroundColor Gray
    & ".\venv\Scripts\pip.exe" install $pkg --quiet
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $pkg" -ForegroundColor Green
    } else {
        Write-Host "  [X] $pkg - ОШИБКА!" -ForegroundColor Red
    }
}

Write-Host "`n  [~] Проверка установленных пакетов..." -ForegroundColor Cyan
$installedCount = (& ".\venv\Scripts\pip.exe" list --format=json | ConvertFrom-Json).Count
Write-Host "  [OK] Установлено пакетов: $installedCount`n" -ForegroundColor Green

Write-Host ""

# ===============================================================================
# ЭТАП 5: ПРОВЕРКА FRONTEND ЗАВИСИМОСТЕЙ
# ===============================================================================

Write-Host "[5/7] Проверка Frontend зависимостей...`n" -ForegroundColor Yellow

$frontendPath = "D:\bybit_strategy_tester_v2\frontend"
Set-Location $frontendPath

if (Test-Path "node_modules") {
    $nodeModulesCount = (Get-ChildItem node_modules -Directory).Count
    Write-Host "  [OK] node_modules существует ($nodeModulesCount пакетов)" -ForegroundColor Green
    
    # Проверка ключевых пакетов
    $keyPackages = @("react", "electron", "lightweight-charts", "vite", "typescript")
    foreach ($pkg in $keyPackages) {
        if (Test-Path "node_modules\$pkg") {
            Write-Host "  [OK] $pkg установлен" -ForegroundColor Green
        } else {
            Write-Host "  [X] $pkg НЕ НАЙДЕН!" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  [X] node_modules НЕ СУЩЕСТВУЕТ!" -ForegroundColor Red
    Write-Host "  [~] Запуск npm install..." -ForegroundColor Yellow
    Write-Host "      Это может занять 3-5 минут...`n" -ForegroundColor Gray
    
    npm install --legacy-peer-deps
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n  [OK] Frontend зависимости установлены" -ForegroundColor Green
    } else {
        Write-Host "`n  [X] Ошибка при установке frontend зависимостей!" -ForegroundColor Red
    }
}

Write-Host ""

# ===============================================================================
# ЭТАП 6: СОЗДАНИЕ .ENV ФАЙЛА
# ===============================================================================

Write-Host "[6/7] Создание .env файла...`n" -ForegroundColor Yellow

$projectRoot = "D:\bybit_strategy_tester_v2"
Set-Location $projectRoot

if (-not (Test-Path ".env") -or $Force) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env" -Force
        Write-Host "  [OK] .env создан из .env.example" -ForegroundColor Green
        Write-Host "      Отредактируйте пароли и ключи API!" -ForegroundColor Yellow
    } else {
        # Создать базовый .env
        $envContent = @"
# Database Configuration
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/bybit_strategy_tester
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True

# CORS
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Bybit API (опционально)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=True

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Security
SECRET_KEY=change-this-secret-key-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
"@
        $envContent | Out-File -FilePath ".env" -Encoding UTF8
        Write-Host "  [OK] .env создан" -ForegroundColor Green
        Write-Host "      ВАЖНО: Отредактируйте пароли!" -ForegroundColor Red
    }
} else {
    Write-Host "  [SKIP] .env уже существует" -ForegroundColor Yellow
}

Write-Host ""

# ===============================================================================
# ЭТАП 7: СОЗДАНИЕ БАЗЫ ДАННЫХ
# ===============================================================================

Write-Host "[7/7] Создание базы данных...`n" -ForegroundColor Yellow

if ($postgresInstalled) {
    # Проверка существования БД
    $dbExists = & psql -U postgres -lqt 2>&1 | Select-String -Pattern "bybit_strategy_tester"
    
    if ($dbExists) {
        Write-Host "  [OK] База данных 'bybit_strategy_tester' уже существует" -ForegroundColor Green
    } else {
        Write-Host "  [~] Создание базы данных..." -ForegroundColor Cyan
        
        $createDbCommand = "createdb -U postgres bybit_strategy_tester"
        Invoke-Expression $createDbCommand 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] База данных создана" -ForegroundColor Green
            
            # Установка TimescaleDB extension
            Write-Host "  [~] Установка TimescaleDB extension..." -ForegroundColor Cyan
            $extensionCommand = "psql -U postgres -d bybit_strategy_tester -c 'CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;'"
            Invoke-Expression $extensionCommand 2>&1 | Out-Null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [OK] TimescaleDB extension установлен" -ForegroundColor Green
            } else {
                Write-Host "  [!] Не удалось установить TimescaleDB extension" -ForegroundColor Yellow
                Write-Host "      Установите TimescaleDB вручную" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [X] Ошибка при создании базы данных" -ForegroundColor Red
            Write-Host "      Проверьте что PostgreSQL запущен" -ForegroundColor Yellow
            Write-Host "      И у вас есть права создания БД" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [SKIP] PostgreSQL не установлен - БД не создана" -ForegroundColor Yellow
    Write-Host "         Можно работать без БД в development режиме" -ForegroundColor Gray
}

Write-Host ""

# ===============================================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ===============================================================================

Write-Host "===============================================================================" -ForegroundColor Green
Write-Host "  УСТАНОВКА ЗАВЕРШЕНА!" -ForegroundColor Green
Write-Host "===============================================================================`n" -ForegroundColor Green

Write-Host "СТАТУС КОМПОНЕНТОВ:`n" -ForegroundColor Cyan

# Проверка статуса
$backendOK = Test-Path "$backendPath\venv\Scripts\python.exe"
$frontendOK = Test-Path "$frontendPath\node_modules"
$envOK = Test-Path "$projectRoot\.env"

if ($backendOK) {
    Write-Host "  [OK] Backend Python environment" -ForegroundColor Green
} else {
    Write-Host "  [X] Backend Python environment" -ForegroundColor Red
}

if ($frontendOK) {
    Write-Host "  [OK] Frontend Node.js environment" -ForegroundColor Green
} else {
    Write-Host "  [X] Frontend Node.js environment" -ForegroundColor Red
}

if ($postgresInstalled) {
    Write-Host "  [OK] PostgreSQL + TimescaleDB" -ForegroundColor Green
} else {
    Write-Host "  [!] PostgreSQL (требуется установка)" -ForegroundColor Yellow
}

if ($redisInstalled) {
    Write-Host "  [OK] Redis" -ForegroundColor Green
} else {
    Write-Host "  [!] Redis (опционально)" -ForegroundColor Yellow
}

if ($envOK) {
    Write-Host "  [OK] .env файл создан" -ForegroundColor Green
} else {
    Write-Host "  [X] .env файл" -ForegroundColor Red
}

Write-Host "`nСЛЕДУЮЩИЕ ШАГИ:`n" -ForegroundColor Cyan

Write-Host "1. Проверить .env файл:" -ForegroundColor Yellow
Write-Host "   code D:\bybit_strategy_tester_v2\.env" -ForegroundColor White
Write-Host "   Изменить пароли и API ключи`n" -ForegroundColor Gray

Write-Host "2. Запустить Backend API:" -ForegroundColor Yellow
Write-Host "   cd D:\bybit_strategy_tester_v2\backend" -ForegroundColor White
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   uvicorn backend.main:app --reload`n" -ForegroundColor White

Write-Host "3. Запустить Frontend:" -ForegroundColor Yellow
Write-Host "   cd D:\bybit_strategy_tester_v2\frontend" -ForegroundColor White
Write-Host "   npm run dev`n" -ForegroundColor White

Write-Host "4. Начать разработку:" -ForegroundColor Yellow
Write-Host "   Открыть docs\IMPLEMENTATION_ROADMAP.md" -ForegroundColor White
Write-Host "   Следовать плану День 1`n" -ForegroundColor White

if (-not $postgresInstalled) {
    Write-Host "ВАЖНО: PostgreSQL не установлен!" -ForegroundColor Red
    Write-Host "Для полноценной работы установите:" -ForegroundColor Yellow
    Write-Host "  https://www.postgresql.org/download/windows/" -ForegroundColor White
    Write-Host "Затем перезапустите этот скрипт`n" -ForegroundColor White
}

Write-Host "===============================================================================" -ForegroundColor Green
Write-Host "  ГОТОВ К РАЗРАБОТКЕ!" -ForegroundColor Green
Write-Host "===============================================================================`n" -ForegroundColor Green

Set-Location $projectRoot
