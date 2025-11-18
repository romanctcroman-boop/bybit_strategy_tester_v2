@echo off
cd /d d:\bybit_strategy_tester_v2
py -m uvicorn backend.examples.minimal_test_app:app --host 127.0.0.1 --port 8002
pause
