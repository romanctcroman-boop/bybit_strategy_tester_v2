# ==============================================================================
# MCP Server Debug Launcher
# ==============================================================================
# Запускает MCP сервер с подробным выводом для отладки

$ErrorActionPreference = "Stop"

# Пути
$projectRoot = "D:\bybit_strategy_tester_v2"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mcpServer = Join-Path $projectRoot "mcp-server\server.py"
$logsDir = Join-Path $projectRoot "logs"

# Создать директорию для логов
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

# Timestamp для лога
$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$logFile = Join-Path $logsDir "mcp_debug_$timestamp.log"

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  MCP SERVER - DEBUG MODE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Проверки
Write-Host "[CHECK] Project Root: " -NoNewline
if (Test-Path $projectRoot) {
    Write-Host "OK" -ForegroundColor Green
    Write-Host "        $projectRoot" -ForegroundColor Gray
}
else {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "        Path not found: $projectRoot" -ForegroundColor Red
    exit 1
}

Write-Host "[CHECK] Python venv: " -NoNewline
if (Test-Path $venvPython) {
    Write-Host "OK" -ForegroundColor Green
    Write-Host "        $venvPython" -ForegroundColor Gray
}
else {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "        Python executable not found" -ForegroundColor Red
    exit 1
}

Write-Host "[CHECK] MCP Server: " -NoNewline
if (Test-Path $mcpServer) {
    Write-Host "OK" -ForegroundColor Green
    Write-Host "        $mcpServer" -ForegroundColor Gray
}
else {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "        Server script not found" -ForegroundColor Red
    exit 1
}

# API Keys
Write-Host ""
Write-Host "[CONFIG] Setting environment variables..." -ForegroundColor Yellow
$env:PERPLEXITY_API_KEY = "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"
$env:DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"

Write-Host "         PERPLEXITY_API_KEY: " -NoNewline -ForegroundColor Gray
Write-Host "pplx-FSlOe...hTF2R" -ForegroundColor Green
Write-Host "         DEEPSEEK_API_KEY: " -NoNewline -ForegroundColor Gray
Write-Host "sk-1630f...37242" -ForegroundColor Green

# Log file
Write-Host ""
Write-Host "[LOG] Output will be saved to:" -ForegroundColor Yellow
Write-Host "      $logFile" -ForegroundColor Gray

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  STARTING MCP SERVER..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Запуск сервера с логированием
try {
    # Запуск с Tee-Object для одновременного вывода в консоль и файл
    & $venvPython $mcpServer 2>&1 | Tee-Object -FilePath $logFile
    
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    
    if ($exitCode -eq 0) {
        Write-Host "  SERVER STOPPED NORMALLY" -ForegroundColor Green
    }
    else {
        Write-Host "  SERVER EXITED WITH ERROR (CODE: $exitCode)" -ForegroundColor Red
    }
    
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[LOG] Full log saved to: $logFile" -ForegroundColor Yellow
    
    exit $exitCode
    
}
catch {
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host "  FATAL ERROR" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "[LOG] Error log saved to: $logFile" -ForegroundColor Yellow
    
    exit 1
}
