# Start Audit Agent
# Windows PowerShell script to start the Audit Agent

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  BYBIT STRATEGY TESTER V2 - AUDIT AGENT" -ForegroundColor Yellow
Write-Host "  Автоматический аудит проекта в фоновом режиме" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptPath)

Write-Host " Project root: $projectRoot" -ForegroundColor Green

# Check if Python is available
try {
    $pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
    
    if (-not (Test-Path $pythonPath)) {
        Write-Host " Error: Virtual environment not found at .venv" -ForegroundColor Red
        Write-Host "   Please run setup first." -ForegroundColor Yellow
        exit 1
    }
    
    $pythonVersion = & $pythonPath --version
    Write-Host " Python: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host " Error: Python is not available" -ForegroundColor Red
    exit 1
}

# Install requirements if needed
Write-Host ""
Write-Host " Checking dependencies..." -ForegroundColor Cyan
$requirementsFile = Join-Path $scriptPath "requirements.txt"

try {
    & $pythonPath -m pip install -q -r $requirementsFile
    Write-Host " Dependencies installed" -ForegroundColor Green
}
catch {
    Write-Host " Error installing dependencies" -ForegroundColor Red
    exit 1
}

# Create necessary directories
$logsDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
    Write-Host " Created: logs/" -ForegroundColor Green
}

$resultsDir = Join-Path $projectRoot "audit_reports"
if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
    Write-Host " Created: audit_reports/" -ForegroundColor Green
}

# Start the audit agent
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " Starting Audit Agent..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Configuration:" -ForegroundColor Yellow
Write-Host "   - Watch path: $projectRoot" -ForegroundColor White
Write-Host "   - Check interval: 5 minutes" -ForegroundColor White
Write-Host "   - Reports: audit_reports/" -ForegroundColor White
Write-Host "   - Logs: logs/audit_agent.log" -ForegroundColor White
Write-Host ""
Write-Host " Audit Agent будет:" -ForegroundColor Cyan
Write-Host "   1. Мониторить marker файлы (*_COMPLETE.md, *_TODO.md)" -ForegroundColor White
Write-Host "   2. Отслеживать покрытие тестами (coverage)" -ForegroundColor White
Write-Host "   3. Проверять качество кода" -ForegroundColor White
Write-Host "   4. Генерировать отчеты каждые 5 минут" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Change to project root and run
Set-Location $projectRoot
$agentScript = Join-Path $scriptPath "audit_agent.py"

try {
    & $pythonPath $agentScript
}
catch {
    Write-Host ""
    Write-Host " Audit Agent stopped with error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host " Audit Agent stopped successfully" -ForegroundColor Green