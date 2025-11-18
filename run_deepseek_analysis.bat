@echo off
REM DeepSeek Full Analysis Runner - Background execution
REM This script runs DeepSeek analysis in background without terminal interruption

echo.
echo ========================================
echo  DeepSeek MCP Analysis - Background Mode
echo ========================================
echo.
echo Starting DeepSeek analysis in background...
echo This will run until completion without interruption.
echo.
echo Progress will be saved to:
echo   - DEEPSEEK_ANALYSIS_PROGRESS.json
echo   - deepseek_mcp_analysis.log
echo.
echo You can close this window - analysis will continue!
echo.

cd /d D:\bybit_strategy_tester_v2

REM Run in background with START command - detached from terminal
START /B "" C:\Users\roman\AppData\Local\Programs\Python\Python314\python.exe mcp-server\deepseek_full_analysis.py > deepseek_output.log 2>&1

echo.
echo ✅ Analysis started in background!
echo.
echo To monitor progress:
echo   1. Check: DEEPSEEK_ANALYSIS_PROGRESS.json
echo   2. Check: deepseek_mcp_analysis.log
echo   3. Check: deepseek_output.log
echo.
echo Press any key to close this window (analysis will continue)...
pause >nul
