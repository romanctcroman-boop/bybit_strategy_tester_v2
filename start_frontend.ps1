# Запуск Frontend в системном браузере
# Этот скрипт автоматически открывает приложение в вашем браузере по умолчанию

Write-Host "🚀 Запуск Bybit Strategy Tester v2.0 Frontend..." -ForegroundColor Cyan
Write-Host ""

# Переход в директорию frontend
Set-Location "d:\bybit_strategy_tester_v2\frontend"

# Проверка, не занят ли порт 5173
$port = 5173
$connection = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue

if ($connection.TcpTestSucceeded) {
    Write-Host "⚠️  Порт $port уже занят. Открываю существующее приложение в браузере..." -ForegroundColor Yellow
    Start-Process "http://localhost:5173"
    Write-Host "✅ Браузер открыт!" -ForegroundColor Green
}
else {
    Write-Host "📦 Запуск Vite dev server..." -ForegroundColor Cyan
    Write-Host "   (Браузер откроется автоматически)" -ForegroundColor Gray
    Write-Host ""
    
    # Запуск npm dev (Vite автоматически откроет браузер благодаря open: true)
    npm run dev
}
