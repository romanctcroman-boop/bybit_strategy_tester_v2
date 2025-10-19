# Simple Start Script - Runs both services in current terminal
# Use this if start.ps1 doesn't work properly

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  BYBIT STRATEGY TESTER v2.0" -ForegroundColor Cyan
Write-Host "  Simple Launcher" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendPath = Join-Path $scriptPath "frontend"

# Check if services are already running
function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

$backendRunning = Test-Port -Port 8000
$frontendRunning = Test-Port -Port 5173

Write-Host "Current Status:" -ForegroundColor Yellow
Write-Host "  Backend (8000):  $(if ($backendRunning) { '[RUNNING]' } else { '[STOPPED]' })" -ForegroundColor $(if ($backendRunning) { 'Green' } else { 'Red' })
Write-Host "  Frontend (5173): $(if ($frontendRunning) { '[RUNNING]' } else { '[STOPPED]' })" -ForegroundColor $(if ($frontendRunning) { 'Green' } else { 'Red' })
Write-Host ""

if ($backendRunning -and $frontendRunning) {
    Write-Host "Both services already running!" -ForegroundColor Green
    Write-Host "Opening browser..." -ForegroundColor Yellow
    Start-Process "http://localhost:5173"
    exit 0
}

Write-Host "Starting services in separate windows..." -ForegroundColor Yellow
Write-Host ""

# Start Backend if not running
if (-not $backendRunning) {
    Write-Host "[1/2] Starting Backend..." -ForegroundColor Yellow
    $backendScript = @"
`$Host.UI.RawUI.WindowTitle = 'Backend API - Port 8000'
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  BACKEND API SERVER' -ForegroundColor Cyan
Write-Host '  Port: 8000' -ForegroundColor Yellow
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
cd '$scriptPath'
python -m uvicorn backend.main:app --reload
"@
    
    $backendScript | Out-File -FilePath "$env:TEMP\start_backend.ps1" -Encoding UTF8
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$env:TEMP\start_backend.ps1"
    
    Write-Host "  Waiting for Backend..." -ForegroundColor Gray
    $attempts = 0
    while ($attempts -lt 30) {
        Start-Sleep -Milliseconds 500
        if (Test-Port -Port 8000) {
            Write-Host "  [OK] Backend ready!" -ForegroundColor Green
            break
        }
        $attempts++
    }
    if ($attempts -eq 30) {
        Write-Host "  [WARNING] Backend timeout - check Backend window" -ForegroundColor Yellow
    }
}

# Start Frontend if not running
if (-not $frontendRunning) {
    Write-Host "[2/2] Starting Frontend..." -ForegroundColor Yellow
    $frontendScript = @"
`$Host.UI.RawUI.WindowTitle = 'Frontend Dev Server - Port 5173'
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  FRONTEND DEV SERVER' -ForegroundColor Cyan
Write-Host '  Port: 5173' -ForegroundColor Yellow
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
cd '$frontendPath'
npm run dev
"@
    
    $frontendScript | Out-File -FilePath "$env:TEMP\start_frontend.ps1" -Encoding UTF8
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$env:TEMP\start_frontend.ps1"
    
    Write-Host "  Waiting for Frontend..." -ForegroundColor Gray
    $attempts = 0
    while ($attempts -lt 30) {
        Start-Sleep -Milliseconds 500
        if (Test-Port -Port 5173) {
            Write-Host "  [OK] Frontend ready!" -ForegroundColor Green
            break
        }
        $attempts++
    }
    if ($attempts -eq 30) {
        Write-Host "  [WARNING] Frontend timeout - check Frontend window" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  STARTUP COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor White
Write-Host "  Frontend:     http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Health Check: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Press any key to exit (services will keep running)..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
