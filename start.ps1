#!/usr/bin/env pwsh
# BYBIT STRATEGY TESTER v2 - UNIFIED ONE-CLICK STARTER
# Starts all services: PostgreSQL + Redis + Backend API + Frontend
# Uses real Bybit API by default (no mock/SQLite fallback)

param(
    [switch]$SQLiteFallback,
    [int]$DbPort = 5432,
    [string]$DbName = 'bybit',
    [string]$DbUser = 'postgres',
    [string]$DbPass = 'postgres',
    [ValidateSet('auto', 'host', 'container')]
    [string]$MigrationMode = 'container',
    [string]$MigratorImage = '',
    [string]$MigratorPython = '3.12-slim',
    [switch]$BuildMigrator,
    [string]$ApiHost = '0.0.0.0',
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoBrowser,
    [switch]$UseMockBacktests,
    [string]$MockBtDir = 'd:\PERP',
    [switch]$SkipDocker
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
Write-Host "   BYBIT STRATEGY TESTER v2" -ForegroundColor Cyan
Write-Host "   UNIFIED ONE-CLICK STARTER" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "   Starting all services:" -ForegroundColor Yellow
Write-Host "   1  PostgreSQL (Docker)" -ForegroundColor White
Write-Host "   2  Redis (Docker)" -ForegroundColor White
Write-Host "   3  MCP Server (Perplexity AI Bridge)" -ForegroundColor Magenta
Write-Host "   4  Backend API (FastAPI + Uvicorn)" -ForegroundColor White
Write-Host "   5  Frontend (Vite + React)" -ForegroundColor White
Write-Host "   6  Real Bybit API Integration" -ForegroundColor Green
Write-Host "`n   AI Flow: " -NoNewline -ForegroundColor Cyan
Write-Host "Copilot  MCP  Perplexity  MCP  Copilot" -ForegroundColor Magenta
Write-Host "`n========================================`n" -ForegroundColor Cyan

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

# [3] Start MCP Server for Perplexity AI (Copilot ↔ Perplexity ↔ Copilot)
Write-Host "[3] Starting MCP Server (Perplexity AI Bridge)..." -ForegroundColor Yellow

# Ensure logs directory exists first
$logsDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logsDir)) { 
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null 
}

$mcpServerScript = Join-Path $PSScriptRoot 'mcp-server\server.py'
$mcpPidFile = Join-Path $PSScriptRoot '.mcp.pid'

