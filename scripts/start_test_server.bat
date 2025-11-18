@echo off
echo ================================================================================
echo   STARTING SECURITY TEST API SERVER
echo ================================================================================
echo.
echo Server will start on http://127.0.0.1:8000
echo.
echo Press Ctrl+C to stop
echo.
echo ================================================================================
echo.

cd /d "%~dp0..\.."
py backend\examples\simple_api_test.py

pause
