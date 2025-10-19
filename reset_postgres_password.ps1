# ============================================================================
# Reset PostgreSQL Password
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL Password Reset" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Administrator privileges required!" -ForegroundColor Red
    exit 1
}

# PostgreSQL paths
$pgDataDir = "C:\Program Files\PostgreSQL\16\data"
$pgHbaPath = "$pgDataDir\pg_hba.conf"
$pgHbaBackup = "$pgDataDir\pg_hba.conf.backup"

if (-not (Test-Path $pgHbaPath)) {
    Write-Host "ERROR: pg_hba.conf not found at: $pgHbaPath" -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Backing up pg_hba.conf..." -ForegroundColor Yellow
Copy-Item $pgHbaPath $pgHbaBackup -Force
Write-Host "   Backup created: $pgHbaBackup" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Modifying pg_hba.conf to allow trust authentication..." -ForegroundColor Yellow

# Read current config
$content = Get-Content $pgHbaPath

# Replace 'scram-sha-256' with 'trust' for local connections
$newContent = $content -replace 'scram-sha-256', 'trust'

# Write new config
$newContent | Set-Content $pgHbaPath -Encoding UTF8

Write-Host "   pg_hba.conf modified" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Restarting PostgreSQL service..." -ForegroundColor Yellow
Restart-Service -Name "postgresql-x64-16"
Start-Sleep -Seconds 3
Write-Host "   Service restarted" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Changing postgres user password..." -ForegroundColor Yellow

$psqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
$changePassword = "ALTER USER postgres WITH PASSWORD 'postgres';"
$tempSqlFile = "$env:TEMP\change_password.sql"
$changePassword | Out-File -FilePath $tempSqlFile -Encoding ASCII

& $psqlPath -U postgres -h localhost -p 5432 -d postgres -f $tempSqlFile 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Password changed to: postgres" -ForegroundColor Green
} else {
    Write-Host "   ERROR: Could not change password" -ForegroundColor Red
}

Remove-Item $tempSqlFile -Force

Write-Host ""
Write-Host "Step 5: Restoring pg_hba.conf..." -ForegroundColor Yellow
Copy-Item $pgHbaBackup $pgHbaPath -Force
Write-Host "   Original config restored" -ForegroundColor Green

Write-Host ""
Write-Host "Step 6: Restarting PostgreSQL service again..." -ForegroundColor Yellow
Restart-Service -Name "postgresql-x64-16"
Start-Sleep -Seconds 3
Write-Host "   Service restarted" -ForegroundColor Green

Write-Host ""
Write-Host "Step 7: Testing connection..." -ForegroundColor Yellow
$env:PGPASSWORD = "postgres"
$result = & $psqlPath -U postgres -h localhost -p 5432 -c "SELECT 'Connection successful!';" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Connection successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host "  PASSWORD RESET COMPLETE!" -ForegroundColor Green
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "   User: postgres" -ForegroundColor White
    Write-Host "   Password: postgres" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "   ERROR: Connection still failing" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try manual password reset:" -ForegroundColor Yellow
    Write-Host "1. Open pgAdmin" -ForegroundColor White
    Write-Host "2. Right-click on 'PostgreSQL 16'" -ForegroundColor White
    Write-Host "3. Properties -> Login/Group Roles -> postgres" -ForegroundColor White
    Write-Host "4. Change password to: postgres" -ForegroundColor White
}

Write-Host ""
