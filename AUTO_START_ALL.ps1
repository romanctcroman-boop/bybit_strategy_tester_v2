# ====================================================================
# ПОЛНЫЙ АВТОЗАПУСК AGENT-TO-AGENT СИСТЕМЫ
# ====================================================================

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " AGENT-TO-AGENT COMMUNICATION SYSTEM - AUTO START" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Остановить все Python процессы
Write-Host "[1/4] Stopping all Python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "      Done" -ForegroundColor Green

# 2. Запустить Backend в отдельном окне
Write-Host "[2/4] Starting Backend in separate terminal..." -ForegroundColor Yellow
$projectPath = "D:\bybit_strategy_tester_v2"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectPath'; Write-Host 'Agent-to-Agent Backend Server' -ForegroundColor Cyan; py run_backend.py"
Write-Host "      Backend starting..." -ForegroundColor Green

# 3. Подождать запуска
Write-Host "[3/4] Waiting for backend to initialize (15 seconds)..." -ForegroundColor Yellow
for ($i = 15; $i -gt 0; $i--) {
    Write-Host "      $i seconds remaining..." -NoNewline
    Start-Sleep -Seconds 1
    Write-Host "`r" -NoNewline
}
Write-Host "      Ready!                          " -ForegroundColor Green

# 4. Запустить диагностику
Write-Host "[4/4] Running diagnostics..." -ForegroundColor Yellow
Write-Host ""
py diagnose_backend.py

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " NEXT STEPS:" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Backend is running in separate terminal window" -ForegroundColor White
Write-Host "  2. Test WebSocket:  py test_websocket_quick.py" -ForegroundColor Yellow
Write-Host "  3. Open Extension:  cd vscode-extension; code ." -ForegroundColor Yellow
Write-Host "  4. Press F5 in VS Code to launch Extension Development Host" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
