#!/usr/bin/env pwsh
# BYBIT STRATEGY TESTER v2 - ONE-CLICK STARTER WITH STATUS REPORT

param(
    [switch]$SQLiteFallback,
    [int]$DbPort = 5433,
    [string]$DbName = 'bybit',
    [string]$DbUser = 'postgres',
    [string]$DbPass = 'postgres',
    [ValidateSet('auto', 'host', 'container')]
    [string]$MigrationMode = 'container',
    [string]$MigratorImage = '',
    [string]$MigratorPython = '3.12-slim',
    [switch]$BuildMigrator,
    [string]$ApiHost = '127.0.0.1',
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoBrowser,
    [switch]$UseMockBacktests,
    [string]$MockBtDir = 'd:\PERP'
)

# Force UTF-8 output to avoid mojibake for Cyrillic text in legacy consoles
try {
    chcp 65001 | Out-Null
}
catch {}
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
}
catch {}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "BYBIT STRATEGY TESTER v2" -ForegroundColor Cyan
Write-Host "ONE-CLICK START" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Load optional configuration: .env (overrides defaults) and migrator.config.json (fallback defaults)
function ConvertTo-Bool($val) {
    if ($null -eq $val) { return $false }
    $s = "$val".Trim().ToLowerInvariant()
    return @('1', 'true', 'yes', 'on').Contains($s)
}

