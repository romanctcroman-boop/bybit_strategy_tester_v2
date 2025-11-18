# ═══════════════════════════════════════════════════════════════════════════
# 🔬 MCP SERVERS MONITOR - Real-time DeepSeek & Perplexity Activity Tracker
# ═══════════════════════════════════════════════════════════════════════════
# Purpose: Monitor real MCP server activity to verify AI agent communications
# Shows: API calls, response times, tokens used, cache hits, errors
# ═══════════════════════════════════════════════════════════════════════════

# Configuration
$LogPath = "D:\bybit_strategy_tester_v2\logs\mcp_activity.log"
$RefreshInterval = 2  # seconds
$MaxLogLines = 1000

# Ensure log directory exists
$LogDir = Split-Path $LogPath -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Initialize log file
if (-not (Test-Path $LogPath)) {
    "=== MCP Monitor Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $LogPath
}

# Stats tracking
$script:Stats = @{
    DeepSeek   = @{
        TotalCalls      = 0
        SuccessfulCalls = 0
        FailedCalls     = 0
        TotalTokens     = 0
        TotalLatency    = 0
        LastActivity    = $null
        LastError       = $null
        CacheHits       = 0
        CacheMisses     = 0
    }
    Perplexity = @{
        TotalCalls      = 0
        SuccessfulCalls = 0
        FailedCalls     = 0
        TotalTokens     = 0
        TotalCost       = 0.0
        TotalLatency    = 0
        LastActivity    = $null
        LastError       = $null
        CacheHits       = 0
        CacheMisses     = 0
    }
    StartTime  = Get-Date
}

# Function to parse MCP log entries
function Parse-MCPLog {
    param([string]$Line)
    
    # Detect Perplexity API calls
    if ($Line -match 'perplexity.*query|mcp_bybit-strateg_perplexity') {
        $script:Stats.Perplexity.TotalCalls++
        $script:Stats.Perplexity.LastActivity = Get-Date
        
        # Extract tokens if present
        if ($Line -match 'total_tokens["\s:]+(\d+)') {
            $tokens = [int]$Matches[1]
            $script:Stats.Perplexity.TotalTokens += $tokens
        }
        
        # Extract cost if present
        if ($Line -match 'total_cost["\s:]+(\d+\.\d+)') {
            $cost = [double]$Matches[1]
            $script:Stats.Perplexity.TotalCost += $cost
        }
        
        # Detect success/failure
        if ($Line -match 'success.*true|"answer"') {
            $script:Stats.Perplexity.SuccessfulCalls++
        }
        elseif ($Line -match 'error|ERROR|failed') {
            $script:Stats.Perplexity.FailedCalls++
            $script:Stats.Perplexity.LastError = $Line
        }
        
        # Detect cache
        if ($Line -match 'cached.*true|cache.*hit') {
            $script:Stats.Perplexity.CacheHits++
        }
        elseif ($Line -match 'cached.*false|cache.*miss') {
            $script:Stats.Perplexity.CacheMisses++
        }
        
        return $true
    }
    
    # Detect DeepSeek/chain-of-thought calls
    if ($Line -match 'deepseek|chain.*thought|reasoning') {
        $script:Stats.DeepSeek.TotalCalls++
        $script:Stats.DeepSeek.LastActivity = Get-Date
        
        # Detect success/failure
        if ($Line -match 'success|completed|reasoning.*step') {
            $script:Stats.DeepSeek.SuccessfulCalls++
        }
        elseif ($Line -match 'error|ERROR|failed|cache.*not.*defined') {
            $script:Stats.DeepSeek.FailedCalls++
            $script:Stats.DeepSeek.LastError = $Line
        }
        
        return $true
    }
    
    return $false
}

