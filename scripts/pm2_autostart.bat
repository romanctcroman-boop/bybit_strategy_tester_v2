@echo off
REM PM2 Full Autostart Script
REM This script starts PM2 daemon and resurrects saved processes

REM Set PATH to include npm global binaries
set PATH=%PATH%;C:\Users\roman\AppData\Roaming\npm

REM Create logs directory if not exists
if not exist "D:\bybit_strategy_tester_v2\logs" mkdir "D:\bybit_strategy_tester_v2\logs"

REM Wait for system to stabilize
timeout /t 10 /nobreak >nul

REM Start PM2 daemon (if not running)
pm2 ping >nul 2>&1

REM Resurrect saved processes
pm2 resurrect >> D:\bybit_strategy_tester_v2\logs\pm2_autostart.log 2>&1

REM Log success
echo [%date% %time%] PM2 autostart completed >> D:\bybit_strategy_tester_v2\logs\pm2_autostart.log

exit
