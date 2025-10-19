@echo off
REM =============================================================================
REM Bybit Strategy Tester - Complete Start Script
REM =============================================================================
REM 
REM Starts:
REM   1. Backend API (port 8000)
REM   2. Frontend HTTP Server (port 8080)
REM   3. Opens browser windows
REM
REM =============================================================================

echo.
echo ================================================================================
echo   BYBIT STRATEGY TESTER - STARTING ALL SERVICES
echo ================================================================================
echo.

REM Start Backend API in new window
echo [1/3] Starting Backend API...
start "Backend API - Port 8000" cmd /k "cd /d D:\bybit_strategy_tester_v2 && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul

REM Start Frontend HTTP Server in new window  
echo [2/3] Starting Frontend Server...
start "Frontend Server - Port 8080" cmd /k "cd /d D:\bybit_strategy_tester_v2\frontend && python -m http.server 8080"
timeout /t 3 /nobreak >nul

REM Open browser windows
echo [3/3] Opening browser windows...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8080/demo.html"
timeout /t 1 /nobreak >nul
start "" "http://localhost:8000/docs"

echo.
echo ================================================================================
echo   ALL SERVICES STARTED!
echo ================================================================================
echo.
echo   Backend API:       http://localhost:8000
echo   API Docs:          http://localhost:8000/docs
echo   Demo UI:           http://localhost:8080/demo.html
echo   Test Page:         http://localhost:8080/test.html
echo.
echo   To stop: Close the terminal windows
echo.
echo ================================================================================
echo.
pause
