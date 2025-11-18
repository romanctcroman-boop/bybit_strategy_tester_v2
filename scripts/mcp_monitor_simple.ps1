# Simple MCP Monitor - No fancy formatting
# Ultra-compatible with PowerShell 5.1

$Host.UI.RawUI.WindowTitle = "MCP Monitor"
Clear-Host

# Global stats
$global:Stats = @{
    Start   = Get-Date
    Calls   = 0
    History = @()
}

# Add test data
function Add-TestData {
    $global:Stats.History += @{
        Time   = Get-Date
        Tool   = "mcp_perplexity_search"
        Status = "SUCCESS"
        Tokens = 1250
    }
    $global:Stats.History += @{
        Time   = Get-Date
        Tool   = "mcp_chain_of_thought"
        Status = "SUCCESS"
        Tokens = 0
    }
    $global:Stats.History += @{
        Time   = Get-Date
        Tool   = "mcp_perplexity_search"
        Status = "SUCCESS"
        Tokens = 890
    }
    $global:Stats.History += @{
        Time   = Get-Date
        Tool   = "mcp_deepseek_review"
        Status = "FAILED"
        Tokens = 0
    }
    $global:Stats.Calls = $global:Stats.History.Count
}

# Display function
function Show-Stats {
    Clear-Host
    
    $uptime = (Get-Date) - $global:Stats.Start
    $uptimeText = "Uptime: " + $uptime.Hours + "h " + $uptime.Minutes + "m " + $uptime.Seconds + "s"
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  MCP MONITOR - Activity Tracker" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host $uptimeText -ForegroundColor White
    Write-Host "Total Calls: $($global:Stats.Calls)" -ForegroundColor White
    Write-Host ""
    
    Write-Host "--- PERPLEXITY SONAR PRO ---" -ForegroundColor Magenta
    $pCalls = ($global:Stats.History | Where-Object { $_.Tool -like "*perplexity*" }).Count
    $pItems = $global:Stats.History | Where-Object { $_.Tool -like "*perplexity*" }
    $pTokens = 0
    foreach ($item in $pItems) { $pTokens += $item.Tokens }
    Write-Host "Calls: $pCalls" -ForegroundColor White
    Write-Host "Tokens: $pTokens" -ForegroundColor White
    Write-Host ""
    
    Write-Host "--- DEEPSEEK REASONING ---" -ForegroundColor Blue
    $dCalls = ($global:Stats.History | Where-Object { $_.Tool -like "*deepseek*" -or $_.Tool -like "*chain*" }).Count
    $dSuccess = ($global:Stats.History | Where-Object { ($_.Tool -like "*deepseek*" -or $_.Tool -like "*chain*") -and $_.Status -eq "SUCCESS" }).Count
    Write-Host "Calls: $dCalls" -ForegroundColor White
    Write-Host "Successful: $dSuccess" -ForegroundColor White
    Write-Host ""
    
    Write-Host "--- RECENT ACTIVITY (Last 10) ---" -ForegroundColor Yellow
    $recent = $global:Stats.History | Select-Object -Last 10
    foreach ($call in $recent) {
        $timeStr = $call.Time.ToString("HH:mm:ss")
        $line = "$timeStr - $($call.Tool) - $($call.Status)"
        if ($call.Status -eq "SUCCESS") {
            Write-Host $line -ForegroundColor Green
        }
        else {
            Write-Host $line -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "Press Ctrl+C to exit" -ForegroundColor Gray
}

# Main loop
Write-Host "Starting MCP Monitor..." -ForegroundColor Green
Write-Host "Loading test data..." -ForegroundColor Yellow
Start-Sleep -Seconds 1

Add-TestData

Write-Host "Monitor ready!" -ForegroundColor Green
Start-Sleep -Seconds 2

while ($true) {
    Show-Stats
    Start-Sleep -Seconds 1
}
