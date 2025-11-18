# DeepSeek MCP Server Launcher
# Запускает DeepSeek MCP Server как фоновый процесс Windows

$ErrorActionPreference = "Stop"

$PythonExe = "C:\Users\roman\AppData\Local\Programs\Python\Python314\python.exe"
$ServerScript = "D:\bybit_strategy_tester_v2\mcp-server\deepseek_mcp_server.py"
$LogFile = "D:\bybit_strategy_tester_v2\deepseek_mcp_server.log"
$StateFile = "D:\bybit_strategy_tester_v2\deepseek_server_state.json"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  DEEPSEEK MCP SERVER LAUNCHER" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if server already running
$existingProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*deepseek_mcp_server.py*"
}

if ($existingProcess) {
    Write-Host "WARNING: DeepSeek MCP Server already running" -ForegroundColor Yellow
    Write-Host "PID: $($existingProcess.Id)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To stop: Stop-Process -Id $($existingProcess.Id)" -ForegroundColor White
    Write-Host ""
    exit 0
}

# Clean old state if needed
if (Test-Path $StateFile) {
    $state = Get-Content $StateFile | ConvertFrom-Json
    if ($state.status -eq "completed") {
        Write-Host "Previous analysis completed. Starting fresh..." -ForegroundColor Green
        Remove-Item $StateFile -Force
    }
    elseif ($state.status -eq "interrupted") {
        Write-Host "Previous analysis interrupted. Resuming..." -ForegroundColor Yellow
    }
}

Write-Host "Starting DeepSeek MCP Server..." -ForegroundColor Green
Write-Host "Python: $PythonExe" -ForegroundColor Gray
Write-Host "Script: $ServerScript" -ForegroundColor Gray
Write-Host "Log: $LogFile" -ForegroundColor Gray
Write-Host ""

# Start as background job
$job = Start-Job -ScriptBlock {
    param($python, $script)
    & $python $script
} -ArgumentList $PythonExe, $ServerScript

Write-Host "SUCCESS: DeepSeek MCP Server started!" -ForegroundColor Green
Write-Host "Job ID: $($job.Id)" -ForegroundColor Cyan
Write-Host "Job Name: $($job.Name)" -ForegroundColor Cyan
Write-Host ""

Write-Host "Monitoring Commands:" -ForegroundColor Yellow
Write-Host ""
Write-Host "View logs (live):" -ForegroundColor White
Write-Host "  Get-Content '$LogFile' -Tail 50 -Wait" -ForegroundColor Gray
Write-Host ""

Write-Host "Check state:" -ForegroundColor White
Write-Host "  Get-Content '$StateFile' | ConvertFrom-Json | Format-List" -ForegroundColor Gray
Write-Host ""

Write-Host "Check job status:" -ForegroundColor White
Write-Host "  Get-Job -Id $($job.Id)" -ForegroundColor Gray
Write-Host ""

Write-Host "Stop server:" -ForegroundColor White
Write-Host "  Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)" -ForegroundColor Gray
Write-Host ""

Write-Host "Get results:" -ForegroundColor White
$ResultPath = "D:\bybit_strategy_tester_v2\DEEPSEEK_PROJECT_ANALYSIS.json"
Write-Host "  Get-Content '$ResultPath' | ConvertFrom-Json" -ForegroundColor Gray
Write-Host ""

# Wait a moment and show initial output
Start-Sleep -Seconds 2

Write-Host "Initial log output:" -ForegroundColor Cyan
if (Test-Path $LogFile) {
    Get-Content $LogFile -Tail 20 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "SUCCESS: Server is running in background!" -ForegroundColor Green
Write-Host "Use monitoring commands above to track progress." -ForegroundColor Yellow
Write-Host ""
