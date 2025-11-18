# DeepSeek Full Analysis Runner - PowerShell Background
# Runs DeepSeek analysis as background job that survives terminal close

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " DeepSeek MCP Analysis - Background Job" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$pythonPath = "C:\Users\roman\AppData\Local\Programs\Python\Python314\python.exe"
$scriptPath = "D:\bybit_strategy_tester_v2\mcp-server\deepseek_full_analysis.py"
$workingDir = "D:\bybit_strategy_tester_v2"

Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "   Python: $pythonPath"
Write-Host "   Script: $scriptPath"
Write-Host "   Working Dir: $workingDir`n"

# Start as PowerShell background job
Write-Host "🚀 Starting DeepSeek analysis as background job..." -ForegroundColor Green

$job = Start-Job -ScriptBlock {
    param($python, $script, $dir)
    Set-Location $dir
    & $python $script 2>&1 | Tee-Object -FilePath "deepseek_output.log"
} -ArgumentList $pythonPath, $scriptPath, $workingDir

Write-Host "✅ Background job started!" -ForegroundColor Green
Write-Host "   Job ID: $($job.Id)" -ForegroundColor Cyan
Write-Host "   Job Name: $($job.Name)" -ForegroundColor Cyan

Write-Host "`n📊 Monitoring:" -ForegroundColor Yellow
Write-Host "   Progress: $workingDir\DEEPSEEK_ANALYSIS_PROGRESS.json"
Write-Host "   Log: $workingDir\deepseek_mcp_analysis.log"
Write-Host "   Output: $workingDir\deepseek_output.log"

Write-Host "`n💡 Commands:" -ForegroundColor Cyan
Write-Host "   Check status: Get-Job $($job.Id)"
Write-Host "   View output: Receive-Job $($job.Id) -Keep"
Write-Host "   Wait for completion: Wait-Job $($job.Id)"
Write-Host "   Get results: Receive-Job $($job.Id)"

Write-Host "`n⏳ You can close this window - job will continue running!" -ForegroundColor Green
Write-Host "   Analysis will complete in background.`n"

# Optional: Wait for a few seconds to see initial output
Write-Host "Waiting 5 seconds to capture initial output..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Show initial output
$initialOutput = Receive-Job $job -Keep
if ($initialOutput) {
    Write-Host "`n📝 Initial output:" -ForegroundColor Cyan
    $initialOutput | Select-Object -First 10 | ForEach-Object { Write-Host "   $_" }
}

Write-Host "`n✅ Job is running in background!" -ForegroundColor Green
Write-Host "   You can now safely close this terminal." -ForegroundColor Green
Write-Host ""
