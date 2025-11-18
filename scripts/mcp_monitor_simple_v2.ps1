# ═══════════════════════════════════════════════════════════════════════════
# MCP Activity Monitor - Simple Version (No Emoji, No Parser Errors)
# ═══════════════════════════════════════════════════════════════════════════

# Configuration
$LogPath = "D:\bybit_strategy_tester_v2\logs\mcp_activity.jsonl"
$RefreshInterval = 2  # seconds

# Stats tracking
$script:Stats = @{
    TotalEvents     = 0
    SuccessfulCalls = 0
    FailedCalls     = 0
    TotalTokens     = 0
    TotalCost       = 0.0
    LastActivity    = $null
    PerplexityCalls = 0
    DeepSeekCalls   = 0
    StartTime       = Get-Date
}

# Function to parse JSON log line
function Get-LogEntry {
    param([string]$Line)
    
    try {
        $entry = $Line | ConvertFrom-Json
        
        $script:Stats.TotalEvents++
        $script:Stats.LastActivity = Get-Date
        
        # Update stats based on entry
        if ($entry.status -eq "SUCCESS") {
            $script:Stats.SuccessfulCalls++
        }
        elseif ($entry.status -eq "FAILED") {
            $script:Stats.FailedCalls++
        }
        
        # Add tokens and cost
        if ($entry.tokens) {
            $script:Stats.TotalTokens += $entry.tokens
        }
        if ($entry.cost) {
            $script:Stats.TotalCost += $entry.cost
        }
        
        # Track API type
        if ($entry.api -eq "Perplexity") {
            $script:Stats.PerplexityCalls++
        }
        elseif ($entry.api -match "DeepSeek") {
            $script:Stats.DeepSeekCalls++
        }
        
        return $entry
    }
    catch {
        return $null
    }
}

# Function to display stats
function Show-Stats {
    param([array]$RecentEvents)
    
    Clear-Host
    
    $now = Get-Date
    $uptime = $now - $script:Stats.StartTime
    
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Write-Host "  MCP ACTIVITY MONITOR - Real-time Tool Call Tracking" -ForegroundColor Cyan
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host " SYSTEM STATUS" -ForegroundColor Yellow
    Write-Host "  Uptime: $($uptime.Hours)h $($uptime.Minutes)m $($uptime.Seconds)s"
    Write-Host "  Refresh: Every $RefreshInterval seconds"
    Write-Host "  Log file: $LogPath"
    Write-Host ""
    
    Write-Host " STATISTICS" -ForegroundColor Green
    Write-Host "  Total Events: $($script:Stats.TotalEvents)"
    Write-Host "  Successful: $($script:Stats.SuccessfulCalls) | Failed: $($script:Stats.FailedCalls)"
    Write-Host "  Total Tokens: $($script:Stats.TotalTokens)"
    Write-Host "  Total Cost: `$$([math]::Round($script:Stats.TotalCost, 6))"
    Write-Host ""
    
    Write-Host " API BREAKDOWN" -ForegroundColor Magenta
    Write-Host "  Perplexity calls: $($script:Stats.PerplexityCalls)"
    Write-Host "  DeepSeek calls: $($script:Stats.DeepSeekCalls)"
    Write-Host ""
    
    if ($script:Stats.LastActivity) {
        $timeSince = ($now - $script:Stats.LastActivity).TotalSeconds
        Write-Host "  Last activity: $([int]$timeSince) seconds ago" -ForegroundColor Cyan
    }
    Write-Host ""
    
    # Recent events
    Write-Host " RECENT EVENTS (Last 10)" -ForegroundColor Yellow
    
    if ($RecentEvents.Count -gt 0) {
        foreach ($logEvent in $RecentEvents[-10..-1]) {
            if ($logEvent) {
                $status = if ($logEvent.status -eq "SUCCESS") { "[OK]" } else { "[FAIL]" }
                $statusColor = if ($logEvent.status -eq "SUCCESS") { "Green" } else { "Red" }
                
                $timestamp = $logEvent.timestamp
                $api = $logEvent.api
                $tool = $logEvent.tool
                $duration = $logEvent.duration_ms
                $tokens = if ($logEvent.tokens) { $logEvent.tokens } else { 0 }
                
                Write-Host "  $status " -NoNewline -ForegroundColor $statusColor
                Write-Host "$timestamp | $api/$tool | ${duration}ms | ${tokens} tokens" -ForegroundColor Gray
            }
        }
    }
    else {
        Write-Host "  No events logged yet..." -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Write-Host "  Press Ctrl+C to stop monitoring" -ForegroundColor Cyan
    Write-Host "===============================================================================" -ForegroundColor Cyan
}

# Main monitoring loop
function Start-Monitoring {
    Write-Host "Starting MCP Activity Monitor..." -ForegroundColor Green
    Write-Host "Monitoring: $LogPath" -ForegroundColor Yellow
    Write-Host ""
    
    # Check if log file exists
    if (-not (Test-Path $LogPath)) {
        Write-Host "Warning: Log file not found. Creating..." -ForegroundColor Yellow
        $logDir = Split-Path $LogPath -Parent
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        New-Item -ItemType File -Path $LogPath -Force | Out-Null
    }
    
    Start-Sleep -Seconds 1
    
    $recentEvents = @()
    
    while ($true) {
        try {
            # RESET STATS BEFORE EACH REFRESH (fix накопления)
            $script:Stats.TotalEvents = 0
            $script:Stats.SuccessfulCalls = 0
            $script:Stats.FailedCalls = 0
            $script:Stats.TotalTokens = 0
            $script:Stats.TotalCost = 0.0
            $script:Stats.PerplexityCalls = 0
            $script:Stats.DeepSeekCalls = 0
            
            # Read all log entries
            if (Test-Path $LogPath) {
                $lines = Get-Content $LogPath -ErrorAction SilentlyContinue
                
                # Parse each line
                $recentEvents = @()
                foreach ($line in $lines) {
                    if ($line.Trim() -ne "") {
                        $entry = Get-LogEntry -Line $line
                        if ($entry) {
                            $recentEvents += $entry
                        }
                    }
                }
            }
            
            # Display stats
            Show-Stats -RecentEvents $recentEvents
            
            # Wait before next refresh
            Start-Sleep -Seconds $RefreshInterval
        }
        catch {
            Write-Host "Error in monitoring loop: $_" -ForegroundColor Red
            Start-Sleep -Seconds $RefreshInterval
        }
    }
}

# Handle Ctrl+C gracefully
try {
    Start-Monitoring
}
finally {
    Write-Host ""
    Write-Host "MCP Monitor stopped." -ForegroundColor Yellow
}
