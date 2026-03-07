@echo off
d:\bybit_strategy_tester_v2\.venv\Scripts\python.exe d:\bybit_strategy_tester_v2\temp_analysis\run_backtest.py > d:\bybit_strategy_tester_v2\temp_analysis\backtest_result.txt 2>&1
echo Done. Exit code: %ERRORLEVEL%