# Parse .env if present
$dotenv = @{}
$dotenvPath = Join-Path $PSScriptRoot '.env'
if (Test-Path $dotenvPath) {
    try {
        Get-Content -Path $dotenvPath -ErrorAction Stop | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith('#')) { return }
            $idx = $line.IndexOf('=')
            if ($idx -gt 0) {
                $k = $line.Substring(0, $idx).Trim()
                $v = $line.Substring($idx + 1).Trim()
                # Strip surrounding quotes
                if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                    $v = $v.Substring(1, $v.Length - 2)
                }
                $dotenv[$k] = $v
            }
        }
        Write-Host "    Loaded .env overrides" -ForegroundColor DarkGray
    }
    catch { Write-Host "    WARNING: Failed to parse .env: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# Load migrator config json (fallback defaults for migrator-related settings)
$migrCfg = $null
$migrCfgPath = Join-Path $PSScriptRoot 'scripts\migrator.config.json'
if (Test-Path $migrCfgPath) {
    try { $migrCfg = Get-Content $migrCfgPath -Raw | ConvertFrom-Json } catch { Write-Host "    WARNING: Failed to parse migrator.config.json: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# Apply precedence: CLI ($PSBoundParameters) > .env > config > default
if (-not $PSBoundParameters.ContainsKey('DbPort') -and $dotenv.ContainsKey('DB_PORT')) { [int]$DbPort = $dotenv['DB_PORT'] }
if (-not $PSBoundParameters.ContainsKey('DbName') -and $dotenv.ContainsKey('DB_NAME')) { $DbName = $dotenv['DB_NAME'] }
if (-not $PSBoundParameters.ContainsKey('DbUser') -and $dotenv.ContainsKey('DB_USER')) { $DbUser = $dotenv['DB_USER'] }
if (-not $PSBoundParameters.ContainsKey('DbPass') -and $dotenv.ContainsKey('DB_PASS')) { $DbPass = $dotenv['DB_PASS'] }

if (-not $PSBoundParameters.ContainsKey('MigrationMode')) {
    if ($dotenv.ContainsKey('MIGRATION_MODE')) { $MigrationMode = $dotenv['MIGRATION_MODE'] }
    elseif ($migrCfg -and $migrCfg.DefaultMigrationMode) { $MigrationMode = "$($migrCfg.DefaultMigrationMode)" }
}
if (-not $PSBoundParameters.ContainsKey('MigratorImage')) {
    if ($dotenv.ContainsKey('MIGRATOR_IMAGE')) { $MigratorImage = $dotenv['MIGRATOR_IMAGE'] }
    elseif ($migrCfg -and $migrCfg.MigratorImage) { $MigratorImage = "$($migrCfg.MigratorImage)" }
}
if (-not $PSBoundParameters.ContainsKey('MigratorPython')) {
    if ($dotenv.ContainsKey('MIGRATOR_PYTHON')) { $MigratorPython = $dotenv['MIGRATOR_PYTHON'] }
    elseif ($migrCfg -and $migrCfg.MigratorPython) { $MigratorPython = "$($migrCfg.MigratorPython)" }
}
if (-not $PSBoundParameters.ContainsKey('BuildMigrator')) {
    if ($dotenv.ContainsKey('BUILD_MIGRATOR')) { if (ConvertTo-Bool $dotenv['BUILD_MIGRATOR']) { $BuildMigrator = $true } }
    elseif ($migrCfg -and $migrCfg.BuildMigrator) { if ([bool]$migrCfg.BuildMigrator) { $BuildMigrator = $true } }
}

if (-not $PSBoundParameters.ContainsKey('ApiHost') -and $dotenv.ContainsKey('API_HOST')) { $ApiHost = $dotenv['API_HOST'] }
if (-not $PSBoundParameters.ContainsKey('ApiPort') -and $dotenv.ContainsKey('API_PORT')) { [int]$ApiPort = $dotenv['API_PORT'] }
if (-not $PSBoundParameters.ContainsKey('FrontendPort') -and $dotenv.ContainsKey('FRONTEND_PORT')) { [int]$FrontendPort = $dotenv['FRONTEND_PORT'] }
if (-not $PSBoundParameters.ContainsKey('NoBrowser') -and $dotenv.ContainsKey('NO_BROWSER')) { if (ConvertTo-Bool $dotenv['NO_BROWSER']) { $NoBrowser = $true } }
if (-not $PSBoundParameters.ContainsKey('SQLiteFallback') -and $dotenv.ContainsKey('SQLITE_FALLBACK')) { if (ConvertTo-Bool $dotenv['SQLITE_FALLBACK']) { $SQLiteFallback = $true } }
if (-not $PSBoundParameters.ContainsKey('UseMockBacktests') -and $dotenv.ContainsKey('USE_MOCK_BACKTESTS')) { if (ConvertTo-Bool $dotenv['USE_MOCK_BACKTESTS']) { $UseMockBacktests = $true } }
if (-not $PSBoundParameters.ContainsKey('MockBtDir') -and $dotenv.ContainsKey('MOCK_BT_DIR')) { $MockBtDir = $dotenv['MOCK_BT_DIR'] }

# If DATABASE_URL is specified in .env, set it now so our later logic respects it
if ($dotenv.ContainsKey('DATABASE_URL')) { $env:DATABASE_URL = $dotenv['DATABASE_URL'] }

# [1] Check Python
Write-Host "[1] Checking Python..." -ForegroundColor Yellow
# Prefer venv Python if available
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $pythonExe = $venvPy
}
else {
    $pythonExe = "python"
}

$pythonVersion = & $pythonExe --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "    $pythonVersion`n" -ForegroundColor Green
}
else {
    Write-Host "    ERROR: Python not found!`n" -ForegroundColor Red
    exit 1
}

# [2] Check Node.js
Write-Host "[2] Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version
if ($LASTEXITCODE -eq 0) {
    Write-Host "    $nodeVersion`n" -ForegroundColor Green
}
else {
    Write-Host "    ERROR: Node.js not found!`n" -ForegroundColor Red
    exit 1
}

# [3] Ensure logs directory
Write-Host "[3] Preparing logs directory..." -ForegroundColor Yellow
$logsDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
Write-Host "    $logsDir" -ForegroundColor Green
if (Test-Path $dotenvPath) { Write-Host "    Using .env from $dotenvPath" -ForegroundColor DarkGray }
if (Test-Path $migrCfgPath) { Write-Host "    Using migrator defaults from $migrCfgPath" -ForegroundColor DarkGray }
Write-Host "" 

# [4] Start Postgres and run migrations (docker-compose)
Write-Host "[4] Starting Postgres (+migrations)..." -ForegroundColor Yellow
try {
    # Use robust container-mode migrations by default on Windows; can be overridden via parameters
    $securePass = ConvertTo-SecureString $DbPass -AsPlainText -Force
    $dbCred = New-Object System.Management.Automation.PSCredential($DbUser, $securePass)
    & (Join-Path $PSScriptRoot 'scripts/start_postgres_and_migrate.ps1') `
        -Port $DbPort `
        -Db $DbName `
        -Credential $dbCred `
        -MigrationMode $MigrationMode `
        -MigratorImage $MigratorImage `
        -MigratorPython $MigratorPython `
        -BuildMigrator:$BuildMigrator | Write-Output
    Write-Host "    Postgres ready on 127.0.0.1:$DbPort`n" -ForegroundColor Green
}
catch {
    Write-Host "    ERROR starting Postgres: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# [5] Env vars for backend
Write-Host "[5] Preparing environment..." -ForegroundColor Yellow
$env:PYTHONPATH = $PSScriptRoot
if ($SQLiteFallback) {
    $env:DATABASE_URL = "sqlite:///:memory:"
}
elseif (-not $env:DATABASE_URL) {
    # Default to local Postgres dev container
    $env:DATABASE_URL = "postgresql://${DbUser}:${DbPass}@127.0.0.1:${DbPort}/${DbName}"
}
# Avoid DB writes for Bybit klines on dev startup unless explicitly enabled
if (-not $env:BYBIT_PERSIST_KLINES) {
    $env:BYBIT_PERSIST_KLINES = "0"
}
Write-Host "    PYTHONPATH=$($env:PYTHONPATH)" -ForegroundColor DarkGray
Write-Host "    DATABASE_URL=$($env:DATABASE_URL)" -ForegroundColor DarkGray
Write-Host "    BYBIT_PERSIST_KLINES=$($env:BYBIT_PERSIST_KLINES)" -ForegroundColor DarkGray

# Enable Bybit WS manager (optional live feed to Redis)
if (-not $env:BYBIT_WS_ENABLED) { $env:BYBIT_WS_ENABLED = "1" }
if (-not $env:BYBIT_WS_SYMBOLS) { $env:BYBIT_WS_SYMBOLS = "BTCUSDT,ETHUSDT" }
if (-not $env:BYBIT_WS_INTERVALS) { $env:BYBIT_WS_INTERVALS = "1,5" }
Write-Host "    BYBIT_WS_ENABLED=$($env:BYBIT_WS_ENABLED)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_SYMBOLS=$($env:BYBIT_WS_SYMBOLS)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_INTERVALS=$($env:BYBIT_WS_INTERVALS)" -ForegroundColor DarkGray

# Enable mock backtests if requested
if ($UseMockBacktests) {
    $env:USE_MOCK_BACKTESTS = '1'
    if ($MockBtDir) { $env:MOCK_BT_DIR = $MockBtDir }
    Write-Host "    USE_MOCK_BACKTESTS=1 (MOCK_BT_DIR=$($env:MOCK_BT_DIR))" -ForegroundColor DarkGray
}

# [6] Start Backend via helper (PID/logs managed)
Write-Host "[6] Starting Backend..." -ForegroundColor Yellow
$uvicornScript = Join-Path $PSScriptRoot 'scripts/start_uvicorn.ps1'
$dbUrlMasked = ($env:DATABASE_URL -replace '://([^:]+):([^@]+)@', '://$1:****@')
Write-Host "    DATABASE_URL=$dbUrlMasked" -ForegroundColor DarkGray
& $uvicornScript start -AppModule 'backend.api.app:app' -BindHost $ApiHost -Port $ApiPort -DatabaseUrl $env:DATABASE_URL | Write-Output
$pidFile = Join-Path $PSScriptRoot '.uvicorn.pid'
$backendPid = $null
if (Test-Path $pidFile) { $backendPid = Get-Content $pidFile }
if ($backendPid) { Write-Host "    Backend PID: $backendPid`n" -ForegroundColor Green } else { Write-Host "    WARNING: Backend PID not found`n" -ForegroundColor Yellow }
Start-Sleep -Seconds 3

# Quick external connectivity probe to Bybit via backend endpoint (with retries)
for ($i = 1; $i -le 3; $i++) {
    try {
        $probe = Invoke-RestMethod -Uri "http://${ApiHost}:${ApiPort}/api/v1/exchangez" -TimeoutSec 6 -ErrorAction Stop
        if ($probe.status -eq 'ok') {
            Write-Host "    Exchange probe: Bybit reachable (latency $($probe.latency_ms) ms)" -ForegroundColor Green
            break
        }
        else {
            Write-Host "    Exchange probe: DOWN ($($probe | ConvertTo-Json -Compress))" -ForegroundColor Yellow
        }
    }
    catch {
        if ($i -lt 3) {
            Write-Host "    Exchange probe attempt $i/3 failed: $($_.Exception.Message) - retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        }
        else {
            Write-Host "    Exchange probe failed after 3 attempts: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# [7] Start Frontend (Vite) in background with logs
Write-Host "[7] Starting Frontend..." -ForegroundColor Yellow
$cmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
$npmExe = if ($cmd) { $cmd.Source } else { 'npm.cmd' }
$feOut = Join-Path $logsDir 'frontend.out.log'
$feErr = Join-Path $logsDir 'frontend.err.log'
$frontendArgs = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$FrontendPort")
$frontend = Start-Process -FilePath $npmExe -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $PSScriptRoot 'frontend') -RedirectStandardOutput $feOut -RedirectStandardError $feErr -PassThru
($frontend.Id) | Out-File -FilePath (Join-Path $PSScriptRoot '.vite.pid') -Encoding ascii
Write-Host "    Frontend PID: $($frontend.Id) (logs: $feOut)" -ForegroundColor Green
Start-Sleep -Seconds 2

# [8] Health & Status report
Write-Host "[8] Status report:" -ForegroundColor Yellow
try {
    $h = Invoke-RestMethod -Uri "http://${ApiHost}:${ApiPort}/api/v1/healthz" -TimeoutSec 4 -ErrorAction Stop
    Write-Host "    API Health: $($h.status)" -ForegroundColor Green
}
catch { Write-Host "    API Health: ERROR $($_.Exception.Message)" -ForegroundColor Red }
try {
    $x = Invoke-RestMethod -Uri "http://${ApiHost}:${ApiPort}/api/v1/exchangez" -TimeoutSec 6 -ErrorAction Stop
    $lat = ('{0:N1}' -f ($x.latency_ms))
    Write-Host "    Exchange: $($x.status) (latency ${lat} ms)" -ForegroundColor Green
}
catch { Write-Host "    Exchange: ERROR $($_.Exception.Message)" -ForegroundColor Red }
try {
    $rootResp = Invoke-WebRequest -Uri "http://localhost:${FrontendPort}/" -TimeoutSec 6 -ErrorAction Stop
    Write-Host "    Frontend: OK (HTTP $($rootResp.StatusCode))" -ForegroundColor Green
}
catch { Write-Host "    Frontend: starting (check logs) - $($_.Exception.Message)" -ForegroundColor Yellow }

if (-not $NoBrowser) {
    Write-Host "[9] Opening browser..." -ForegroundColor Yellow
    $defaultPath = "/#/"
    if ($UseMockBacktests) { $defaultPath = "/#/backtests" }
    $url = "http://localhost:${FrontendPort}$defaultPath"
    Start-Process $url
    Write-Host "    Browser opening to $defaultPath...`n" -ForegroundColor Green
}

# Success message
Write-Host "========================================" -ForegroundColor Green
Write-Host "ALL SERVERS STARTED" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host ("Backend:  http://{0}:{1}" -f $ApiHost, $ApiPort) -ForegroundColor Cyan
Write-Host ("Frontend: http://localhost:{0}" -f $FrontendPort) -ForegroundColor Cyan
if ($backendPid) { Write-Host ("Backend PID: {0}" -f $backendPid) -ForegroundColor DarkGray }
Write-Host ("Frontend PID: {0}" -f $frontend.Id) -ForegroundColor DarkGray
Write-Host "`nOpen in browser:" -ForegroundColor Yellow
Write-Host ("  http://localhost:{0}/#/" -f $FrontendPort) -ForegroundColor Magenta
Write-Host "`nHome opens the Bots mock dashboard (start page of the mock)`n" -ForegroundColor Green
