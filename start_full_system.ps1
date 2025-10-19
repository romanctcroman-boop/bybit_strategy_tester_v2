# Запуск полной системы (Backend + Frontend)
# Открывает оба сервера и автоматически запускает приложение в браузере

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  🚀 Bybit Strategy Tester v2.0" -ForegroundColor Cyan
Write-Host "  Полный запуск системы" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Переход в корневую директорию
Set-Location "d:\bybit_strategy_tester_v2"

# Функция для проверки занятости порта
function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

# Проверка портов
$backendRunning = Test-Port -Port 8000
$frontendRunning = Test-Port -Port 5173

Write-Host "📊 Проверка статуса..." -ForegroundColor Yellow
Write-Host ""

if ($backendRunning) {
    Write-Host "✅ Backend уже запущен (порт 8000)" -ForegroundColor Green
}
else {
    Write-Host "⏳ Backend не запущен (порт 8000)" -ForegroundColor Gray
}

if ($frontendRunning) {
    Write-Host "✅ Frontend уже запущен (порт 5173)" -ForegroundColor Green
}
else {
    Write-Host "⏳ Frontend не запущен (порт 5173)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Если оба уже запущены
if ($backendRunning -and $frontendRunning) {
    Write-Host "🎉 Система уже полностью запущена!" -ForegroundColor Green
    Write-Host ""
    Write-Host "   🌐 Frontend: http://localhost:5173" -ForegroundColor Cyan
    Write-Host "   📚 Backend API: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 Открыть приложение в браузере? (Y/N)" -ForegroundColor Yellow
    $answer = Read-Host
    if ($answer -eq "Y" -or $answer -eq "y") {
        Start-Process "http://localhost:5173"
        Write-Host "✅ Приложение открыто в браузере!" -ForegroundColor Green
    }
    exit 0
}

# Если нужно запустить оба сервиса
Write-Host "⚙️  Запуск необходимых сервисов..." -ForegroundColor Yellow
Write-Host ""

# Запуск Backend в отдельном окне (если не запущен)
if (-not $backendRunning) {
    Write-Host "🔧 Запуск Backend в отдельном окне..." -ForegroundColor Cyan
    $backendCmd = "cd d:\bybit_strategy_tester_v2; python -m uvicorn backend.main:app --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    Write-Host "   Ожидание запуска Backend..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}

# Запуск Frontend в отдельном окне (если не запущен)
if (-not $frontendRunning) {
    Write-Host "🎨 Запуск Frontend в отдельном окне..." -ForegroundColor Cyan
    $frontendCmd = "cd d:\bybit_strategy_tester_v2\frontend; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    Write-Host "   Ожидание запуска Frontend..." -ForegroundColor Gray
    Start-Sleep -Seconds 8
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  ✅ Система запущена!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "📚 Backend API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "📖 ReDoc: http://localhost:8000/redoc" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Открываю приложение в браузере..." -ForegroundColor Yellow

# Автоматически открыть в браузере
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "✅ Приложение открыто в системном браузере!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Для остановки закройте окна PowerShell с Backend и Frontend" -ForegroundColor Gray
Write-Host ""