# Function to display real-time stats
function Show-Stats {
    Clear-Host
    
    $now = Get-Date
    $uptime = $now - $script:Stats.StartTime
    
    # Header
    Write-Host "╔══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  🔬 MCP SERVERS MONITOR - Real-time AI Activity Tracker                 ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host " 📊 SYSTEM STATUS" -ForegroundColor Yellow
    Write-Host "  Uptime: $($uptime.Hours)h $($uptime.Minutes)m $($uptime.Seconds)s" -ForegroundColor White
    Write-Host "  Refresh: Every $RefreshInterval seconds" -ForegroundColor White
    Write-Host "  Log: $LogPath" -ForegroundColor Gray
    Write-Host ""
    
    # Perplexity Sonar Pro Stats
    Write-Host " 🤖 PERPLEXITY SONAR PRO" -ForegroundColor Magenta
    Write-Host "  ├─ Status: " -NoNewline -ForegroundColor White
    if ($script:Stats.Perplexity.LastActivity) {
        $timeSinceActivity = ($now - $script:Stats.Perplexity.LastActivity).TotalSeconds
        if ($timeSinceActivity -lt 30) {
            Write-Host "🟢 ACTIVE" -ForegroundColor Green
        }
        else {
            Write-Host "🟡 IDLE ($([int]$timeSinceActivity)s ago)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "⚪ NO ACTIVITY" -ForegroundColor Gray
    }
    
    Write-Host "  ├─ Total Calls: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.TotalCalls)" -ForegroundColor Cyan
    
    Write-Host "  ├─ Success: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.SuccessfulCalls) " -NoNewline -ForegroundColor Green
    Write-Host "/ Failed: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.FailedCalls)" -ForegroundColor Red
    
    Write-Host "  ├─ Tokens Used: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.TotalTokens)" -ForegroundColor Cyan
    
    Write-Host "  ├─ Total Cost: " -NoNewline -ForegroundColor White
    Write-Host "`$$([math]::Round($script:Stats.Perplexity.TotalCost, 4))" -ForegroundColor Yellow
    
    Write-Host "  ├─ Cache Hits: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.CacheHits) " -NoNewline -ForegroundColor Green
    Write-Host "/ Misses: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.Perplexity.CacheMisses)" -ForegroundColor Yellow
    
    if ($script:Stats.Perplexity.LastActivity) {
        Write-Host "  └─ Last Activity: " -NoNewline -ForegroundColor White
        Write-Host "$($script:Stats.Perplexity.LastActivity.ToString('HH:mm:ss'))" -ForegroundColor Cyan
    }
    
    if ($script:Stats.Perplexity.LastError) {
        Write-Host "  └─ Last Error: " -NoNewline -ForegroundColor Red
        $errorPreview = $script:Stats.Perplexity.LastError.Substring(0, [Math]::Min(60, $script:Stats.Perplexity.LastError.Length))
        Write-Host "$errorPreview..." -ForegroundColor Red
    }
    Write-Host ""
    
    # DeepSeek Stats
    Write-Host " 🧠 DEEPSEEK REASONING" -ForegroundColor Blue
    Write-Host "  ├─ Status: " -NoNewline -ForegroundColor White
    if ($script:Stats.DeepSeek.LastActivity) {
        $timeSinceActivity = ($now - $script:Stats.DeepSeek.LastActivity).TotalSeconds
        if ($timeSinceActivity -lt 30) {
            Write-Host "🟢 ACTIVE" -ForegroundColor Green
        }
        else {
            Write-Host "🟡 IDLE ($([int]$timeSinceActivity)s ago)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "⚪ NO ACTIVITY" -ForegroundColor Gray
    }
    
    Write-Host "  ├─ Total Calls: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.DeepSeek.TotalCalls)" -ForegroundColor Cyan
    
    Write-Host "  ├─ Success: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.DeepSeek.SuccessfulCalls) " -NoNewline -ForegroundColor Green
    Write-Host "/ Failed: " -NoNewline -ForegroundColor White
    Write-Host "$($script:Stats.DeepSeek.FailedCalls)" -ForegroundColor Red
    
    if ($script:Stats.DeepSeek.LastActivity) {
        Write-Host "  └─ Last Activity: " -NoNewline -ForegroundColor White
        Write-Host "$($script:Stats.DeepSeek.LastActivity.ToString('HH:mm:ss'))" -ForegroundColor Cyan
    }
    
    if ($script:Stats.DeepSeek.LastError) {
        Write-Host "  └─ Last Error: " -NoNewline -ForegroundColor Red
        $errorPreview = $script:Stats.DeepSeek.LastError.Substring(0, [Math]::Min(60, $script:Stats.DeepSeek.LastError.Length))
        Write-Host "$errorPreview..." -ForegroundColor Red
    }
    Write-Host ""
    
    # Recent Activity Log (last 10 entries)
    Write-Host " 📜 RECENT ACTIVITY (Last 10 events)" -ForegroundColor Yellow
    
    if (Test-Path $LogPath) {
        $recentLines = Get-Content $LogPath -Tail 10 -ErrorAction SilentlyContinue
        foreach ($line in $recentLines) {
            if ($line -match 'perplexity') {
                Write-Host "  🤖 " -NoNewline -ForegroundColor Magenta
                Write-Host $line.Substring(0, [Math]::Min(70, $line.Length)) -ForegroundColor Gray
            }
            elseif ($line -match 'deepseek|chain.*thought') {
                Write-Host "  🧠 " -NoNewline -ForegroundColor Blue
                Write-Host $line.Substring(0, [Math]::Min(70, $line.Length)) -ForegroundColor Gray
            }
            elseif ($line -match 'error|ERROR') {
                Write-Host "  ❌ " -NoNewline -ForegroundColor Red
                Write-Host $line.Substring(0, [Math]::Min(70, $line.Length)) -ForegroundColor Red
            }
            else {
                Write-Host "  ℹ️  " -NoNewline -ForegroundColor White
                Write-Host $line.Substring(0, [Math]::Min(70, $line.Length)) -ForegroundColor Gray
            }
        }
    }
    else {
        Write-Host "  No activity logged yet..." -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  Press Ctrl+C to stop monitoring                                        ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

# Function to monitor MCP server output
function Start-MCPMonitoring {
    Write-Host "Starting MCP Monitor..." -ForegroundColor Green
    Write-Host "Monitoring MCP server activity..." -ForegroundColor Yellow
    Write-Host ""
    
    # Find MCP server process (if running)
    $mcpProcess = Get-Process -Name "node", "python" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*mcp*" -or $_.CommandLine -like "*perplexity*" }
    
    if ($mcpProcess) {
        Write-Host "✅ Found MCP server process: PID $($mcpProcess.Id)" -ForegroundColor Green
        "MCP Process detected: PID $($mcpProcess.Id)" | Add-Content $LogPath
    }
    else {
        Write-Host "⚠️  MCP server process not found. Starting anyway..." -ForegroundColor Yellow
        "MCP Process not detected at startup" | Add-Content $LogPath
    }
    
    Start-Sleep -Seconds 2
    
    # Main monitoring loop
    $lastSize = 0
    
    while ($true) {
        try {
            # Check if log file has new content
            if (Test-Path $LogPath) {
                $currentSize = (Get-Item $LogPath).Length
                
                if ($currentSize -gt $lastSize) {
                    # Read new lines
                    $newContent = Get-Content $LogPath -Tail 100 -ErrorAction SilentlyContinue
                    
                    foreach ($line in $newContent) {
                        Parse-MCPLog -Line $line
                    }
                    
                    $lastSize = $currentSize
                }
            }
            
            # Also check VS Code extension logs (if accessible)
            $vscodeLogPath = "$env:USERPROFILE\.vscode\extensions\*mcp*\logs\*.log"
            $vscodeLogFiles = Get-ChildItem $vscodeLogPath -ErrorAction SilentlyContinue
            
            foreach ($logFile in $vscodeLogFiles) {
                $recentLines = Get-Content $logFile.FullName -Tail 50 -ErrorAction SilentlyContinue
                foreach ($line in $recentLines) {
                    if (Parse-MCPLog -Line $line) {
                        # Log detected activity
                        "$(Get-Date -Format 'HH:mm:ss') - $line" | Add-Content $LogPath
                    }
                }
            }
            
            # Display updated stats
            Show-Stats
            
            # Wait before next refresh
            Start-Sleep -Seconds $RefreshInterval
            
        }
        catch {
            Write-Host "Error in monitoring loop: $_" -ForegroundColor Red
            Start-Sleep -Seconds $RefreshInterval
        }
    }
}

# Trap Ctrl+C to clean up
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Write-Host "`n`nMCP Monitor stopped." -ForegroundColor Yellow
    "=== MCP Monitor Stopped: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Add-Content $LogPath
}

# Start monitoring
Clear-Host
Start-MCPMonitoring
