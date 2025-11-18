# DeepSeek Auto-Refactor Launcher
# Launches autonomous refactoring process

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  DEEPSEEK AUTO-REFACTOR LAUNCHER" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = "D:\bybit_strategy_tester_v2"
$PythonExe = "C:\Users\roman\AppData\Local\Programs\Python\Python314\python.exe"
$ScriptPath = "$ProjectRoot\mcp-server\deepseek_auto_refactor.py"
$StateFile = "$ProjectRoot\deepseek_refactor_state.json"
$LogFile = "$ProjectRoot\deepseek_auto_refactor.log"

# Verify Python
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python not found at $PythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "Python: $PythonExe" -ForegroundColor Green

# Verify script
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Script: $ScriptPath" -ForegroundColor Green
Write-Host ""

# Clean old state
if (Test-Path $StateFile) {
    Remove-Item $StateFile -Force
    Write-Host "Old state cleaned" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  LAUNCHING AUTO-REFACTOR" -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "MODE: FULL_AUTO" -ForegroundColor Yellow
Write-Host "  - Analyze code" -ForegroundColor Gray
Write-Host "  - Generate refactoring" -ForegroundColor Gray
Write-Host "  - APPLY CHANGES automatically" -ForegroundColor Yellow
Write-Host "  - Create backups" -ForegroundColor Gray
Write-Host ""

# Start as background job
$job = Start-Job -ScriptBlock {
    param($python, $script)
    Set-Location "D:\bybit_strategy_tester_v2"
    & $python $script 2>&1
} -ArgumentList $PythonExe, $ScriptPath -Name "DeepSeekAutoRefactor"

Write-Host "SUCCESS: Auto-Refactor launched!" -ForegroundColor Green
Write-Host "Job ID: $($job.Id)" -ForegroundColor Cyan
Write-Host "Job Name: $($job.Name)" -ForegroundColor Cyan
Write-Host ""

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  MONITORING COMMANDS" -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Check state:" -ForegroundColor Yellow
Write-Host "  Get-Content '$StateFile' | ConvertFrom-Json | Format-List" -ForegroundColor Gray
Write-Host ""

Write-Host "Watch logs:" -ForegroundColor Yellow
Write-Host "  Get-Content '$LogFile' -Wait -Tail 20" -ForegroundColor Gray
Write-Host ""

Write-Host "Check job:" -ForegroundColor Yellow
Write-Host "  Get-Job -Id $($job.Id)" -ForegroundColor Gray
Write-Host "  Receive-Job -Id $($job.Id) -Keep" -ForegroundColor Gray
Write-Host ""

Write-Host "Stop job:" -ForegroundColor Yellow
Write-Host "  Stop-Job -Id $($job.Id)" -ForegroundColor Gray
Write-Host ""

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  Waiting for initialization..." -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 8

# Check initial status
if (Test-Path $StateFile) {
    Write-Host "INITIAL STATUS:" -ForegroundColor Green
    Write-Host ""
    $state = Get-Content $StateFile | ConvertFrom-Json
    Write-Host "  Session: $($state.session_id)" -ForegroundColor Cyan
    Write-Host "  Mode: $($state.mode)" -ForegroundColor Cyan
    Write-Host "  Status: $($state.status)" -ForegroundColor Yellow
    Write-Host "  Files: $($state.files_processed)/$($state.total_files)" -ForegroundColor Cyan
    if ($state.current_file) {
        Write-Host "  Current: $($state.current_file)" -ForegroundColor Gray
    }
    Write-Host ""
}
else {
    Write-Host "State file not created yet (still initializing)..." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Monitor progress: .\monitor_auto_refactor.ps1" -ForegroundColor Green
Write-Host ""
