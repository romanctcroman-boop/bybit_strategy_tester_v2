# ============================================================================
# Quick PostgreSQL Connection Helper
# ============================================================================

$PSQL = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
$PGHOST = "localhost"
$PGPORT = "5432"
$PGUSER = "postgres"
$PGDATABASE = "bybit_strategy_tester"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL Connection Helper" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ----------------------------------------------------------------------------
# Test 1: Check if PostgreSQL is running
# ----------------------------------------------------------------------------
Write-Host "[1/5] Checking PostgreSQL service..." -ForegroundColor Yellow
$service = Get-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "✅ PostgreSQL service is running`n" -ForegroundColor Green
} else {
    Write-Host "❌ PostgreSQL service is NOT running" -ForegroundColor Red
    Write-Host "   Run: Start-Service postgresql-x64-16`n" -ForegroundColor Yellow
    exit 1
}

# ----------------------------------------------------------------------------
# Test 2: Check if database exists
# ----------------------------------------------------------------------------
Write-Host "[2/5] Checking if database exists..." -ForegroundColor Yellow
$env:PGPASSWORD = "postgres123"
$dbCheck = & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d postgres -t -c "SELECT 1 FROM pg_database WHERE datname='$PGDATABASE'" 2>$null

if ($dbCheck -match "1") {
    Write-Host "✅ Database '$PGDATABASE' exists`n" -ForegroundColor Green
} else {
    Write-Host "⚠️  Database '$PGDATABASE' does NOT exist" -ForegroundColor Yellow
    Write-Host "   Creating database..." -ForegroundColor Gray
    
    & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d postgres -c "CREATE DATABASE $PGDATABASE WITH ENCODING='UTF8';" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Database created successfully`n" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create database`n" -ForegroundColor Red
        exit 1
    }
}

# ----------------------------------------------------------------------------
# Test 3: Check TimescaleDB extension
# ----------------------------------------------------------------------------
Write-Host "[3/5] Checking TimescaleDB extension..." -ForegroundColor Yellow
$tsdbCheck = & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d $PGDATABASE -t -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb'" 2>$null

if ($tsdbCheck) {
    $version = $tsdbCheck.Trim()
    Write-Host "✅ TimescaleDB version: $version`n" -ForegroundColor Green
} else {
    Write-Host "⚠️  TimescaleDB extension NOT installed" -ForegroundColor Yellow
    Write-Host "   Installing extension..." -ForegroundColor Gray
    
    & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d $PGDATABASE -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ TimescaleDB extension installed`n" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to install TimescaleDB (this is OK if not needed)`n" -ForegroundColor Yellow
    }
}

# ----------------------------------------------------------------------------
# Test 4: Check tables
# ----------------------------------------------------------------------------
Write-Host "[4/5] Checking database schema..." -ForegroundColor Yellow
$tableCount = & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d $PGDATABASE -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>$null

if ($tableCount) {
    $count = $tableCount.Trim()
    Write-Host "✅ Tables found: $count" -ForegroundColor Green
    
    if ($count -eq "0") {
        Write-Host "   ⚠️  No tables found. Run: .\setup_database.ps1" -ForegroundColor Yellow
    } else {
        # List tables
        Write-Host "   Tables:" -ForegroundColor Gray
        & $PSQL -U $PGUSER -h $PGHOST -p $PGPORT -d $PGDATABASE -c "\dt" 2>$null | Select-Object -Skip 2 | Select-Object -SkipLast 2 | ForEach-Object {
            Write-Host "   $_" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
} else {
    Write-Host "❌ Failed to query tables`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Test 5: Connection string for VS Code
# ----------------------------------------------------------------------------
Write-Host "[5/5] Connection details for VS Code..." -ForegroundColor Yellow
Write-Host "   Connection Name: Bybit Strategy Tester" -ForegroundColor Gray
Write-Host "   Server: $PGHOST" -ForegroundColor Gray
Write-Host "   Port: $PGPORT" -ForegroundColor Gray
Write-Host "   Database: $PGDATABASE" -ForegroundColor Gray
Write-Host "   Username: $PGUSER" -ForegroundColor Gray
Write-Host "   Password: postgres123" -ForegroundColor Gray
Write-Host ""
Write-Host "   Connection String:" -ForegroundColor Gray
Write-Host "   postgresql://${PGUSER}:postgres123@${PGHOST}:${PGPORT}/${PGDATABASE}" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "1️⃣  Open VS Code PostgreSQL Extension (Ctrl+Shift+P → 'PostgreSQL: New Connection')" -ForegroundColor Yellow
Write-Host "2️⃣  Use connection details above" -ForegroundColor Yellow
Write-Host "3️⃣  If no tables, run: .\setup_database.ps1" -ForegroundColor Yellow
Write-Host "4️⃣  Or apply schema manually: psql -U postgres -d $PGDATABASE -f database_schema.sql`n" -ForegroundColor Yellow

# Create .env if not exists
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file with database connection..." -ForegroundColor Yellow
    
    $envContent = @"
# PostgreSQL Connection
DATABASE_URL=postgresql://${PGUSER}:postgres123@${PGHOST}:${PGPORT}/${PGDATABASE}
POSTGRES_HOST=$PGHOST
POSTGRES_PORT=$PGPORT
POSTGRES_DB=$PGDATABASE
POSTGRES_USER=$PGUSER
POSTGRES_PASSWORD=postgres123

# Redis Connection  
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# API Settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=True

# Bybit API (optional - for live data loading)
BYBIT_API_KEY=
BYBIT_API_SECRET=
"@
    
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host ".env file created" -ForegroundColor Green
    Write-Host ""
}

Write-Host "PostgreSQL is ready for VS Code connection!" -ForegroundColor Green
Write-Host ""
