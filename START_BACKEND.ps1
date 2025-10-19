# Start Backend API Server
# Автоматический запуск FastAPI backend с возможностью открыть в браузере

Write-Host "🚀 Запуск Bybit Strategy Tester v2.0 Backend..." -ForegroundColor Cyan
Write-Host ""

# Переход в корневую директорию проекта
Set-Location -Path $PSScriptRoot

# Проверка, не занят ли порт 8000
$port = 8000
$connection = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue

if ($connection.TcpTestSucceeded) {
    Write-Host "⚠️  Порт $port уже занят. Backend уже запущен." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   📚 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "   📖 ReDoc: http://localhost:8000/redoc" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 Открыть Swagger UI в браузере? (Y/N)" -ForegroundColor Yellow
    $answer = Read-Host
    if ($answer -eq "Y" -or $answer -eq "y") {
        Start-Process "http://localhost:8000/docs"
        Write-Host "✅ Swagger UI открыт в браузере!" -ForegroundColor Green
    }
    exit 0
}

# Запуск FastAPI
Write-Host "📦 Запуск FastAPI server..." -ForegroundColor Cyan
Write-Host "   API: http://localhost:8000" -ForegroundColor Gray
Write-Host "   Swagger UI: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "   ReDoc: http://localhost:8000/redoc" -ForegroundColor Gray
Write-Host ""
Write-Host "Нажмите Ctrl+C для остановки сервера" -ForegroundColor Gray
Write-Host ""

# Запуск uvicorn
python -m uvicorn backend.main:app --reload
