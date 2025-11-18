# Monitor Self-Improvement Orchestrator Progress

param(
    [int]$CheckIntervalSeconds = 30,
    [int]$MaxChecks = 60
)

Write-Host "`n🔍 MONITORING SELF-IMPROVEMENT SESSION" -ForegroundColor Cyan
Write-Host "="*80

$checkCount = 0

while ($checkCount -lt $MaxChecks) {
    $checkCount++
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    Write-Host "`n[$timestamp] Check #$checkCount/$MaxChecks" -ForegroundColor Yellow
    
    # Check for generated artifacts
    $artifactDirs = Get-ChildItem -Path "logs" -Filter "self_improvement_*" -Directory -ErrorAction SilentlyContinue
    
    if ($artifactDirs) {
        Write-Host "  📁 Found session directories:" -ForegroundColor Green
        foreach ($dir in $artifactDirs) {
            $fileCount = (Get-ChildItem -Path $dir.FullName -File).Count
            Write-Host "     - $($dir.Name): $fileCount files" -ForegroundColor White
            
            # List files
            $files = Get-ChildItem -Path $dir.FullName -File | Select-Object -ExpandProperty Name
            foreach ($file in $files) {
                Write-Host "       • $file" -ForegroundColor Gray
            }
        }
        
        # Show latest file content preview
        $latestFile = Get-ChildItem -Path "logs\self_improvement_*\*" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latestFile) {
            Write-Host "`n  📄 Latest file: $($latestFile.Name)" -ForegroundColor Cyan
            Write-Host "     Modified: $($latestFile.LastWriteTime)" -ForegroundColor Gray
            Write-Host "     Size: $([math]::Round($latestFile.Length / 1KB, 2)) KB" -ForegroundColor Gray
            
            # Preview first 20 lines
            $preview = Get-Content $latestFile.FullName -TotalCount 20 -ErrorAction SilentlyContinue
            if ($preview) {
                Write-Host "`n     Preview:" -ForegroundColor Cyan
                $preview | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkGray }
            }
        }
    }
    else {
        Write-Host "  ⏳ No artifacts yet - agents still thinking..." -ForegroundColor Yellow
    }
    
    # Check if Python process is running
    $pythonProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue
    if ($pythonProcess) {
        Write-Host "`n  ✅ Orchestrator running:" -ForegroundColor Green
        Write-Host "     PID: $($pythonProcess.Id)" -ForegroundColor White
        Write-Host "     CPU: $([math]::Round($pythonProcess.CPU, 2))s" -ForegroundColor White
        Write-Host "     Memory: $([math]::Round($pythonProcess.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor White
    }
    else {
        Write-Host "`n  ⚠️ Orchestrator not running - may have completed or crashed" -ForegroundColor Red
        
        # Check for final report
        $finalReport = Get-ChildItem -Path "logs\self_improvement_*\SELF_IMPROVEMENT_FINAL_REPORT.md" -ErrorAction SilentlyContinue
        if ($finalReport) {
            Write-Host "  🎉 Final report found! Session complete." -ForegroundColor Green
            break
        }
    }
    
    # Check recent log entries
    $logFiles = Get-ChildItem -Path "logs" -Filter "self_improvement_session*.log" -ErrorAction SilentlyContinue
    if ($logFiles) {
        $latestLog = $logFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $recentLines = Get-Content $latestLog.FullName -Tail 5 -ErrorAction SilentlyContinue
        if ($recentLines) {
            Write-Host "`n  📋 Recent log entries:" -ForegroundColor Cyan
            $recentLines | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkGray }
        }
    }
    
    if ($checkCount -lt $MaxChecks) {
        Write-Host "`n  ⏱️ Next check in ${CheckIntervalSeconds}s..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds $CheckIntervalSeconds
    }
}

Write-Host "`n"
Write-Host "="*80
Write-Host "Monitoring complete. Check logs/self_improvement_*/ for full results." -ForegroundColor Cyan
Write-Host "="*80
