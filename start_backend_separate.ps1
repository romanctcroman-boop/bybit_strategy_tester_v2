# Скрипт запуска Agent-to-Agent Backend в отдельном окне

Write-Host "Starting Agent-to-Agent Backend in separate terminal..." -ForegroundColor Cyan

# Путь к проекту
$projectPath = "D:\bybit_strategy_tester_v2"

# Команда для запуска uvicorn
$uvicornCmd = "py -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

# Запуск в новом окне PowerShell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$projectPath'; Write-Host 'Agent-to-Agent Backend Server' -ForegroundColor Green; Write-Host 'Port: 8000' -ForegroundColor Yellow; Write-Host ''; Invoke-Expression '$uvicornCmd'"

Write-Host "Backend started in separate window!" -ForegroundColor Green
Write-Host "WebSocket URL: ws://localhost:8000/api/v1/agent/ws" -ForegroundColor Yellow
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Waiting 5 seconds for backend to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
