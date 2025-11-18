@echo off
REM Quick Start Script for Bybit Strategy Tester

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     Bybit Strategy Tester v2 - Quick Start                    ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo [1] Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не установлен! Установите Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python найден

echo [2] Проверка Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js не установлен! Установите Node.js 16+
    pause
    exit /b 1
)
echo ✅ Node.js найден

echo.
echo [3] Запуск Backend...
echo    URL: http://127.0.0.1:8000
start /MIN cmd /c "cd %CD% && python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000"
timeout /T 3 /NOBREAK

echo.
echo [4] Запуск Frontend...
echo    URL: http://localhost:5173
start /MIN cmd /c "cd %CD%\frontend && npm run dev"
timeout /T 3 /NOBREAK

echo.
echo ✅ Оба сервера запущены!
echo.
echo 📝 Инструкции:
echo    1. Откройте браузер: http://localhost:5173
echo    2. Перейдите на страницу: http://localhost:5173/#/test-chart
echo    3. Вы должны увидеть график с реальными свечами BTCUSDT
echo.
echo 🔗 Ссылки:
echo    App:     http://localhost:5173
echo    Backend: http://127.0.0.1:8000
echo    Health:  http://127.0.0.1:8000/health
echo    API:     http://127.0.0.1:8000/api/v1/marketdata/bybit/klines/fetch
echo.
echo ⚠️  Окна консоли минимизированы. Не закрывайте их!
echo.
pause
