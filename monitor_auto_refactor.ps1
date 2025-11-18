# DeepSeek Auto-Refactor Monitor
# Live progress monitoring

$StateFile = "D:\bybit_strategy_tester_v2\deepseek_refactor_state.json"
$LogFile = "D:\bybit_strategy_tester_v2\deepseek_auto_refactor.log"
$RefreshInterval = 3

Clear-Host

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  DEEPSEEK AUTO-REFACTOR MONITOR" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "State file: $StateFile" -ForegroundColor Gray
Write-Host "Log file: $LogFile" -ForegroundColor Gray
Write-Host "Refresh: Every $RefreshInterval seconds" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Yellow
Write-Host ""

$lastStatus = ""
$lastFilesProcessed = -1
$startTime = Get-Date

while ($true) {
    Clear-Host
    
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "  DEEPSEEK AUTO-REFACTOR - LIVE PROGRESS" -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    $currentTime = Get-Date
    $elapsed = $currentTime - $startTime
    $elapsedStr = "{0:hh\:mm\:ss}" -f $elapsed
    Write-Host "Monitoring time: $elapsedStr" -ForegroundColor Gray
    Write-Host ""
    
    if (Test-Path $StateFile) {
        try {
            $state = Get-Content $StateFile -Raw | ConvertFrom-Json
            
            $lastStatus = $state.status
            $lastFilesProcessed = $state.files_processed
            
            Write-Host "SESSION INFO:" -ForegroundColor Yellow
            Write-Host "  Session ID: $($state.session_id)" -ForegroundColor Cyan
            Write-Host "  Mode: $($state.mode)" -ForegroundColor Cyan
            Write-Host "  Started: $($state.started_at)" -ForegroundColor Gray
            Write-Host "  Updated: $($state.updated_at)" -ForegroundColor Gray
            Write-Host ""
            
            Write-Host "PROGRESS:" -ForegroundColor Yellow
            
            $progressPercent = 0
            if ($state.total_files -gt 0) {
                $progressPercent = [math]::Round(($state.files_processed / $state.total_files) * 100)
            }
            
            $progressBar = ""
            $progressWidth = 30
            $filledWidth = [math]::Round($progressWidth * $progressPercent / 100)
            for ($i = 0; $i -lt $progressWidth; $i++) {
                if ($i -lt $filledWidth) {
                    $progressBar += "█"
                }
                else {
                    $progressBar += "░"
                }
            }
            
            Write-Host "  Status: $($state.status)" -ForegroundColor $(
                if ($state.status -eq "completed") { "Green" }
                elseif ($state.status -like "error*") { "Red" }
                else { "Yellow" }
            )
            Write-Host "  Progress: [$progressBar] $progressPercent%" -ForegroundColor Cyan
            Write-Host "  Files: $($state.files_processed)/$($state.total_files)" -ForegroundColor Cyan
            Write-Host ""
            
            if ($state.current_file) {
                Write-Host "CURRENT FILE:" -ForegroundColor Yellow
                Write-Host "  $($state.current_file)" -ForegroundColor White
                Write-Host ""
            }
            
            if ($state.completed_files -and $state.completed_files.Count -gt 0) {
                Write-Host "COMPLETED FILES:" -ForegroundColor Green
                foreach ($file in $state.completed_files.PSObject.Properties) {
                    Write-Host "  ✓ $($file.Name)" -ForegroundColor Green
                }
                Write-Host ""
            }
            
            if ($state.failed_files -and $state.failed_files.Count -gt 0) {
                Write-Host "FAILED FILES:" -ForegroundColor Red
                foreach ($file in $state.failed_files.PSObject.Properties) {
                    Write-Host "  ✗ $($file.Name)" -ForegroundColor Red
                    Write-Host "    Error: $($file.Value)" -ForegroundColor Gray
                }
                Write-Host ""
            }
            
            if ($state.modifications_applied) {
                Write-Host "MODIFICATIONS APPLIED:" -ForegroundColor Yellow
                foreach ($mod in $state.modifications_applied) {
                    Write-Host "  • $($mod.file)" -ForegroundColor Cyan
                    Write-Host "    Backup: $($mod.backup)" -ForegroundColor Gray
                    Write-Host "    Time: $($mod.timestamp)" -ForegroundColor Gray
                }
                Write-Host ""
            }
            
            if ($state.status -eq "completed") {
                Write-Host "========================================================================" -ForegroundColor Green
                Write-Host "  REFACTORING COMPLETED!" -ForegroundColor Green
                Write-Host "========================================================================" -ForegroundColor Green
                Write-Host ""
                
                $job = Get-Job -Name "DeepSeekAutoRefactor" -ErrorAction SilentlyContinue
                if ($job) {
                    Write-Host "Job Status: $($job.State)" -ForegroundColor Cyan
                    Write-Host ""
                    
                    if ($job.State -eq "Completed") {
                        Write-Host "Cleanup command:" -ForegroundColor Yellow
                        Write-Host "  Remove-Job -Name DeepSeekAutoRefactor" -ForegroundColor Gray
                        Write-Host ""
                    }
                }
                
                break
            }
            
            if ($state.status -like "error*") {
                Write-Host "========================================================================" -ForegroundColor Red
                Write-Host "  ERROR DETECTED!" -ForegroundColor Red
                Write-Host "========================================================================" -ForegroundColor Red
                Write-Host ""
                
                if ($state.error) {
                    Write-Host "Error: $($state.error)" -ForegroundColor Red
                    Write-Host ""
                }
                
                break
            }
        }
        catch {
            Write-Host "ERROR: Failed to parse state file" -ForegroundColor Red
            Write-Host $_.Exception.Message -ForegroundColor Gray
            Write-Host ""
        }
    }
    else {
        Write-Host "Waiting for state file..." -ForegroundColor Yellow
        Write-Host ""
    }
    
    if (Test-Path $LogFile) {
        Write-Host "RECENT LOG ENTRIES:" -ForegroundColor Yellow
        $logContent = Get-Content $LogFile -Tail 5
        foreach ($line in $logContent) {
            Write-Host "  $line" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor DarkGray
    Write-Host ""
    
    Start-Sleep -Seconds $RefreshInterval
}

Write-Host "Monitoring stopped" -ForegroundColor Yellow
Write-Host ""
