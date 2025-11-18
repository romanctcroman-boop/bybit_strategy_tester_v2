@echo off
REM Final Production Report to DeepSeek - Auto-confirm script
cd /d "D:\bybit_strategy_tester_v2"
echo y | .venv\Scripts\python.exe send_final_production_report.py
pause
