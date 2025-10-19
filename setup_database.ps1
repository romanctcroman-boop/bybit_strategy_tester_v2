# ============================================================================
# ⚠️  DEPRECATED - DO NOT USE
# ============================================================================
# This script is OBSOLETE and contains syntax errors
# 
# The project NO LONGER uses PostgreSQL or Redis
# All functionality works without external databases
#
# Use start.ps1 instead to launch the application
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Red
Write-Host "  ⚠️  DEPRECATED SCRIPT - DO NOT USE" -ForegroundColor Red
Write-Host "============================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "This script is OBSOLETE and contains 22+ syntax errors" -ForegroundColor Yellow
Write-Host ""
Write-Host "REASON:" -ForegroundColor Cyan
Write-Host "  • Project no longer uses PostgreSQL" -ForegroundColor Gray
Write-Host "  • Project no longer uses Redis" -ForegroundColor Gray
Write-Host "  • All data stored in files (data/cache/)" -ForegroundColor Gray
Write-Host "  • Script contains hardcoded paths and broken syntax" -ForegroundColor Gray
Write-Host ""
Write-Host "WHAT TO USE INSTEAD:" -ForegroundColor Cyan
Write-Host "  .\start.ps1" -ForegroundColor Green
Write-Host ""
Write-Host "This will:" -ForegroundColor Gray
Write-Host "  ✅ Start backend API (port 8000)" -ForegroundColor Gray
Write-Host "  ✅ Start frontend server (port 8080)" -ForegroundColor Gray
Write-Host "  ✅ Open browser automatically" -ForegroundColor Gray
Write-Host ""
Write-Host "For more information, see:" -ForegroundColor Cyan
Write-Host "  • QUICK_START.md" -ForegroundColor White
Write-Host "  • API_READY.md" -ForegroundColor White
Write-Host "  • PROJECT_STATUS.md" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
exit 0

# ============================================================================
# OLD CODE BELOW (KEPT FOR REFERENCE ONLY - DO NOT EXECUTE)
# ============================================================================
<#
# Step 1: Verify PostgreSQL
Write-Host "Step 1: Verifying PostgreSQL..." -ForegroundColor Yellow

try {
    $pgVersion = psql --version 2>&1
    Write-Host "[OK] $pgVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] PostgreSQL not found in PATH" -ForegroundColor Red
    Write-Host "Please restart PowerShell and try again" -ForegroundColor Yellow
    pause
    exit 1
}

# Step 2: Check PostgreSQL service
Write-Host ""
Write-Host "Step 2: Checking PostgreSQL service..." -ForegroundColor Yellow

$pgService = Get-Service "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($pgService) {
    Write-Host "[OK] Service: $($pgService.DisplayName)" -ForegroundColor Green
    Write-Host "    Status: $($pgService.Status)" -ForegroundColor $(if($pgService.Status -eq ''Running''){''Green''}else{''Yellow''})
    
    if ($pgService.Status -ne ''Running'') {
        Write-Host "    Starting service..." -ForegroundColor Yellow
        Start-Service $pgService.Name
        Start-Sleep -Seconds 3
    }
}
else {
    Write-Host "[WARNING] PostgreSQL service not found" -ForegroundColor Yellow
}

# Step 3: Create database
Write-Host ""
Write-Host "Step 3: Creating database..." -ForegroundColor Yellow

$env:PGPASSWORD = "postgres123"

try {
    # Check if database exists
    $dbExists = psql -U postgres -lqt 2>&1 | Select-String "bybit_strategy_tester"
    
    if ($dbExists) {
        Write-Host "[OK] Database already exists" -ForegroundColor Green
    }
    else {
        Write-Host "    Creating database..." -ForegroundColor Gray
        $result = psql -U postgres -c "CREATE DATABASE bybit_strategy_tester ENCODING ''UTF8'';" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Database created" -ForegroundColor Green
        }
        else {
            Write-Host "[ERROR] Failed to create database" -ForegroundColor Red
            Write-Host "Error: $result" -ForegroundColor Gray
        }
    }
}
catch {
    Write-Host "[ERROR] Cannot connect to PostgreSQL" -ForegroundColor Red
    Write-Host "Make sure PostgreSQL service is running" -ForegroundColor Yellow
}

# Step 4: Apply schema
Write-Host ""
Write-Host "Step 4: Applying database schema..." -ForegroundColor Yellow

$schemaFile = "D:\bybit_strategy_tester_v2\database_schema.sql"

if (Test-Path $schemaFile) {
    try {
        Write-Host "    Executing SQL script..." -ForegroundColor Gray
        $result = psql -U postgres -d bybit_strategy_tester -f $schemaFile 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Schema applied successfully" -ForegroundColor Green
        }
        else {
            Write-Host "[WARNING] Schema applied with warnings" -ForegroundColor Yellow
            Write-Host "This is normal if running multiple times" -ForegroundColor Gray
        }
    }
    catch {
        Write-Host "[ERROR] Failed to apply schema" -ForegroundColor Red
    }
}
else {
    Write-Host "[ERROR] Schema file not found: $schemaFile" -ForegroundColor Red
}

# Step 5: Verify database
Write-Host ""
Write-Host "Step 5: Verifying database..." -ForegroundColor Yellow

try {
    $tables = psql -U postgres -d bybit_strategy_tester -c "\dt" 2>&1
    
    if ($tables -match "users|strategies|backtests") {
        Write-Host "[OK] Database tables created" -ForegroundColor Green
    }
    else {
        Write-Host "[WARNING] Tables may not be created properly" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[WARNING] Cannot verify tables" -ForegroundColor Yellow
}

Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

# Step 6: Check Redis
Write-Host ""
Write-Host "Step 6: Checking Redis..." -ForegroundColor Yellow

try {
    $redisService = Get-Service "Memurai*" -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if ($redisService) {
        Write-Host "[OK] Service: $($redisService.DisplayName)" -ForegroundColor Green
        Write-Host "    Status: $($redisService.Status)" -ForegroundColor $(if($redisService.Status -eq ''Running''){''Green''}else{''Yellow''})
        
        if ($redisService.Status -ne ''Running'') {
            Write-Host "    Starting service..." -ForegroundColor Yellow
            Start-Service $redisService.Name
        }
    }
    else {
        Write-Host "[WARNING] Memurai service not found" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[WARNING] Cannot check Redis service" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Change PostgreSQL password!" -ForegroundColor Red
Write-Host ""
Write-Host "Run these commands:" -ForegroundColor Yellow
Write-Host "  psql -U postgres" -ForegroundColor White
Write-Host "  ALTER USER postgres WITH PASSWORD ''your_secure_password'';" -ForegroundColor White
Write-Host "  \q" -ForegroundColor White
Write-Host ""
Write-Host "Then update .env file with new password" -ForegroundColor Yellow
Write-Host ""
Write-Host "Start backend:" -ForegroundColor Yellow
Write-Host "  cd D:\bybit_strategy_tester_v2\backend" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  uvicorn main:app --reload" -ForegroundColor White
Write-Host ""
pause
#>
