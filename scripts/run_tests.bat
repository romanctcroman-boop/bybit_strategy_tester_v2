@echo off
echo ================================================================================
echo   RUNNING SECURITY COMPONENT TESTS
echo ================================================================================
echo.
echo Make sure the server is running in another window!
echo Server URL: http://127.0.0.1:8000
echo.
echo Tests will start in 3 seconds...
echo.
timeout /t 3 /nobreak >nul

cd /d "%~dp0..\.."
py backend\examples\manual_test.py

echo.
echo ================================================================================
echo   TESTS COMPLETE
echo ================================================================================
echo.
pause
