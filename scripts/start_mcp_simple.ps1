# ==============================================================================
# MCP Server Simple Launcher
# ==============================================================================
# Простой запуск MCP сервера с минимальным выводом

$ErrorActionPreference = "Stop"

# Пути
$projectRoot = "D:\bybit_strategy_tester_v2"
$venvPython = "$projectRoot\.venv\Scripts\python.exe"
$mcpServer = "$projectRoot\mcp-server\server.py"

# Установка API ключей
$env:PERPLEXITY_API_KEY = "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"
$env:DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"

# Проверки
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Python not found at $venvPython" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $mcpServer)) {
    Write-Host "ERROR: Server not found at $mcpServer" -ForegroundColor Red
    exit 1
}

# Запуск сервера
& $venvPython $mcpServer
