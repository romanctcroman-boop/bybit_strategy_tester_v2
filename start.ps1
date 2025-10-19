# Bybit Strategy Tester v2.0 - Main Launch Script
# Starts Backend (FastAPI) + Frontend (React+Vite) + Opens browser

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  BYBIT STRATEGY TESTER v2.0" -ForegroundColor Cyan
Write-Host "  Starting Full System..." -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendPath = Join-Path $scriptPath "frontend"

# Check if ports are already in use
function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

$backendRunning = Test-Port -Port 8000
$frontendRunning = Test-Port -Port 5173

Write-Host "Status Check..." -ForegroundColor Yellow
if ($backendRunning) {
    Write-Host "  [OK] Backend already running (port 8000)" -ForegroundColor Green
}
else {
    Write-Host "  [ ] Backend not running" -ForegroundColor Gray
}

if ($frontendRunning) {
    Write-Host "  [OK] Frontend already running (port 5173)" -ForegroundColor Green
}
else {
    Write-Host "  [ ] Frontend not running" -ForegroundColor Gray
}

Write-Host ""

# If both already running, just open browser
if ($backendRunning -and $frontendRunning) {
    Write-Host "System already running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Frontend App:  http://localhost:5173" -ForegroundColor Cyan
    Write-Host "  Backend Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Opening browser..." -ForegroundColor Yellow
    Start-Process "http://localhost:5173"
    exit 0
}

# Start Backend (if not running)
if (-not $backendRunning) {
    Write-Host "[1/2] Starting Backend API (FastAPI)..." -ForegroundColor Yellow
    $backendCmd = "cd '$scriptPath'; Write-Host 'Backend API Server' -ForegroundColor Cyan; Write-Host 'URL: http://localhost:8000' -ForegroundColor Gray; python -m uvicorn backend.main:app --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    Write-Host "  Waiting for Backend to start..." -ForegroundColor Gray
    
    # Wait for backend to be ready
    $attempts = 0
    while ($attempts -lt 20) {
        Start-Sleep -Seconds 1
        if (Test-Port -Port 8000) {
            Write-Host "  Backend is ready!" -ForegroundColor Green
            break
        }
        $attempts++
    }
}

# Start Frontend (if not running)
if (-not $frontendRunning) {
    Write-Host "[2/2] Starting Frontend (React + Vite)..." -ForegroundColor Yellow
    $frontendCmd = "cd '$frontendPath'; Write-Host 'Frontend Dev Server' -ForegroundColor Cyan; Write-Host 'URL: http://localhost:5173' -ForegroundColor Gray; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    Write-Host "  Waiting for Frontend to start..." -ForegroundColor Gray
    
    # Wait for frontend to be ready
    $attempts = 0
    while ($attempts -lt 20) {
        Start-Sleep -Seconds 1
        if (Test-Port -Port 5173) {
            Write-Host "  Frontend is ready!" -ForegroundColor Green
            break
        }
        $attempts++
    }
}

# Open browsers
Write-Host ""
Write-Host "Opening application in browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  SYSTEM RUNNING!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor White
Write-Host "  Frontend App:    http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API Docs:        http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  ReDoc:           http://localhost:8000/redoc" -ForegroundColor Cyan
Write-Host "  Health Check:    http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor White
Write-Host "  - Dashboard with statistics" -ForegroundColor Gray
Write-Host "  - Backtesting engine" -ForegroundColor Gray
Write-Host "  - Strategy optimization" -ForegroundColor Gray
Write-Host "  - Real-time market data" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop: Close PowerShell windows or press Ctrl+C" -ForegroundColor Gray
Write-Host ""
