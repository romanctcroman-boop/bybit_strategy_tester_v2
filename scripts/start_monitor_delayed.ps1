# Auto-start MCP Monitor
# Запускается через 5 секунд после старта MCP сервера

$projectRoot = "D:\bybit_strategy_tester_v2"
$monitorScript = "$projectRoot\scripts\mcp_monitor_simple.ps1"

# Ждём запуска MCP сервера
Start-Sleep -Seconds 5

# Проверяем что MCP сервер запустился
$pythonProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*bybit_strategy_tester_v2*" }

if ($pythonProcess) {
    # Запускаем монитор
    if (Test-Path $monitorScript) {
        Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $monitorScript -WindowStyle Normal
        Write-Host "MCP Monitor запущен!" -ForegroundColor Green
    }
}
else {
    Write-Host "MCP Server не запущен. Монитор не запускается." -ForegroundColor Yellow
}
