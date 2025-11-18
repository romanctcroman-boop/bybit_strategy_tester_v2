#!/usr/bin/env pwsh
# Quick script to run all Phase 1 tests

Write-Host "🧪 Running Phase 1 Security Tests..." -ForegroundColor Cyan
Write-Host ""

# Set PYTHONPATH
$env:PYTHONPATH = "D:\bybit_strategy_tester_v2"

# Backend Tests
Write-Host "📦 Backend Tests (JWT + Rate Limiting)..." -ForegroundColor Yellow
D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m pytest tests/test_phase1_security.py::TestJWTAuthentication tests/test_phase1_security.py::TestRateLimiting -v

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Backend tests PASSED" -ForegroundColor Green
}
else {
    Write-Host "❌ Backend tests FAILED" -ForegroundColor Red
}

Write-Host ""

# Frontend Tests
Write-Host "🎨 Frontend Unit Tests..." -ForegroundColor Yellow
Set-Location -Path "D:\bybit_strategy_tester_v2\frontend"
npm test -- --run

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Frontend tests PASSED" -ForegroundColor Green
}
else {
    Write-Host "❌ Frontend tests FAILED" -ForegroundColor Red
}

Write-Host ""
Write-Host "🎯 Test run complete! Check TEST_RESULTS_PHASE1.md for details." -ForegroundColor Cyan
