# PostgreSQL + Redis Installation Script
# Run as Administrator!

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL 16 + Redis Installation" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ""
    Write-Host "[ERROR] Administrator rights required!" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host ""
Write-Host "[OK] Administrator rights confirmed" -ForegroundColor Green

# Install Chocolatey
Write-Host ""
Write-Host "Step 1: Checking Chocolatey..." -ForegroundColor Yellow

try {
    $chocoVersion = choco --version 2>&1
    Write-Host "[OK] Chocolatey installed: v$chocoVersion" -ForegroundColor Green
}
catch {
    Write-Host "[INFO] Installing Chocolatey..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString("https://community.chocolatey.org/install.ps1"))
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "[OK] Chocolatey installed" -ForegroundColor Green
}

# Install PostgreSQL
Write-Host ""
Write-Host "Step 2: Installing PostgreSQL 16..." -ForegroundColor Yellow

try {
    $pg = psql --version 2>&1
    if ($pg -match "PostgreSQL.*16") {
        Write-Host "[OK] PostgreSQL 16 already installed" -ForegroundColor Green
    }
    else {
        choco install postgresql16 --params "/Password:postgres123" -y
        Write-Host "[OK] PostgreSQL 16 installed" -ForegroundColor Green
    }
}
catch {
    choco install postgresql16 --params "/Password:postgres123" -y
    Write-Host "[OK] PostgreSQL 16 installed" -ForegroundColor Green
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Install Redis
Write-Host ""
Write-Host "Step 3: Installing Redis..." -ForegroundColor Yellow

try {
    $redis = redis-server --version 2>&1
    if ($redis -match "Redis") {
        Write-Host "[OK] Redis already installed" -ForegroundColor Green
    }
    else {
        choco install redis-64 -y
        Write-Host "[OK] Redis installed" -ForegroundColor Green
    }
}
catch {
    choco install redis-64 -y
    Write-Host "[OK] Redis installed" -ForegroundColor Green
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Install Python drivers
Write-Host ""
Write-Host "Step 4: Installing Python drivers..." -ForegroundColor Yellow

$venvPython = "D:\bybit_strategy_tester_v2\backend\venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython -m pip install --quiet psycopg2-binary asyncpg
    Write-Host "[OK] Python drivers installed" -ForegroundColor Green
}

# Create database
Write-Host ""
Write-Host "Step 5: Creating database..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

try {
    $env:PGPASSWORD = "postgres123"
    $dbExists = psql -U postgres -lqt 2>&1 | Select-String "bybit_strategy_tester"
    
    if (-not $dbExists) {
        psql -U postgres -c "CREATE DATABASE bybit_strategy_tester ENCODING ''UTF8'';" 2>&1 | Out-Null
        Write-Host "[OK] Database created" -ForegroundColor Green
    }
    else {
        Write-Host "[OK] Database exists" -ForegroundColor Green
    }
    
    # Apply schema
    $schemaFile = "D:\bybit_strategy_tester_v2\database_schema.sql"
    if (Test-Path $schemaFile) {
        psql -U postgres -d bybit_strategy_tester -f $schemaFile 2>&1 | Out-Null
        Write-Host "[OK] Schema applied" -ForegroundColor Green
    }
}
catch {
    Write-Host "[WARNING] Database setup incomplete" -ForegroundColor Yellow
}
finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

# Final check
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Installation Complete" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

try { psql --version; Write-Host "" } catch { }
try { redis-server --version; Write-Host "" } catch { }

Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Close and reopen PowerShell" -ForegroundColor White
Write-Host "2. Change PostgreSQL password:" -ForegroundColor White
Write-Host "   psql -U postgres" -ForegroundColor Gray
Write-Host "   ALTER USER postgres WITH PASSWORD ''your_password'';" -ForegroundColor Gray
Write-Host "3. Update .env file" -ForegroundColor White
Write-Host "4. Start backend:" -ForegroundColor White
Write-Host "   cd backend" -ForegroundColor Gray
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "   uvicorn main:app --reload" -ForegroundColor Gray
Write-Host ""
pause
