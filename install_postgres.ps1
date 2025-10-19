# ============================================================================
# PostgreSQL + TimescaleDB Installation Script
# ============================================================================
# 
# Automated installation of PostgreSQL 16 and TimescaleDB for Windows
# Creates database: bybit_strategy_tester
#
# Run: .\install_postgres.ps1
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL + TimescaleDB Installation" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester v2" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check administrator privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "WARNING: ADMINISTRATOR PRIVILEGES REQUIRED!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please restart PowerShell as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Close this window" -ForegroundColor Yellow
    Write-Host "2. Right-click on PowerShell" -ForegroundColor Yellow
    Write-Host "3. Select 'Run as administrator'" -ForegroundColor Yellow
    Write-Host "4. Run script again: .\install_postgres.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check Chocolatey
Write-Host "Checking Chocolatey..." -ForegroundColor Yellow
$chocoInstalled = Get-Command choco -ErrorAction SilentlyContinue

if (-not $chocoInstalled) {
    Write-Host "Chocolatey not found. Installing..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Update PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Host "Chocolatey installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Chocolatey already installed" -ForegroundColor Green
}

Write-Host ""

# Check PostgreSQL
Write-Host "Checking PostgreSQL..." -ForegroundColor Yellow
$pgInstalled = Test-Path "C:\Program Files\PostgreSQL\16\bin\psql.exe"

if ($pgInstalled) {
    Write-Host "PostgreSQL 16 already installed" -ForegroundColor Green
} else {
    Write-Host "Installing PostgreSQL 16..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This may take 5-10 minutes..." -ForegroundColor Cyan
    Write-Host ""
    
    # Install via Chocolatey
    choco install postgresql16 --params '/Password:postgres' -y
    
    # Update PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PostgreSQL 16 installed successfully!" -ForegroundColor Green
        
        # Wait for service to start
        Write-Host "Waiting for PostgreSQL service..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        
        # Check service
        $service = Get-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
        if ($service -and $service.Status -eq "Running") {
            Write-Host "PostgreSQL service is running" -ForegroundColor Green
        } else {
            Write-Host "Trying to start service..." -ForegroundColor Yellow
            Start-Service -Name "postgresql-x64-16"
            Start-Sleep -Seconds 5
            Write-Host "PostgreSQL service started" -ForegroundColor Green
        }
    } else {
        Write-Host "ERROR: PostgreSQL installation failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Install TimescaleDB
Write-Host "Checking TimescaleDB..." -ForegroundColor Yellow

# Path to psql
$psqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe"

if (Test-Path $psqlPath) {
    Write-Host "Downloading TimescaleDB for PostgreSQL 16..." -ForegroundColor Yellow
    
    # TimescaleDB for Windows
    $timescaleVersion = "2.16.1"
    $timescaleUrl = "https://github.com/timescale/timescaledb/releases/download/$timescaleVersion/timescaledb-postgresql-16-$timescaleVersion-windows-amd64.zip"
    $downloadPath = "$env:TEMP\timescaledb.zip"
    $extractPath = "$env:TEMP\timescaledb"
    
    try {
        # Download
        Write-Host "Downloading TimescaleDB..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $timescaleUrl -OutFile $downloadPath -ErrorAction Stop
        
        # Extract
        Write-Host "Extracting..." -ForegroundColor Cyan
        Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
        
        # Copy files
        $pgLibDir = "C:\Program Files\PostgreSQL\16\lib"
        $pgShareDir = "C:\Program Files\PostgreSQL\16\share\extension"
        
        Write-Host "Copying TimescaleDB files..." -ForegroundColor Cyan
        Copy-Item "$extractPath\*.dll" -Destination $pgLibDir -Force
        Copy-Item "$extractPath\*.sql" -Destination $pgShareDir -Force
        Copy-Item "$extractPath\*.control" -Destination $pgShareDir -Force
        
        Write-Host "TimescaleDB installed successfully!" -ForegroundColor Green
        
        # Cleanup
        Remove-Item $downloadPath -Force
        Remove-Item $extractPath -Recurse -Force
    } catch {
        Write-Host "WARNING: Could not install TimescaleDB automatically" -ForegroundColor Yellow
        Write-Host "   You can install it manually later" -ForegroundColor Yellow
        Write-Host "   Link: https://docs.timescale.com/install/latest/self-hosted/installation-windows/" -ForegroundColor Cyan
    }
}

Write-Host ""

# Create database
Write-Host "Creating database..." -ForegroundColor Yellow

$env:PGPASSWORD = "postgres"

$dbExists = & $psqlPath -U postgres -h localhost -p 5432 -t -c "SELECT 1 FROM pg_database WHERE datname = 'bybit_strategy_tester';" 2>$null

if ($dbExists -match "1") {
    Write-Host "Database 'bybit_strategy_tester' already exists" -ForegroundColor Green
} else {
    Write-Host "Creating database 'bybit_strategy_tester'..." -ForegroundColor Yellow
    
    $createDb = "CREATE DATABASE bybit_strategy_tester WITH OWNER = postgres ENCODING = 'UTF8' LC_COLLATE = 'C' LC_CTYPE = 'C' TABLESPACE = pg_default CONNECTION LIMIT = -1;"
    
    # Write to temp file
    $tempSqlFile = "$env:TEMP\create_db.sql"
    $createDb | Out-File -FilePath $tempSqlFile -Encoding ASCII
    
    # Execute
    & $psqlPath -U postgres -h localhost -p 5432 -f $tempSqlFile 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database created successfully!" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Database may already exist" -ForegroundColor Yellow
    }
    
    Remove-Item $tempSqlFile -Force
}

Write-Host ""

# Enable TimescaleDB extension
Write-Host "Enabling TimescaleDB extension..." -ForegroundColor Yellow

$enableExtension = "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

$tempExtFile = "$env:TEMP\enable_timescale.sql"
$enableExtension | Out-File -FilePath $tempExtFile -Encoding ASCII

& $psqlPath -U postgres -h localhost -p 5432 -d bybit_strategy_tester -f $tempExtFile 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "TimescaleDB extension enabled!" -ForegroundColor Green
} else {
    Write-Host "WARNING: TimescaleDB extension not enabled (may already be enabled)" -ForegroundColor Yellow
}

Remove-Item $tempExtFile -Force

Write-Host ""

# Check connection
Write-Host "Testing database connection..." -ForegroundColor Yellow

$testQuery = "SELECT version();"
$tempTestFile = "$env:TEMP\test_connection.sql"
$testQuery | Out-File -FilePath $tempTestFile -Encoding ASCII

$result = & $psqlPath -U postgres -h localhost -p 5432 -d bybit_strategy_tester -f $tempTestFile 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database connection successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "PostgreSQL Info:" -ForegroundColor Cyan
    Write-Host $result
} else {
    Write-Host "ERROR: Database connection failed" -ForegroundColor Red
    exit 1
}

Remove-Item $tempTestFile -Force

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "   Host: localhost" -ForegroundColor White
Write-Host "   Port: 5432" -ForegroundColor White
Write-Host "   Database: bybit_strategy_tester" -ForegroundColor White
Write-Host "   User: postgres" -ForegroundColor White
Write-Host "   Password: postgres" -ForegroundColor White
Write-Host ""
Write-Host "Connection String:" -ForegroundColor Cyan
Write-Host "   postgresql://postgres:postgres@localhost:5432/bybit_strategy_tester" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Step: Creating SQLAlchemy models and migrations" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
