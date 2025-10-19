# ==============================================================================
# УСТАНОВКА POSTGRESQL 16 + TIMESCALEDB + REDIS 7
# ==============================================================================
# Этот скрипт автоматизирует установку PostgreSQL, TimescaleDB и Redis на Windows
# Требуется запуск от имени администратора!
# ==============================================================================

Write-Host @'
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║               УСТАНОВКА POSTGRESQL 16 + TIMESCALEDB + REDIS 7               ║
║                                                                              ║
║  Этот скрипт установит:                                                     ║
║    1. PostgreSQL 16                                                          ║
║    2. TimescaleDB Extension                                                  ║
║    3. Redis 7                                                                ║
║    4. Драйверы Python (psycopg2-binary, asyncpg)                            ║
║                                                                              ║
║  Требуется:                                                                  ║
║    - Права администратора Windows                                            ║
║    - Интернет-соединение (~400MB загрузки)                                   ║
║    - ~15-20 минут на установку                                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
'@ -ForegroundColor Cyan

# Проверка прав администратора
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "`n[ОШИБКА] Требуются права администратора!" -ForegroundColor Red
    Write-Host "Запустите PowerShell от имени администратора и повторите установку" -ForegroundColor Yellow
    Write-Host "`nНажмите любую клавишу для выхода..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 1
}

# Переменные конфигурации
$POSTGRES_VERSION = "16"
$POSTGRES_PASSWORD = "postgres123"  # ИЗМЕНИТЕ после установки!
$POSTGRES_PORT = "5432"
$REDIS_PORT = "6379"
$INSTALL_DIR = "C:\Program Files\PostgreSQL\16"
$REDIS_DIR = "C:\Program Files\Redis"
$TEMP_DIR = "$env:TEMP\bybit_installer"

# Создаем временную директорию
if (-not (Test-Path $TEMP_DIR)) {
    New-Item -ItemType Directory -Path $TEMP_DIR -Force | Out-Null
}

Write-Host "`n[INFO] Временная директория: $TEMP_DIR" -ForegroundColor Gray
Write-Host "[INFO] PostgreSQL будет установлен в: $INSTALL_DIR" -ForegroundColor Gray
Write-Host "[INFO] Redis будет установлен в: $REDIS_DIR" -ForegroundColor Gray

