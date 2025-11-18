# Автозапуск MCP Monitor при старте IDE
# Этот скрипт автоматически запускается вместе с MCP сервером

Write-Host "Запуск MCP Monitor..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

# Запустить монитор в отдельном окне
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\mcp_monitor_simple.ps1"

Write-Host "MCP Monitor запущен успешно!" -ForegroundColor Green
