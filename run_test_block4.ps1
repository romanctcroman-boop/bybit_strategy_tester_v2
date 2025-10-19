# Скрипт для запуска теста Block 4: Backtest Engine
# Автоматически устанавливает PYTHONPATH и запускает тест

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "  🧪 RUNNING BLOCK 4 TEST: BACKTEST ENGINE" -ForegroundColor Yellow
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host ""

# Установка PYTHONPATH
$env:PYTHONPATH = "d:\bybit_strategy_tester_v2"

# Запуск теста
python backend\test_block4_backtest_engine.py

# Проверка результата
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Green
    Write-Host ("=" * 79) -ForegroundColor Green
    Write-Host "  ✅ BLOCK 4 TEST PASSED!" -ForegroundColor Green
    Write-Host ("=" * 80) -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Red
    Write-Host ("=" * 79) -ForegroundColor Red
    Write-Host "  ❌ BLOCK 4 TEST FAILED!" -ForegroundColor Red
    Write-Host ("=" * 80) -ForegroundColor Red
    exit 1
}
