# Staging Week 1 Monitoring Scheduler
# Автоматические проверки Quick Wins в staging

param(
    [int]$DurationHours = 24,
    [int]$CheckIntervalMinutes = 60
)

Write-Host @"

╔══════════════════════════════════════════════════════════╗
║   STAGING WEEK 1 - AUTOMATIC MONITORING SCHEDULER       ║
║   Quick Wins #1-4 - Hour-by-Hour Checks                 ║
╚══════════════════════════════════════════════════════════╝

Configuration:
  Duration: $DurationHours hours
  Check Interval: $CheckIntervalMinutes minutes
  Start Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

"@ -ForegroundColor Cyan

$startTime = Get-Date
$endTime = $startTime.AddHours($DurationHours)
$checkCount = 0

# Create reports directory if not exists
$reportsDir = "logs\staging_checks"
if (-not (Test-Path $reportsDir)) {
    New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
    Write-Host "✅ Created reports directory: $reportsDir`n" -ForegroundColor Green
}

function Invoke-MonitoringCheck {
    param([int]$CheckNumber)
    
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $reportFile = "$reportsDir\check_$timestamp.txt"
    
    Write-Host "`n" + ("=" * 60) -ForegroundColor Yellow
    Write-Host "CHECK #$CheckNumber - $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Yellow
    
    # Run monitoring script
    $output = py monitor_staging_quick_wins.py 2>&1
    
    # Save to file
    $output | Out-File -FilePath $reportFile -Encoding UTF8
    
    # Parse results
    $success = $output -match "All Quick Wins operational"
    $budgetValue = if ($output -match "TOOL_CALL_BUDGET = (\d+)") { $Matches[1] } else { "?" }
    $deepseekKeys = if ($output -match "DeepSeek Keys: (\d+)/(\d+)") { "$($Matches[1])/$($Matches[2])" } else { "?" }
    $perplexityKeys = if ($output -match "Perplexity Keys: (\d+)/(\d+)") { "$($Matches[1])/$($Matches[2])" } else { "?" }
    
    # Display summary
    Write-Host "`n📊 QUICK SUMMARY:" -ForegroundColor White
    Write-Host "   Status: $(if ($success) { '✅ OPERATIONAL' } else { '⚠️ ISSUES DETECTED' })" -ForegroundColor $(if ($success) { 'Green' } else { 'Yellow' })
    Write-Host "   Budget: $budgetValue tool calls" -ForegroundColor Gray
    Write-Host "   DeepSeek: $deepseekKeys keys active" -ForegroundColor Gray
    Write-Host "   Perplexity: $perplexityKeys keys active" -ForegroundColor Gray
    Write-Host "   Report: $reportFile" -ForegroundColor Gray
    
    return $success
}

# Main monitoring loop
Write-Host "🚀 Starting automatic monitoring...`n" -ForegroundColor Green

try {
    while ((Get-Date) -lt $endTime) {
        $checkCount++
        
        $checkSuccess = Invoke-MonitoringCheck -CheckNumber $checkCount
        
        if (-not $checkSuccess) {
            Write-Host "`n⚠️ WARNING: Issues detected in Check #$checkCount" -ForegroundColor Yellow
            Write-Host "   Review report file for details" -ForegroundColor Yellow
            
            # Optional: Send alert (email, Slack, etc.)
            # Send-Alert "Staging monitoring detected issues in Check #$checkCount"
        }
        
        # Calculate next check time
        $nextCheck = (Get-Date).AddMinutes($CheckIntervalMinutes)
        
        if ($nextCheck -lt $endTime) {
            $waitMinutes = ($nextCheck - (Get-Date)).TotalMinutes
            Write-Host "`n⏱️  Next check in $([math]::Round($waitMinutes, 1)) minutes (at $($nextCheck.ToString('HH:mm:ss')))" -ForegroundColor Cyan
            Write-Host "   Press Ctrl+C to stop monitoring`n" -ForegroundColor Gray
            
            Start-Sleep -Seconds ($CheckIntervalMinutes * 60)
        }
        else {
            break
        }
    }
    
    # Final summary
    Write-Host "`n" + ("=" * 60) -ForegroundColor Green
    Write-Host "MONITORING COMPLETE" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host "Total Checks: $checkCount" -ForegroundColor White
    Write-Host "Duration: $([math]::Round(((Get-Date) - $startTime).TotalHours, 2)) hours" -ForegroundColor White
    Write-Host "Reports: $reportsDir\check_*.txt" -ForegroundColor White
    Write-Host "`n✅ Monitoring session completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "`n❌ ERROR: Monitoring failed" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    exit 1
}