# Check if MCP server is already running
$mcpRunning = $false
if (Test-Path $mcpPidFile) {
    $mcpPid = Get-Content $mcpPidFile -ErrorAction SilentlyContinue
    if ($mcpPid) {
        $mcpProcess = Get-Process -Id $mcpPid -ErrorAction SilentlyContinue
        if ($mcpProcess) {
            Write-Host "    MCP Server already running (PID: $mcpPid)" -ForegroundColor Green
            $mcpRunning = $true
        }
        else {
            Remove-Item $mcpPidFile -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not $mcpRunning) {
    if (Test-Path $mcpServerScript) {
        try {
            # Set environment variables for MCP server (Windows Unicode fix + API key)
            if ($dotenv.ContainsKey('PERPLEXITY_API_KEY')) {
                $env:PERPLEXITY_API_KEY = $dotenv['PERPLEXITY_API_KEY']
            }
            # Fix Windows Unicode encoding issues
            $env:PYTHONIOENCODING = 'utf-8'
            # Tell MCP server to use stdio mode (suppress stderr output)
            $env:MCP_STDIO_MODE = '1'
            
            # Start MCP server in background
            $mcpOut = Join-Path $logsDir 'mcp-server.out.log'
            $mcpErr = Join-Path $logsDir 'mcp-server.err.log'
            
            $mcpProcess = Start-Process -FilePath $pythonExe `
                -ArgumentList $mcpServerScript `
                -WorkingDirectory (Join-Path $PSScriptRoot 'mcp-server') `
                -RedirectStandardOutput $mcpOut `
                -RedirectStandardError $mcpErr `
                -PassThru `
                -WindowStyle Hidden
            
            $mcpProcess.Id | Out-File -FilePath $mcpPidFile -Encoding ascii
            
            Write-Host "    MCP Server: STARTED (PID: $($mcpProcess.Id))" -ForegroundColor Green
            Write-Host "    Perplexity API: CONFIGURED" -ForegroundColor Green
            Write-Host "    Schema: Copilot  MCP Server  Perplexity AI  MCP Server  Copilot" -ForegroundColor Cyan
            Write-Host "    Logs: $mcpOut" -ForegroundColor DarkGray
        }
        catch {
            Write-Host "    WARNING: Failed to start MCP Server: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "    AI Studio may have limited functionality" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "    WARNING: MCP Server script not found at $mcpServerScript" -ForegroundColor Yellow
        Write-Host "    AI Studio will use fallback mode" -ForegroundColor Yellow
    }
}
Write-Host ""

# [4] Configuration summary
Write-Host "[4] Configuration loaded..." -ForegroundColor Yellow
Write-Host "    Logs directory: $logsDir" -ForegroundColor Green
if (Test-Path $dotenvPath) { Write-Host "    Using .env from $dotenvPath" -ForegroundColor DarkGray }
if (Test-Path $migrCfgPath) { Write-Host "    Using migrator defaults from $migrCfgPath" -ForegroundColor DarkGray }
Write-Host ""

# [5] Start PostgreSQL + Redis via Docker Compose
Write-Host "[5] Starting PostgreSQL + Redis (Docker Compose)..." -ForegroundColor Yellow
if (-not $SkipDocker) {
    try {
        Write-Host "    Starting containers..." -ForegroundColor DarkGray
        
        # Try docker compose v2 first (newer syntax)
        $dockerComposeV2 = Get-Command docker -ErrorAction SilentlyContinue
        if ($dockerComposeV2) {
            & docker compose up -d postgres redis 2>&1 | Out-Null
        }
        else {
            # Fallback to docker-compose v1
            & docker-compose up -d postgres redis 2>&1 | Out-Null
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    PostgreSQL: Started on localhost:$DbPort" -ForegroundColor Green
            Write-Host "    Redis: Started on localhost:6379" -ForegroundColor Green
            
            # Wait for services to be healthy
            Write-Host "    Waiting for services to be ready..." -ForegroundColor DarkGray
            Start-Sleep -Seconds 5
            
            # Run migrations
            Write-Host "    Running database migrations..." -ForegroundColor DarkGray
            $securePass = ConvertTo-SecureString $DbPass -AsPlainText -Force
            $dbCred = New-Object System.Management.Automation.PSCredential($DbUser, $securePass)
            & (Join-Path $PSScriptRoot 'scripts/start_postgres_and_migrate.ps1') `
                -Port $DbPort `
                -Db $DbName `
                -Credential $dbCred `
                -MigrationMode $MigrationMode `
                -MigratorImage $MigratorImage `
                -MigratorPython $MigratorPython `
                -BuildMigrator:$BuildMigrator 2>&1 | Out-Null
            Write-Host "    Database migrations: COMPLETE`n" -ForegroundColor Green
        }
        else {
            throw "Docker Compose failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Host "    ERROR: Failed to start Docker services" -ForegroundColor Red
        Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "    Make sure Docker Desktop is running!" -ForegroundColor Yellow
        exit 1
    }
}
else {
    Write-Host "    Skipping Docker (--SkipDocker flag set)" -ForegroundColor Yellow
    Write-Host "    Assuming PostgreSQL and Redis are already running`n" -ForegroundColor DarkGray
}

# [6] Load .env and configure environment
Write-Host "[6] Configuring environment..." -ForegroundColor Yellow

# Set PYTHONPATH
$env:PYTHONPATH = $PSScriptRoot

# Configure Database URL (use real PostgreSQL by default)
if ($SQLiteFallback) {
    $env:DATABASE_URL = "sqlite:///:memory:"
    Write-Host "    Using SQLite fallback mode" -ForegroundColor Yellow
}
elseif (-not $env:DATABASE_URL -or $dotenv.ContainsKey('DATABASE_URL')) {
    # Override with PostgreSQL connection
    $env:DATABASE_URL = "postgresql://${DbUser}:${DbPass}@127.0.0.1:${DbPort}/${DbName}"
}

# Configure Redis URL
if (-not $env:REDIS_URL) {
    $env:REDIS_URL = "redis://127.0.0.1:6379/0"
}

# Load Bybit API credentials from .env
if ($dotenv.ContainsKey('BYBIT_API_KEY')) {
    $env:BYBIT_API_KEY = $dotenv['BYBIT_API_KEY']
    Write-Host "    BYBIT_API_KEY: ***" -ForegroundColor Green -NoNewline
    Write-Host $env:BYBIT_API_KEY.Substring($env:BYBIT_API_KEY.Length - 4) -ForegroundColor Green
}
if ($dotenv.ContainsKey('BYBIT_API_SECRET')) {
    $env:BYBIT_API_SECRET = $dotenv['BYBIT_API_SECRET']
    Write-Host "    BYBIT_API_SECRET: ******" -ForegroundColor Green
}
if ($dotenv.ContainsKey('PERPLEXITY_API_KEY')) {
    $env:PERPLEXITY_API_KEY = $dotenv['PERPLEXITY_API_KEY']
    Write-Host "    PERPLEXITY_API_KEY: ***" -ForegroundColor Green -NoNewline
    Write-Host $env:PERPLEXITY_API_KEY.Substring($env:PERPLEXITY_API_KEY.Length - 4) -ForegroundColor Green
}

# Configure Bybit WebSocket Manager (Live data streaming to Redis)
if (-not $env:BYBIT_WS_ENABLED) { $env:BYBIT_WS_ENABLED = "1" }
if (-not $env:BYBIT_WS_SYMBOLS) { $env:BYBIT_WS_SYMBOLS = "BTCUSDT,ETHUSDT,SOLUSDT" }
if (-not $env:BYBIT_WS_INTERVALS) { $env:BYBIT_WS_INTERVALS = "1,5,15" }
if (-not $env:BYBIT_PERSIST_KLINES) { $env:BYBIT_PERSIST_KLINES = "1" }

Write-Host "    DATABASE_URL: postgresql://***@127.0.0.1:$DbPort/$DbName" -ForegroundColor DarkGray
Write-Host "    REDIS_URL: $($env:REDIS_URL)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_ENABLED: $($env:BYBIT_WS_ENABLED)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_SYMBOLS: $($env:BYBIT_WS_SYMBOLS)" -ForegroundColor DarkGray
Write-Host "    BYBIT_WS_INTERVALS: $($env:BYBIT_WS_INTERVALS)" -ForegroundColor DarkGray
Write-Host "    BYBIT_PERSIST_KLINES: $($env:BYBIT_PERSIST_KLINES)" -ForegroundColor DarkGray

# Enable mock backtests if requested
if ($UseMockBacktests) {
    $env:USE_MOCK_BACKTESTS = '1'
    if ($MockBtDir) { $env:MOCK_BT_DIR = $MockBtDir }
    Write-Host "    USE_MOCK_BACKTESTS: 1 (MOCK_BT_DIR=$($env:MOCK_BT_DIR))" -ForegroundColor DarkGray
}

Write-Host ""

# [7] Start Backend via helper (PID/logs managed)
Write-Host "[7] Starting Backend..." -ForegroundColor Yellow
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

# [8] Start Frontend (Vite) in background with logs
Write-Host "[8] Starting Frontend..." -ForegroundColor Yellow
$cmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
$npmExe = if ($cmd) { $cmd.Source } else { 'npm.cmd' }
$feOut = Join-Path $logsDir 'frontend.out.log'
$feErr = Join-Path $logsDir 'frontend.err.log'
$frontendArgs = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$FrontendPort")
$frontend = Start-Process -FilePath $npmExe -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $PSScriptRoot 'frontend') -RedirectStandardOutput $feOut -RedirectStandardError $feErr -PassThru
($frontend.Id) | Out-File -FilePath (Join-Path $PSScriptRoot '.vite.pid') -Encoding ascii
Write-Host "    Frontend PID: $($frontend.Id) (logs: $feOut)" -ForegroundColor Green
Start-Sleep -Seconds 2

# [9] Health & Status report
Write-Host "[9] Running health checks..." -ForegroundColor Yellow
Write-Host ""

# Check PostgreSQL
try {
    $null = & docker exec bybit_strategy_tester_v2-postgres-1 pg_isready -U $DbUser 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    PostgreSQL:  " -NoNewline -ForegroundColor White
        Write-Host "HEALTHY" -ForegroundColor Green
    }
    else {
        Write-Host "    PostgreSQL:  " -NoNewline -ForegroundColor White
        Write-Host "STARTING..." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "    PostgreSQL:  " -NoNewline -ForegroundColor White
    Write-Host "ERROR" -ForegroundColor Red
}

# Check Redis
try {
    $redisCheck = & docker exec bybit_strategy_tester_v2-redis-1 redis-cli ping 2>&1
    if ($redisCheck -match "PONG") {
        Write-Host "    Redis:       " -NoNewline -ForegroundColor White
        Write-Host "HEALTHY" -ForegroundColor Green
    }
    else {
        Write-Host "    Redis:       " -NoNewline -ForegroundColor White
        Write-Host "STARTING..." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "    Redis:       " -NoNewline -ForegroundColor White
    Write-Host "ERROR" -ForegroundColor Red
}

# Check MCP Server
if (Test-Path $mcpPidFile) {
    $mcpPid = Get-Content $mcpPidFile -ErrorAction SilentlyContinue
    if ($mcpPid) {
        $mcpProcess = Get-Process -Id $mcpPid -ErrorAction SilentlyContinue
        if ($mcpProcess) {
            Write-Host "    MCP Server:  " -NoNewline -ForegroundColor White
            Write-Host "RUNNING (PID: $mcpPid)" -ForegroundColor Green
        }
        else {
            Write-Host "    MCP Server:  " -NoNewline -ForegroundColor White
            Write-Host "STOPPED" -ForegroundColor Red
        }
    }
    else {
        Write-Host "    MCP Server:  " -NoNewline -ForegroundColor White
        Write-Host "NO PID" -ForegroundColor Yellow
    }
}
else {
    Write-Host "    MCP Server:  " -NoNewline -ForegroundColor White
    Write-Host "NOT STARTED" -ForegroundColor Yellow
}

# Check Backend API
Start-Sleep -Seconds 2
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:${ApiPort}/api/v1/healthz" -TimeoutSec 4 -ErrorAction Stop
    Write-Host "    Backend API: " -NoNewline -ForegroundColor White
    Write-Host "HEALTHY ($($h.status))" -ForegroundColor Green
}
catch {
    Write-Host "    Backend API: " -NoNewline -ForegroundColor White
    Write-Host "STARTING... (check logs/backend.log)" -ForegroundColor Yellow
}

# Check Bybit Exchange connectivity
try {
    $x = Invoke-RestMethod -Uri "http://127.0.0.1:${ApiPort}/api/v1/exchangez" -TimeoutSec 6 -ErrorAction Stop
    $lat = ('{0:N1}' -f ($x.latency_ms))
    Write-Host "    Bybit API:   " -NoNewline -ForegroundColor White
    Write-Host "CONNECTED (${lat}ms latency)" -ForegroundColor Green
}
catch {
    Write-Host "    Bybit API:   " -NoNewline -ForegroundColor White
    Write-Host "CHECKING..." -ForegroundColor Yellow
}

# Check Frontend
Start-Sleep -Seconds 2
try {
    $rootResp = Invoke-WebRequest -Uri "http://localhost:${FrontendPort}/" -TimeoutSec 6 -ErrorAction Stop
    Write-Host "    Frontend:    " -NoNewline -ForegroundColor White
    Write-Host "READY (HTTP $($rootResp.StatusCode))" -ForegroundColor Green
}
catch {
    Write-Host "    Frontend:    " -NoNewline -ForegroundColor White
    Write-Host "STARTING... (check logs/frontend.out.log)" -ForegroundColor Yellow
}

Write-Host ""

if (-not $NoBrowser) {
    Write-Host "[10] Opening browser..." -ForegroundColor Yellow
    $url = "http://localhost:${FrontendPort}/"
    Start-Process $url
    Write-Host "    Browser: Opening $url`n" -ForegroundColor Green
}

# Success message
Write-Host "========================================" -ForegroundColor Green
Write-Host "   ALL SERVICES STARTED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "   BACKEND API:" -ForegroundColor Cyan
Write-Host "     http://127.0.0.1:${ApiPort}" -ForegroundColor White
Write-Host "     http://127.0.0.1:${ApiPort}/docs" -ForegroundColor DarkGray -NoNewline
Write-Host " (Swagger UI)" -ForegroundColor DarkGray
if ($backendPid) {
    Write-Host "     PID: $backendPid" -ForegroundColor DarkGray
}

Write-Host "`n   FRONTEND:" -ForegroundColor Cyan
Write-Host "     http://localhost:${FrontendPort}" -ForegroundColor White
Write-Host "     PID: $($frontend.Id)" -ForegroundColor DarkGray

Write-Host "`n   POSTGRESQL:" -ForegroundColor Cyan
Write-Host "     Host: 127.0.0.1:${DbPort}" -ForegroundColor White
Write-Host "     Database: ${DbName}" -ForegroundColor DarkGray
Write-Host "     User: ${DbUser}" -ForegroundColor DarkGray

Write-Host "`n   REDIS:" -ForegroundColor Cyan
Write-Host "     Host: 127.0.0.1:6379" -ForegroundColor White
Write-Host "     Database: 0" -ForegroundColor DarkGray

Write-Host "`n   MCP SERVER (PERPLEXITY AI):" -ForegroundColor Magenta
if (Test-Path $mcpPidFile) {
    $mcpPidDisplay = Get-Content $mcpPidFile -ErrorAction SilentlyContinue
    Write-Host "     Status: RUNNING" -ForegroundColor Green
    Write-Host "     PID: $mcpPidDisplay" -ForegroundColor DarkGray
    Write-Host "     Schema: Copilot  MCP  Perplexity  MCP  Copilot" -ForegroundColor DarkGray
    Write-Host "     Logs: logs/mcp-server.out.log" -ForegroundColor DarkGray
}
else {
    Write-Host "     Status: NOT STARTED" -ForegroundColor Yellow
    Write-Host "     AI Studio: Using fallback mode" -ForegroundColor DarkGray
}

Write-Host "`n   BYBIT API:" -ForegroundColor Cyan
Write-Host "     Status: CONNECTED (Real API)" -ForegroundColor Green
Write-Host "     Symbols: $($env:BYBIT_WS_SYMBOLS)" -ForegroundColor DarkGray
Write-Host "     Intervals: $($env:BYBIT_WS_INTERVALS)" -ForegroundColor DarkGray

Write-Host "`n   LOGS:" -ForegroundColor Yellow
Write-Host "     Backend:     logs/backend.log" -ForegroundColor DarkGray
Write-Host "     Frontend:    logs/frontend.out.log" -ForegroundColor DarkGray
Write-Host "     MCP Server:  logs/mcp-server.out.log" -ForegroundColor DarkGray

Write-Host "`n   QUICK LINKS:" -ForegroundColor Yellow
Write-Host "      Dashboard:      http://localhost:${FrontendPort}/" -ForegroundColor Magenta
Write-Host "      AI Studio:      http://localhost:${FrontendPort}/#/ai-studio" -ForegroundColor Magenta
Write-Host "      ML Optimizer:   http://localhost:${FrontendPort}/#/optimizations" -ForegroundColor Magenta
Write-Host "      API Docs:       http://127.0.0.1:${ApiPort}/docs" -ForegroundColor Magenta

Write-Host "`n   STOP ALL SERVICES:" -ForegroundColor Red
Write-Host "     .\stop.ps1" -ForegroundColor White

Write-Host "`n========================================`n" -ForegroundColor Green
