# ============================================================================
# Full Testing Script - Manual API Tests
# ============================================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  MANUAL API TESTING SCRIPT" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$BASE_URL = "http://localhost:8000"

# ----------------------------------------------------------------------------
# Test 1: Health Check
# ----------------------------------------------------------------------------
Write-Host "[Test 1] Health Check Endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/api/health" -Method Get
    Write-Host "✓ PASS: Health check successful" -ForegroundColor Green
    Write-Host "  Status: $($response.status)" -ForegroundColor Gray
    Write-Host "  Message: $($response.message)`n" -ForegroundColor Gray
} catch {
    Write-Host "✗ FAIL: Health check failed" -ForegroundColor Red
    Write-Host "  Error: $_`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Test 2: Data Loader Singleton (GET /api/data/)
# ----------------------------------------------------------------------------
Write-Host "[Test 2] Data Loader Singleton..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/api/data/" -Method Get
    Write-Host "✓ PASS: Data endpoint accessible" -ForegroundColor Green
    Write-Host "  Response: $($response.message)`n" -ForegroundColor Gray
} catch {
    Write-Host "✗ FAIL: Data endpoint failed" -ForegroundColor Red
    Write-Host "  Error: $_`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Test 3: Load Sample Data (with real API call)
# ----------------------------------------------------------------------------
Write-Host "[Test 3] Load Market Data (Bybit API)..." -ForegroundColor Yellow
try {
    $body = @{
        symbol = "BTCUSDT"
        interval = "15"
        start_date = "2025-10-15"
        end_date = "2025-10-16"
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "$BASE_URL/api/data/load" `
        -Method Post `
        -Body $body `
        -ContentType "application/json"
    
    Write-Host "✓ PASS: Data loaded successfully" -ForegroundColor Green
    Write-Host "  Candles loaded: $($response.candles_count)" -ForegroundColor Gray
    Write-Host "  Symbol: $($response.metadata.symbol)" -ForegroundColor Gray
    Write-Host "  Interval: $($response.metadata.interval)`n" -ForegroundColor Gray
} catch {
    Write-Host "✗ FAIL: Data loading failed" -ForegroundColor Red
    Write-Host "  Error: $_`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Test 4: Run Simple Backtest
# ----------------------------------------------------------------------------
Write-Host "[Test 4] Run Simple Backtest..." -ForegroundColor Yellow
try {
    $body = @{
        symbol = "BTCUSDT"
        interval = "15"
        start_date = "2025-10-15"
        end_date = "2025-10-16"
        strategy_name = "RSI Mean Reversion"
        strategy_type = "indicator"
        initial_capital = 10000
        position_size_pct = 10
        maker_fee = 0.02
        taker_fee = 0.055
        strategy_params = @{
            rsi_period = 14
            rsi_oversold = 30
            rsi_overbought = 70
        }
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "$BASE_URL/api/v1/backtest/run-simple" `
        -Method Post `
        -Body $body `
        -ContentType "application/json"
    
    Write-Host "✓ PASS: Backtest completed successfully" -ForegroundColor Green
    Write-Host "  Final Capital: `$$($response.final_capital)" -ForegroundColor Gray
    Write-Host "  Total Trades: $($response.result.total_trades)" -ForegroundColor Gray
    Write-Host "  Win Rate: $([math]::Round($response.result.win_rate * 100, 2))%" -ForegroundColor Gray
    Write-Host "  Sharpe Ratio: $([math]::Round($response.result.sharpe_ratio, 3))`n" -ForegroundColor Gray
} catch {
    Write-Host "✗ FAIL: Backtest failed" -ForegroundColor Red
    Write-Host "  Error: $_`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Test 5: Structured Logging (Check logs file)
# ----------------------------------------------------------------------------
Write-Host "[Test 5] Structured Logging..." -ForegroundColor Yellow
$today = Get-Date -Format "yyyy-MM-dd"
$logFile = "logs\api_$today.log"

if (Test-Path $logFile) {
    $lastLogs = Get-Content $logFile -Tail 5
    Write-Host "✓ PASS: Structured logging working" -ForegroundColor Green
    Write-Host "  Log file: $logFile" -ForegroundColor Gray
    Write-Host "  Last 5 log entries:" -ForegroundColor Gray
    $lastLogs | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Host ""
} else {
    Write-Host "✗ FAIL: Log file not found" -ForegroundColor Red
    Write-Host "  Expected: $logFile`n" -ForegroundColor Red
}

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TESTING COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review test results above" -ForegroundColor Gray
Write-Host "  2. Check logs in logs/api_$today.log" -ForegroundColor Gray
Write-Host "  3. Open http://localhost:8000/docs for Swagger UI`n" -ForegroundColor Gray
