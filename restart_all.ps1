# Full restart script - kills all python processes and starts fresh

Write-Host "🧹 Cleaning up..." -ForegroundColor Yellow
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "`n🚀 Starting Backend API..." -ForegroundColor Cyan
$apiJob = Start-Job -ScriptBlock {
    cd D:\bybit_strategy_tester_v2
    & D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m uvicorn backend.api.app:app --port 8000
}

Write-Host "⏳ Waiting for API to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

Write-Host "`n✅ API Job ID: $($apiJob.Id)" -ForegroundColor Green

Write-Host "`n🔍 Testing API endpoints..." -ForegroundColor Cyan
& D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe check_api.py

Write-Host "`n📊 To check API logs:" -ForegroundColor Cyan
Write-Host "  Receive-Job -Id $($apiJob.Id) -Keep" -ForegroundColor Gray

Write-Host "`n🛑 To stop API:" -ForegroundColor Cyan
Write-Host "  Stop-Job -Id $($apiJob.Id); Remove-Job -Id $($apiJob.Id)" -ForegroundColor Gray
