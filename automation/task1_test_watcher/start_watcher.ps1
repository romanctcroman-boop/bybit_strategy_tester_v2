# Start Test Watcher
# Windows PowerShell script to start the Test Watcher

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  BYBIT STRATEGY TESTER V2 - TEST WATCHER" -ForegroundColor Yellow
Write-Host "  Автоматическая верификация тестов через DeepSeek AI" -ForegroundColor White
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

# Check if .env file exists
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host " Error: .env file not found" -ForegroundColor Red
    Write-Host "   Please create .env file with DEEPSEEK_API_KEY" -ForegroundColor Yellow
    exit 1
}

# Check for encrypted_secrets.json or DEEPSEEK_API_KEY
$secretsFile = Join-Path $projectRoot "encrypted_secrets.json"
$hasEncryptedSecrets = Test-Path $secretsFile

if ($hasEncryptedSecrets) {
    Write-Host " Using encrypted API keys (KeyManager)" -ForegroundColor Green
}
else {
    Write-Host "  Using API keys from .env (consider encrypting)" -ForegroundColor Yellow
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
$resultsDir = Join-Path $projectRoot "ai_audit_results"
if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
    Write-Host " Created: ai_audit_results/" -ForegroundColor Green
}

# Start the test watcher
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " Starting Test Watcher..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Configuration:" -ForegroundColor Yellow
Write-Host "   - Watch path: $projectRoot" -ForegroundColor White
Write-Host "   - Debounce: 20 seconds" -ForegroundColor White
Write-Host "   - Results: ai_audit_results/" -ForegroundColor White
Write-Host "   - Logs: test_watcher.log" -ForegroundColor White
Write-Host ""
Write-Host " Test Watcher будет:" -ForegroundColor Cyan
Write-Host "   1. Мониторить изменения .py файлов" -ForegroundColor White
Write-Host "   2. Автоматически запускать тесты с coverage" -ForegroundColor White
Write-Host "   3. Отправлять результаты в DeepSeek для анализа" -ForegroundColor White
Write-Host "   4. Сохранять отчеты в ai_audit_results/" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Change to project root and run
Set-Location $projectRoot
$watcherScript = Join-Path $scriptPath "test_watcher.py"

try {
    & $pythonPath $watcherScript
}
catch {
    Write-Host ""
    Write-Host " Test Watcher stopped with error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host " Test Watcher stopped successfully" -ForegroundColor Green