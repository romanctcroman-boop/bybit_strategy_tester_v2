# DeepSeek MCP Server Monitor
# Отслеживает прогресс работы DeepSeek MCP Server

$StateFile = "D:\bybit_strategy_tester_v2\deepseek_server_state.json"
$LogFile = "D:\bybit_strategy_tester_v2\deepseek_mcp_server.log"
$ResultsFile = "D:\bybit_strategy_tester_v2\DEEPSEEK_PROJECT_ANALYSIS.json"

Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  📊 DEEPSEEK MCP SERVER MONITOR                          ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

# Check if server is running
$serverProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*deepseek_mcp_server.py*"
}

if (-not $serverProcess) {
    Write-Host "❌ DeepSeek MCP Server is not running" -ForegroundColor Red
    Write-Host "`nStart with: .\start_deepseek_server.ps1`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Server Status: RUNNING" -ForegroundColor Green
Write-Host "   PID: $($serverProcess.Id)" -ForegroundColor Cyan
Write-Host "   CPU: $([math]::Round($serverProcess.CPU, 2))s" -ForegroundColor Cyan
Write-Host "   Memory: $([math]::Round($serverProcess.WorkingSet64 / 1MB, 1)) MB`n" -ForegroundColor Cyan

# Read state
if (Test-Path $StateFile) {
    Write-Host "📂 Server State:" -ForegroundColor Yellow
    $state = Get-Content $StateFile | ConvertFrom-Json
    
    Write-Host "   Status: $($state.status)" -ForegroundColor $(
        if ($state.status -eq "completed") { "Green" }
        elseif ($state.status -like "*running*") { "Cyan" }
        else { "Yellow" }
    )
    Write-Host "   Session: $($state.session_id)" -ForegroundColor Gray
    Write-Host "   Started: $($state.started_at)" -ForegroundColor Gray
    
    if ($state.updated_at) {
        Write-Host "   Updated: $($state.updated_at)" -ForegroundColor Gray
    }
    
    Write-Host "`n   Progress: $($state.files_completed)/$($state.total_files) files" -ForegroundColor Cyan
    
    if ($state.current_file) {
        Write-Host "   Current: $($state.current_file)" -ForegroundColor Yellow
    }
    
    if ($state.completed_files.Count -gt 0) {
        Write-Host "`n   ✅ Completed Files:" -ForegroundColor Green
        $state.completed_files | ForEach-Object {
            Write-Host "      • $_" -ForegroundColor Gray
        }
    }
    
    if ($state.failed_files.Count -gt 0) {
        Write-Host "`n   ❌ Failed Files:" -ForegroundColor Red
        $state.failed_files | ForEach-Object {
            Write-Host "      • $_" -ForegroundColor Gray
        }
    }
    
    # Progress bar
    if ($state.total_files -gt 0) {
        $percent = [math]::Round(($state.files_completed / $state.total_files) * 100)
        $barLength = 40
        $filled = [math]::Round(($percent / 100) * $barLength)
        $empty = $barLength - $filled
        
        Write-Host "`n   Progress Bar:" -ForegroundColor Cyan
        Write-Host "   [" -NoNewline -ForegroundColor Gray
        Write-Host ("█" * $filled) -NoNewline -ForegroundColor Green
        Write-Host ("░" * $empty) -NoNewline -ForegroundColor DarkGray
        Write-Host "] $percent%" -ForegroundColor Gray
    }
    
}
else {
    Write-Host "⏳ State file not found. Server initializing..." -ForegroundColor Yellow
}

# Check results
Write-Host "`n📄 Results:" -ForegroundColor Yellow
if (Test-Path $ResultsFile) {
    $results = Get-Content $ResultsFile | ConvertFrom-Json
    Write-Host "   File: DEEPSEEK_PROJECT_ANALYSIS.json" -ForegroundColor Green
    Write-Host "   Size: $([math]::Round((Get-Item $ResultsFile).Length / 1KB, 1)) KB" -ForegroundColor Cyan
    Write-Host "   Files analyzed: $($results.total_files)" -ForegroundColor Cyan
    Write-Host "   Successful: $($results.successful)" -ForegroundColor Green
    Write-Host "   Failed: $($results.failed)" -ForegroundColor $(if ($results.failed -gt 0) { "Red" } else { "Gray" })
}
else {
    Write-Host "   No results yet..." -ForegroundColor Gray
}

# Recent log entries
Write-Host "`n📝 Recent Log (last 15 lines):" -ForegroundColor Yellow
if (Test-Path $LogFile) {
    Get-Content $LogFile -Tail 15 | ForEach-Object {
        # Color code based on log level
        if ($_ -like "*ERROR*") {
            Write-Host "   $_" -ForegroundColor Red
        }
        elseif ($_ -like "*WARNING*") {
            Write-Host "   $_" -ForegroundColor Yellow
        }
        elseif ($_ -like "*✅*" -or $_ -like "*complete*") {
            Write-Host "   $_" -ForegroundColor Green
        }
        elseif ($_ -like "*🔍*" -or $_ -like "*Analyzing*") {
            Write-Host "   $_" -ForegroundColor Cyan
        }
        else {
            Write-Host "   $_" -ForegroundColor Gray
        }
    }
}
else {
    Write-Host "   Log file not found" -ForegroundColor Gray
}

Write-Host "`n💡 Refresh this view:" -ForegroundColor Yellow
Write-Host "   .\monitor_deepseek_server.ps1`n" -ForegroundColor Gray

Write-Host "💡 Live log tail:" -ForegroundColor Yellow
Write-Host "   Get-Content '$LogFile' -Tail 50 -Wait`n" -ForegroundColor Gray