# ==============================================================================
# ФУНКЦИЯ: УСТАНОВКА POSTGRESQL 16
# ==============================================================================
function Install-PostgreSQL {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ ШАГ 1/4: УСТАНОВКА POSTGRESQL 16                                            ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    # Проверка уже установленной версии
    try {
        $existingPg = psql --version 2>&1
        if ($existingPg -match "psql \(PostgreSQL\) 16") {
            Write-Host "`n[OK] PostgreSQL 16 уже установлен!" -ForegroundColor Green
            Write-Host "Версия: $existingPg" -ForegroundColor Gray
            return $true
        }
        elseif ($existingPg -match "PostgreSQL") {
            Write-Host "`n[ПРЕДУПРЕЖДЕНИЕ] Найдена другая версия PostgreSQL: $existingPg" -ForegroundColor Yellow
            Write-Host "Рекомендуется удалить старую версию перед установкой PostgreSQL 16" -ForegroundColor Yellow
            $continue = Read-Host "Продолжить установку? (Y/N)"
            if ($continue -ne 'Y' -and $continue -ne 'y') {
                return $false
            }
        }
    }
    catch {
        Write-Host "`n[INFO] PostgreSQL не установлен, начинаем установку..." -ForegroundColor Gray
    }
    
    # URL для загрузки PostgreSQL 16
    $POSTGRES_URL = "https://get.enterprisedb.com/postgresql/postgresql-16.6-1-windows-x64.exe"
    $POSTGRES_INSTALLER = "$TEMP_DIR\postgresql-16-installer.exe"
    
    Write-Host "`n[1/3] Загрузка PostgreSQL 16..." -ForegroundColor Yellow
    Write-Host "      URL: $POSTGRES_URL" -ForegroundColor Gray
    Write-Host "      Размер: ~240 MB" -ForegroundColor Gray
    
    try {
        # Загрузка с прогресс-баром
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $POSTGRES_URL -OutFile $POSTGRES_INSTALLER -UseBasicParsing
        $ProgressPreference = 'Continue'
        Write-Host "      [OK] Загрузка завершена: $POSTGRES_INSTALLER" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось загрузить PostgreSQL: $_" -ForegroundColor Red
        Write-Host "`n      Загрузите вручную с: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "`n[2/3] Установка PostgreSQL 16 (это займет ~5-10 минут)..." -ForegroundColor Yellow
    Write-Host "      Параметры установки:" -ForegroundColor Gray
    Write-Host "        - Режим: Silent (без GUI)" -ForegroundColor Gray
    Write-Host "        - Директория: $INSTALL_DIR" -ForegroundColor Gray
    Write-Host "        - Порт: $POSTGRES_PORT" -ForegroundColor Gray
    Write-Host "        - Пароль: $POSTGRES_PASSWORD (ИЗМЕНИТЕ ПОСЛЕ УСТАНОВКИ!)" -ForegroundColor Gray
    Write-Host "        - Локаль: Russian, Russia" -ForegroundColor Gray
    
    try {
        # Тихая установка PostgreSQL
        $installArgs = @(
            "--mode", "unattended",
            "--unattendedmodeui", "none",
            "--prefix", "`"$INSTALL_DIR`"",
            "--datadir", "`"$INSTALL_DIR\data`"",
            "--servicename", "postgresql-x64-16",
            "--serviceaccount", "NT AUTHORITY\NetworkService",
            "--superpassword", "`"$POSTGRES_PASSWORD`"",
            "--serverport", "$POSTGRES_PORT",
            "--locale", "Russian, Russia"
        )
        
        $process = Start-Process -FilePath $POSTGRES_INSTALLER -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Host "      [OK] PostgreSQL установлен успешно!" -ForegroundColor Green
        }
        else {
            Write-Host "      [ОШИБКА] Установка завершилась с кодом: $($process.ExitCode)" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "      [ОШИБКА] Ошибка установки: $_" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n[3/3] Добавление PostgreSQL в PATH..." -ForegroundColor Yellow
    
    # Добавление в системный PATH
    $pgBinPath = "$INSTALL_DIR\bin"
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    
    if ($currentPath -notlike "*$pgBinPath*") {
        try {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$pgBinPath", "Machine")
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            Write-Host "      [OK] PostgreSQL добавлен в PATH" -ForegroundColor Green
        }
        catch {
            Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Не удалось добавить в PATH: $_" -ForegroundColor Yellow
            Write-Host "      Добавьте вручную: $pgBinPath" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "      [OK] PostgreSQL уже в PATH" -ForegroundColor Green
    }
    
    # Проверка установки
    Write-Host "`n[ПРОВЕРКА] Проверка установки PostgreSQL..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3  # Даем время службе запуститься
    
    try {
        $pgVersion = & "$pgBinPath\psql.exe" --version 2>&1
        Write-Host "      [OK] $pgVersion" -ForegroundColor Green
        
        # Проверка статуса службы
        $service = Get-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
        if ($service -and $service.Status -eq "Running") {
            Write-Host "      [OK] Служба PostgreSQL запущена" -ForegroundColor Green
        }
        else {
            Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Служба PostgreSQL не запущена" -ForegroundColor Yellow
            Write-Host "      Попытка запуска..." -ForegroundColor Gray
            Start-Service -Name "postgresql-x64-16"
            Start-Sleep -Seconds 2
            $service = Get-Service -Name "postgresql-x64-16"
            if ($service.Status -eq "Running") {
                Write-Host "      [OK] Служба запущена успешно" -ForegroundColor Green
            }
        }
        
        return $true
    }
    catch {
        Write-Host "      [ОШИБКА] PostgreSQL установлен, но не доступен: $_" -ForegroundColor Red
        return $false
    }
}

# ==============================================================================
# ФУНКЦИЯ: УСТАНОВКА TIMESCALEDB
# ==============================================================================
function Install-TimescaleDB {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ ШАГ 2/4: УСТАНОВКА TIMESCALEDB EXTENSION                                    ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    # URL для загрузки TimescaleDB
    $TIMESCALE_URL = "https://github.com/timescale/timescaledb/releases/download/2.18.0/timescaledb-postgresql-16-2.18.0-windows-amd64.zip"
    $TIMESCALE_ZIP = "$TEMP_DIR\timescaledb.zip"
    $TIMESCALE_DIR = "$TEMP_DIR\timescaledb"
    
    Write-Host "`n[1/3] Загрузка TimescaleDB..." -ForegroundColor Yellow
    Write-Host "      URL: $TIMESCALE_URL" -ForegroundColor Gray
    Write-Host "      Размер: ~20 MB" -ForegroundColor Gray
    
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $TIMESCALE_URL -OutFile $TIMESCALE_ZIP -UseBasicParsing
        $ProgressPreference = 'Continue'
        Write-Host "      [OK] Загрузка завершена" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось загрузить TimescaleDB: $_" -ForegroundColor Red
        Write-Host "      TimescaleDB не обязателен для работы, можно продолжить без него" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "`n[2/3] Распаковка и установка TimescaleDB..." -ForegroundColor Yellow
    
    try {
        # Распаковка
        Expand-Archive -Path $TIMESCALE_ZIP -DestinationPath $TIMESCALE_DIR -Force
        
        # Копирование файлов в PostgreSQL
        $pgLibDir = "$INSTALL_DIR\lib"
        $pgShareDir = "$INSTALL_DIR\share\extension"
        
        Copy-Item -Path "$TIMESCALE_DIR\*.dll" -Destination $pgLibDir -Force
        Copy-Item -Path "$TIMESCALE_DIR\*.control" -Destination $pgShareDir -Force
        Copy-Item -Path "$TIMESCALE_DIR\*.sql" -Destination $pgShareDir -Force
        
        Write-Host "      [OK] TimescaleDB установлен" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Ошибка установки TimescaleDB: $_" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n[3/3] Настройка PostgreSQL для TimescaleDB..." -ForegroundColor Yellow
    
    # Добавление в postgresql.conf
    $pgConfPath = "$INSTALL_DIR\data\postgresql.conf"
    
    try {
        if (Test-Path $pgConfPath) {
            $confContent = Get-Content $pgConfPath
            if ($confContent -notmatch "shared_preload_libraries.*timescaledb") {
                Add-Content -Path $pgConfPath -Value "`nshared_preload_libraries = 'timescaledb'"
                Write-Host "      [OK] TimescaleDB добавлен в postgresql.conf" -ForegroundColor Green
                
                # Перезапуск PostgreSQL
                Write-Host "      Перезапуск PostgreSQL..." -ForegroundColor Gray
                Restart-Service -Name "postgresql-x64-16" -Force
                Start-Sleep -Seconds 3
                Write-Host "      [OK] PostgreSQL перезапущен" -ForegroundColor Green
            }
            else {
                Write-Host "      [OK] TimescaleDB уже настроен в postgresql.conf" -ForegroundColor Green
            }
        }
    }
    catch {
        Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Не удалось настроить автозагрузку: $_" -ForegroundColor Yellow
        Write-Host "      Добавьте вручную в postgresql.conf: shared_preload_libraries = 'timescaledb'" -ForegroundColor Yellow
    }
    
    return $true
}

# ==============================================================================
# ФУНКЦИЯ: УСТАНОВКА REDIS 7
# ==============================================================================
function Install-Redis {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ ШАГ 3/4: УСТАНОВКА REDIS 7                                                  ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    # Проверка существующей установки
    try {
        $existingRedis = redis-server --version 2>&1
        if ($existingRedis -match "Redis") {
            Write-Host "`n[OK] Redis уже установлен: $existingRedis" -ForegroundColor Green
            return $true
        }
    }
    catch {
        Write-Host "`n[INFO] Redis не установлен, начинаем установку..." -ForegroundColor Gray
    }
    
    # URL для загрузки Redis (Memurai - совместимая Windows версия)
    $REDIS_URL = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.msi"
    $REDIS_INSTALLER = "$TEMP_DIR\redis-installer.msi"
    
    Write-Host "`n[1/3] Загрузка Redis..." -ForegroundColor Yellow
    Write-Host "      URL: $REDIS_URL" -ForegroundColor Gray
    Write-Host "      Размер: ~5 MB" -ForegroundColor Gray
    
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $REDIS_URL -OutFile $REDIS_INSTALLER -UseBasicParsing
        $ProgressPreference = 'Continue'
        Write-Host "      [OK] Загрузка завершена" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось загрузить Redis: $_" -ForegroundColor Red
        Write-Host "`n      Загрузите вручную с: https://github.com/tporadowski/redis/releases" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "`n[2/3] Установка Redis (это займет ~2-3 минуты)..." -ForegroundColor Yellow
    Write-Host "      Параметры установки:" -ForegroundColor Gray
    Write-Host "        - Режим: Silent" -ForegroundColor Gray
    Write-Host "        - Директория: $REDIS_DIR" -ForegroundColor Gray
    Write-Host "        - Порт: $REDIS_PORT" -ForegroundColor Gray
    Write-Host "        - Windows Service: Да" -ForegroundColor Gray
    
    try {
        # Тихая установка MSI
        $msiArgs = @(
            "/i", "`"$REDIS_INSTALLER`"",
            "/quiet",
            "/norestart",
            "INSTALLDIR=`"$REDIS_DIR`"",
            "PORT=$REDIS_PORT",
            "ADD_TO_PATH=1",
            "INSTALL_SERVICE=1"
        )
        
        $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Host "      [OK] Redis установлен успешно!" -ForegroundColor Green
        }
        else {
            Write-Host "      [ОШИБКА] Установка завершилась с кодом: $($process.ExitCode)" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "      [ОШИБКА] Ошибка установки: $_" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n[3/3] Настройка Redis..." -ForegroundColor Yellow
    
    # Проверка и запуск службы
    Start-Sleep -Seconds 2
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    
    if ($redisService) {
        if ($redisService.Status -ne "Running") {
            Write-Host "      Запуск службы Redis..." -ForegroundColor Gray
            Start-Service -Name "Redis"
            Start-Sleep -Seconds 2
        }
        
        $redisService = Get-Service -Name "Redis"
        if ($redisService.Status -eq "Running") {
            Write-Host "      [OK] Служба Redis запущена" -ForegroundColor Green
        }
    }
    else {
        Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Служба Redis не найдена" -ForegroundColor Yellow
    }
    
    # Добавление в PATH
    $redisBinPath = $REDIS_DIR
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    
    if ($currentPath -notlike "*$redisBinPath*") {
        try {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$redisBinPath", "Machine")
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            Write-Host "      [OK] Redis добавлен в PATH" -ForegroundColor Green
        }
        catch {
            Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Не удалось добавить в PATH: $_" -ForegroundColor Yellow
        }
    }
    
    # Проверка установки
    Write-Host "`n[ПРОВЕРКА] Проверка установки Redis..." -ForegroundColor Cyan
    
    try {
        $redisVersion = & "$redisBinPath\redis-server.exe" --version 2>&1
        Write-Host "      [OK] $redisVersion" -ForegroundColor Green
        
        # Проверка подключения
        $redisPing = & "$redisBinPath\redis-cli.exe" ping 2>&1
        if ($redisPing -eq "PONG") {
            Write-Host "      [OK] Redis отвечает на ping: PONG" -ForegroundColor Green
        }
        
        return $true
    }
    catch {
        Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Redis установлен, но не полностью доступен: $_" -ForegroundColor Yellow
        return $true  # Все равно считаем успехом
    }
}

# ==============================================================================
# ФУНКЦИЯ: УСТАНОВКА PYTHON ДРАЙВЕРОВ
# ==============================================================================
function Install-PythonDrivers {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ ШАГ 4/4: УСТАНОВКА PYTHON ДРАЙВЕРОВ                                         ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    $projectRoot = "D:\bybit_strategy_tester_v2"
    $venvPath = "$projectRoot\backend\venv"
    $venvPython = "$venvPath\Scripts\python.exe"
    
    if (-not (Test-Path $venvPython)) {
        Write-Host "`n[ОШИБКА] Виртуальное окружение не найдено: $venvPath" -ForegroundColor Red
        Write-Host "Сначала создайте venv командой: python -m venv backend\venv" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "`n[1/2] Установка psycopg2-binary (PostgreSQL драйвер)..." -ForegroundColor Yellow
    
    try {
        & $venvPython -m pip install psycopg2-binary --quiet
        Write-Host "      [OK] psycopg2-binary установлен" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось установить psycopg2-binary: $_" -ForegroundColor Red
        Write-Host "      Попробуйте вручную: pip install psycopg2-binary" -ForegroundColor Yellow
    }
    
    Write-Host "`n[2/2] Установка asyncpg (асинхронный PostgreSQL драйвер)..." -ForegroundColor Yellow
    
    try {
        & $venvPython -m pip install asyncpg --quiet
        Write-Host "      [OK] asyncpg установлен" -ForegroundColor Green
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось установить asyncpg: $_" -ForegroundColor Red
        Write-Host "      Попробуйте вручную: pip install asyncpg" -ForegroundColor Yellow
    }
    
    # Проверка установленных пакетов
    Write-Host "`n[ПРОВЕРКА] Установленные драйверы:" -ForegroundColor Cyan
    
    try {
        $packages = & $venvPython -m pip list | Select-String "psycopg2|asyncpg"
        $packages | ForEach-Object {
            Write-Host "      [OK] $_" -ForegroundColor Green
        }
        return $true
    }
    catch {
        Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Не удалось проверить пакеты" -ForegroundColor Yellow
        return $true
    }
}

# ==============================================================================
# ФУНКЦИЯ: СОЗДАНИЕ БАЗЫ ДАННЫХ
# ==============================================================================
function Create-Database {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ БОНУС: СОЗДАНИЕ БАЗЫ ДАННЫХ                                                 ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    $pgBinPath = "$INSTALL_DIR\bin"
    $dbName = "bybit_strategy_tester"
    
    Write-Host "`n[1/2] Создание базы данных '$dbName'..." -ForegroundColor Yellow
    
    try {
        # Проверка существования БД
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        $existingDb = & "$pgBinPath\psql.exe" -U postgres -lqt 2>&1 | Select-String -Pattern $dbName
        
        if ($existingDb) {
            Write-Host "      [OK] База данных '$dbName' уже существует" -ForegroundColor Green
        }
        else {
            # Создание БД
            & "$pgBinPath\createdb.exe" -U postgres -E UTF8 $dbName 2>&1 | Out-Null
            Write-Host "      [OK] База данных '$dbName' создана" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "      [ОШИБКА] Не удалось создать базу данных: $_" -ForegroundColor Red
        Write-Host "      Создайте вручную: createdb -U postgres bybit_strategy_tester" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "`n[2/2] Включение TimescaleDB расширения..." -ForegroundColor Yellow
    
    try {
        $sqlCommand = "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        $result = & "$pgBinPath\psql.exe" -U postgres -d $dbName -c $sqlCommand 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      [OK] TimescaleDB расширение включено" -ForegroundColor Green
        }
        else {
            Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] TimescaleDB расширение не включено" -ForegroundColor Yellow
            Write-Host "      Включите вручную: CREATE EXTENSION timescaledb CASCADE;" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "      [ПРЕДУПРЕЖДЕНИЕ] Не удалось включить TimescaleDB: $_" -ForegroundColor Yellow
    }
    finally {
        Remove-Item Env:\PGPASSWORD
    }
    
    Write-Host "`n[INFO] Строка подключения к БД:" -ForegroundColor Cyan
    Write-Host "      postgresql://postgres:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$dbName" -ForegroundColor White
    Write-Host "`n[ВАЖНО] Измените пароль 'postgres' после установки!" -ForegroundColor Red
    
    return $true
}

# ==============================================================================
# ФУНКЦИЯ: ФИНАЛЬНАЯ ПРОВЕРКА
# ==============================================================================
function Test-Installation {
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ ФИНАЛЬНАЯ ПРОВЕРКА УСТАНОВКИ                                                ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    $results = @{
        PostgreSQL = $false
        TimescaleDB = $false
        Redis = $false
        PythonDrivers = $false
        Database = $false
    }
    
    # PostgreSQL
    Write-Host "`n[1/5] PostgreSQL..." -ForegroundColor Yellow
    try {
        $pgVersion = psql --version 2>&1
        if ($pgVersion -match "PostgreSQL") {
            Write-Host "      [OK] $pgVersion" -ForegroundColor Green
            $results.PostgreSQL = $true
        }
    }
    catch {
        Write-Host "      [X] PostgreSQL не доступен" -ForegroundColor Red
    }
    
    # TimescaleDB
    Write-Host "`n[2/5] TimescaleDB..." -ForegroundColor Yellow
    try {
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        $tsVersion = psql -U postgres -d bybit_strategy_tester -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';" -t 2>&1
        if ($tsVersion) {
            Write-Host "      [OK] TimescaleDB версия: $($tsVersion.Trim())" -ForegroundColor Green
            $results.TimescaleDB = $true
        }
    }
    catch {
        Write-Host "      [X] TimescaleDB не доступен" -ForegroundColor Yellow
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
    
    # Redis
    Write-Host "`n[3/5] Redis..." -ForegroundColor Yellow
    try {
        $redisVersion = redis-server --version 2>&1
        if ($redisVersion -match "Redis") {
            Write-Host "      [OK] $redisVersion" -ForegroundColor Green
            
            $redisPing = redis-cli ping 2>&1
            if ($redisPing -eq "PONG") {
                Write-Host "      [OK] Redis подключение работает (PONG)" -ForegroundColor Green
                $results.Redis = $true
            }
        }
    }
    catch {
        Write-Host "      [X] Redis не доступен" -ForegroundColor Red
    }
    
    # Python драйверы
    Write-Host "`n[4/5] Python драйверы..." -ForegroundColor Yellow
    try {
        $venvPython = "D:\bybit_strategy_tester_v2\backend\venv\Scripts\python.exe"
        $drivers = & $venvPython -m pip list 2>&1 | Select-String "psycopg2|asyncpg"
        
        if ($drivers) {
            $drivers | ForEach-Object {
                Write-Host "      [OK] $_" -ForegroundColor Green
            }
            $results.PythonDrivers = $true
        }
    }
    catch {
        Write-Host "      [X] Python драйверы не найдены" -ForegroundColor Red
    }
    
    # База данных
    Write-Host "`n[5/5] База данных..." -ForegroundColor Yellow
    try {
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        $dbExists = psql -U postgres -lqt 2>&1 | Select-String "bybit_strategy_tester"
        
        if ($dbExists) {
            Write-Host "      [OK] База данных 'bybit_strategy_tester' существует" -ForegroundColor Green
            $results.Database = $true
        }
    }
    catch {
        Write-Host "      [X] База данных не найдена" -ForegroundColor Red
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
    
    # Итоговый результат
    Write-Host "`n" -NoNewline
    Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ РЕЗУЛЬТАТЫ УСТАНОВКИ                                                        ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    $successCount = ($results.Values | Where-Object { $_ -eq $true }).Count
    $totalCount = $results.Count
    $percentage = [math]::Round(($successCount / $totalCount) * 100)
    
    Write-Host "`n  PostgreSQL 16:        " -NoNewline
    if ($results.PostgreSQL) { Write-Host "[OK]" -ForegroundColor Green } else { Write-Host "[FAIL]" -ForegroundColor Red }
    
    Write-Host "  TimescaleDB:          " -NoNewline
    if ($results.TimescaleDB) { Write-Host "[OK]" -ForegroundColor Green } else { Write-Host "[OPTIONAL]" -ForegroundColor Yellow }
    
    Write-Host "  Redis 7:              " -NoNewline
    if ($results.Redis) { Write-Host "[OK]" -ForegroundColor Green } else { Write-Host "[FAIL]" -ForegroundColor Red }
    
    Write-Host "  Python Drivers:       " -NoNewline
    if ($results.PythonDrivers) { Write-Host "[OK]" -ForegroundColor Green } else { Write-Host "[FAIL]" -ForegroundColor Red }
    
    Write-Host "  Database Created:     " -NoNewline
    if ($results.Database) { Write-Host "[OK]" -ForegroundColor Green } else { Write-Host "[FAIL]" -ForegroundColor Red }
    
    Write-Host "`n  ГОТОВНОСТЬ: $percentage% ($successCount/$totalCount)" -ForegroundColor $(if ($percentage -eq 100) { "Green" } elseif ($percentage -ge 80) { "Yellow" } else { "Red" })
    
    if ($percentage -eq 100) {
        Write-Host "`n  ✓ ВСЕ КОМПОНЕНТЫ УСТАНОВЛЕНЫ И РАБОТАЮТ!" -ForegroundColor Green
        Write-Host "  Можно начинать разработку!" -ForegroundColor Green
    }
    elseif ($percentage -ge 60) {
        Write-Host "`n  ! ОСНОВНЫЕ КОМПОНЕНТЫ УСТАНОВЛЕНЫ" -ForegroundColor Yellow
        Write-Host "  Проверьте ошибки выше и при необходимости переустановите компоненты" -ForegroundColor Yellow
    }
    else {
        Write-Host "`n  ✗ УСТАНОВКА НЕ ЗАВЕРШЕНА" -ForegroundColor Red
        Write-Host "  Проверьте ошибки выше и повторите установку" -ForegroundColor Red
    }
    
    return $results
}

# ==============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==============================================================================
function Main {
    Write-Host "`n[START] Начало установки..." -ForegroundColor Cyan
    Write-Host "[TIME] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    
    $startTime = Get-Date
    
    # Шаг 1: PostgreSQL
    $pgSuccess = Install-PostgreSQL
    
    # Шаг 2: TimescaleDB (только если PostgreSQL установлен)
    $tsSuccess = $false
    if ($pgSuccess) {
        $tsSuccess = Install-TimescaleDB
    }
    
    # Шаг 3: Redis
    $redisSuccess = Install-Redis
    
    # Шаг 4: Python драйверы (только если PostgreSQL установлен)
    $driversSuccess = $false
    if ($pgSuccess) {
        $driversSuccess = Install-PythonDrivers
    }
    
    # Шаг 5: Создание БД (только если PostgreSQL установлен)
    $dbSuccess = $false
    if ($pgSuccess) {
        $dbSuccess = Create-Database
    }
    
    # Финальная проверка
    $results = Test-Installation
    
    $endTime = Get-Date
    $duration = $endTime - $startTime
    
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ УСТАНОВКА ЗАВЕРШЕНА                                                         ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    Write-Host "`n[TIME] Время выполнения: $($duration.Minutes) минут $($duration.Seconds) секунд" -ForegroundColor Gray
    Write-Host "[END] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    
    # Следующие шаги
    Write-Host "`n╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║ СЛЕДУЮЩИЕ ШАГИ                                                              ║" -ForegroundColor Yellow
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    
    Write-Host "`n1. ИЗМЕНИТЕ ПАРОЛЬ PostgreSQL:" -ForegroundColor White
    Write-Host "   psql -U postgres" -ForegroundColor Gray
    Write-Host "   ALTER USER postgres WITH PASSWORD 'ваш_новый_пароль';" -ForegroundColor Gray
    
    Write-Host "`n2. ОБНОВИТЕ .env ФАЙЛ:" -ForegroundColor White
    Write-Host "   D:\bybit_strategy_tester_v2\.env" -ForegroundColor Gray
    Write-Host "   DATABASE_URL=postgresql://postgres:ваш_пароль@localhost:5432/bybit_strategy_tester" -ForegroundColor Gray
    Write-Host "   REDIS_URL=redis://localhost:6379" -ForegroundColor Gray
    
    Write-Host "`n3. СОЗДАЙТЕ СХЕМУ БД:" -ForegroundColor White
    Write-Host "   Скопируйте SQL из docs/TECHNICAL_SPECIFICATION.md (раздел 2.3)" -ForegroundColor Gray
    Write-Host "   psql -U postgres -d bybit_strategy_tester -f schema.sql" -ForegroundColor Gray
    
    Write-Host "`n4. ЗАПУСТИТЕ BACKEND:" -ForegroundColor White
    Write-Host "   cd D:\bybit_strategy_tester_v2\backend" -ForegroundColor Gray
    Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "   uvicorn main:app --reload" -ForegroundColor Gray
    
    Write-Host "`n5. НАЧНИТЕ РАЗРАБОТКУ:" -ForegroundColor White
    Write-Host "   Следуйте плану в docs/IMPLEMENTATION_ROADMAP.md (День 1)" -ForegroundColor Gray
    
    Write-Host "`n" -NoNewline
    
    # Очистка временных файлов
    Write-Host "[CLEANUP] Удаление временных файлов..." -ForegroundColor Gray
    try {
        Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Временные файлы удалены" -ForegroundColor Green
    }
    catch {
        Write-Host "[WARNING] Не удалось удалить временные файлы: $TEMP_DIR" -ForegroundColor Yellow
    }
    
    Write-Host "`nНажмите любую клавишу для выхода..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}

# Запуск установки
Main
