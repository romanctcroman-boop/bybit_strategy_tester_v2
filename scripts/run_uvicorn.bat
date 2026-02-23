@echo off
:: Run uvicorn with stdout/stderr redirected to log files
:: Called by start_uvicorn.ps1
::
:: Args: %1=python_exe %2=project_root %3=stdout_log %4=stderr_log

cd /d "%2"
"%1" -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --log-level info >> "%3" 2>> "%4"
