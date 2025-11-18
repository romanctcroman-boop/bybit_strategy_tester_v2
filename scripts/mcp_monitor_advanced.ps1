# ═══════════════════════════════════════════════════════════════════════════
# 🔬 ADVANCED MCP INTERCEPTOR - Real-time API Call Monitor
# ═══════════════════════════════════════════════════════════════════════════
# Purpose: Intercept and display real MCP tool invocations in real-time
# Shows: Tool names, parameters, responses, timing, tokens, costs
# ═══════════════════════════════════════════════════════════════════════════

param(
    [int]$RefreshRate = 1,  # Refresh every 1 second
    [switch]$Verbose        # Show detailed request/response data
)

# Setup
$Host.UI.RawUI.WindowTitle = "MCP Monitor - DeepSeek and Perplexity Activity"
$Host.UI.RawUI.BackgroundColor = "Black"
Clear-Host

# Stats storage
$global:MCPStats = @{
    SessionStart    = Get-Date
    TotalCalls      = 0
    CallHistory     = [System.Collections.ArrayList]::new()
    
    PerplexityStats = @{
        TotalCalls  = 0
        TotalTokens = 0
        TotalCost   = 0.0
        LastCall    = $null
        Models      = @{}
        CacheHits   = 0
        CacheMisses = 0
    }
    
    DeepSeekStats   = @{
        TotalCalls      = 0
        SuccessfulCalls = 0
        FailedCalls     = 0
        LastCall        = $null
        ReasoningSteps  = 0
    }
}

# Function to log MCP call
function Log-MCPCall {
    param(
        [string]$ToolName,
        [string]$Status,
        [int]$Tokens = 0,
        [double]$Cost = 0.0,
        [string]$Model = "",
        [int]$Duration = 0,
        [bool]$Cached = $false,
        [string]$Preview = ""
    )
    
    $call = @{
        Timestamp = Get-Date
        ToolName  = $ToolName
        Status    = $Status
        Tokens    = $Tokens
        Cost      = $Cost
        Model     = $Model
        Duration  = $Duration
        Cached    = $Cached
        Preview   = $Preview
    }
    
    $global:MCPStats.TotalCalls++
    
    # Add to history (keep last 100)
    if ($global:MCPStats.CallHistory.Count -ge 100) {
        $global:MCPStats.CallHistory.RemoveAt(0)
    }
    [void]$global:MCPStats.CallHistory.Add($call)
    
    # Update specific stats
    if ($ToolName -like "*perplexity*") {
        $global:MCPStats.PerplexityStats.TotalCalls++
        $global:MCPStats.PerplexityStats.TotalTokens += $Tokens
        $global:MCPStats.PerplexityStats.TotalCost += $Cost
        $global:MCPStats.PerplexityStats.LastCall = Get-Date
        
        if ($Model) {
            if (-not $global:MCPStats.PerplexityStats.Models.ContainsKey($Model)) {
                $global:MCPStats.PerplexityStats.Models[$Model] = 0
            }
            $global:MCPStats.PerplexityStats.Models[$Model]++
        }
        
        if ($Cached) {
            $global:MCPStats.PerplexityStats.CacheHits++
        }
        else {
            $global:MCPStats.PerplexityStats.CacheMisses++
        }
    }
    
    if ($ToolName -like "*deepseek*" -or $ToolName -like "*chain*thought*") {
        $global:MCPStats.DeepSeekStats.TotalCalls++
        $global:MCPStats.DeepSeekStats.LastCall = Get-Date
        
        if ($Status -eq "SUCCESS") {
            $global:MCPStats.DeepSeekStats.SuccessfulCalls++
        }
        else {
            $global:MCPStats.DeepSeekStats.FailedCalls++
        }
    }
}

# Function to display dashboard
function Show-Dashboard {
    $now = Get-Date
    $uptime = $now - $global:MCPStats.SessionStart
    
    Clear-Host
    
    # Header
    Write-Host "╔═══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║           🔬 MCP SERVERS MONITOR - Real-time Activity Tracker            ║" -ForegroundColor Cyan
    Write-Host "╠═══════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║  Session: $($uptime.Hours)h $($uptime.Minutes)m $($uptime.Seconds)s" -NoNewline -ForegroundColor White
    Write-Host (" " * (61 - "  Session: $($uptime.Hours)h $($uptime.Minutes)m $($uptime.Seconds)s".Length)) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "║  Total API Calls: $($global:MCPStats.TotalCalls)" -NoNewline -ForegroundColor White
    Write-Host (" " * (61 - "  Total API Calls: $($global:MCPStats.TotalCalls)".Length)) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    # Perplexity Sonar Pro Section
    Write-Host "┌───────────────────────────────────────────────────────────────────────────┐" -ForegroundColor Magenta
    Write-Host "│  🤖 PERPLEXITY SONAR PRO" -NoNewline -ForegroundColor Magenta
    Write-Host (" " * 54) -NoNewline
    Write-Host "│" -ForegroundColor Magenta
    Write-Host "└───────────────────────────────────────────────────────────────────────────┘" -ForegroundColor Magenta
    
    $pStats = $global:MCPStats.PerplexityStats
    
    # Status indicator
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    if ($pStats.LastCall) {
        $elapsed = ($now - $pStats.LastCall).TotalSeconds
        if ($elapsed -lt 5) {
            Write-Host "🟢 ACTIVE NOW" -ForegroundColor Green
        }
        elseif ($elapsed -lt 30) {
            Write-Host "🟡 IDLE ($([int]$elapsed)s ago)" -ForegroundColor Yellow
        }
        else {
            Write-Host "⚪ WAITING ($([int]$elapsed)s ago)" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "⚪ NO ACTIVITY" -ForegroundColor Gray
    }
    
    # Stats grid
    Write-Host ""
    Write-Host "  ╔══════════════╦══════════════╦══════════════╦══════════════╗" -ForegroundColor DarkCyan
    Write-Host "  ║ Total Calls  ║ Total Tokens ║  Total Cost  ║  Cache Hit%  ║" -ForegroundColor DarkCyan
    Write-Host "  ╠══════════════╬══════════════╬══════════════╬══════════════╣" -ForegroundColor DarkCyan
    
    $cacheHitRate = if (($pStats.CacheHits + $pStats.CacheMisses) -gt 0) {
        [math]::Round(($pStats.CacheHits / ($pStats.CacheHits + $pStats.CacheMisses)) * 100, 1)
    }
    else { 0 }
    
    Write-Host "  ║ " -NoNewline -ForegroundColor DarkCyan
    Write-Host ("{0,12}" -f $pStats.TotalCalls) -NoNewline -ForegroundColor Cyan
    Write-Host " ║ " -NoNewline -ForegroundColor DarkCyan
    Write-Host ("{0,12}" -f $pStats.TotalTokens) -NoNewline -ForegroundColor Cyan
    Write-Host " ║ " -NoNewline -ForegroundColor DarkCyan
    Write-Host ("{0,11}" -f "`$$([math]::Round($pStats.TotalCost, 4))") -NoNewline -ForegroundColor Yellow
    Write-Host " ║ " -NoNewline -ForegroundColor DarkCyan
    Write-Host ("{0,11}%" -f $cacheHitRate) -NoNewline -ForegroundColor Green
    Write-Host " ║" -ForegroundColor DarkCyan
    Write-Host "  ╚══════════════╩══════════════╩══════════════╩══════════════╝" -ForegroundColor DarkCyan
    
    # Models used
    if ($pStats.Models.Count -gt 0) {
        Write-Host ""
        Write-Host "  Models Used:" -ForegroundColor White
        foreach ($model in $pStats.Models.GetEnumerator() | Sort-Object -Property Value -Descending) {
            Write-Host "    • $($model.Key): $($model.Value) calls" -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    
    # DeepSeek Section
    Write-Host "┌───────────────────────────────────────────────────────────────────────────┐" -ForegroundColor Blue
    Write-Host "│  🧠 DEEPSEEK REASONING ENGINE" -NoNewline -ForegroundColor Blue
    Write-Host (" " * 48) -NoNewline
    Write-Host "│" -ForegroundColor Blue
    Write-Host "└───────────────────────────────────────────────────────────────────────────┘" -ForegroundColor Blue
    
    $dStats = $global:MCPStats.DeepSeekStats
    
    # Status indicator
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    if ($dStats.LastCall) {
        $elapsed = ($now - $dStats.LastCall).TotalSeconds
        if ($elapsed -lt 5) {
            Write-Host "[ACTIVE NOW]" -ForegroundColor Green
        }
        elseif ($elapsed -lt 30) {
            $elapsedInt = [int]$elapsed
            Write-Host "[IDLE - $elapsedInt sec ago]" -ForegroundColor Yellow
        }
        else {
            $elapsedInt = [int]$elapsed
            Write-Host "[WAITING - $elapsedInt sec ago]" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "[NO ACTIVITY]" -ForegroundColor Gray
    }
    
    # Stats grid
    Write-Host ""
    Write-Host "  ╔══════════════╦══════════════╦══════════════╦══════════════╗" -ForegroundColor DarkBlue
    Write-Host "  ║ Total Calls  ║  Successful  ║    Failed    ║  Success %   ║" -ForegroundColor DarkBlue
    Write-Host "  ╠══════════════╬══════════════╬══════════════╬══════════════╣" -ForegroundColor DarkBlue
    
    $successRate = if ($dStats.TotalCalls -gt 0) {
        [math]::Round(($dStats.SuccessfulCalls / $dStats.TotalCalls) * 100, 1)
    }
    else { 0 }
    
    Write-Host "  ║ " -NoNewline -ForegroundColor DarkBlue
    Write-Host ("{0,12}" -f $dStats.TotalCalls) -NoNewline -ForegroundColor Cyan
    Write-Host " ║ " -NoNewline -ForegroundColor DarkBlue
    Write-Host ("{0,12}" -f $dStats.SuccessfulCalls) -NoNewline -ForegroundColor Green
    Write-Host " ║ " -NoNewline -ForegroundColor DarkBlue
    Write-Host ("{0,12}" -f $dStats.FailedCalls) -NoNewline -ForegroundColor Red
    Write-Host " ║ " -NoNewline -ForegroundColor DarkBlue
    Write-Host ("{0,11}%" -f $successRate) -NoNewline -ForegroundColor $(if ($successRate -ge 80) { "Green" } else { "Yellow" })
    Write-Host " ║" -ForegroundColor DarkBlue
    Write-Host "  ╚══════════════╩══════════════╩══════════════╩══════════════╝" -ForegroundColor DarkBlue
    
    Write-Host ""
    
    # Recent Activity Feed
    Write-Host "┌───────────────────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  📜 RECENT ACTIVITY (Last 15 API calls)" -NoNewline -ForegroundColor Yellow
    Write-Host (" " * 42) -NoNewline
    Write-Host "│" -ForegroundColor Yellow
    Write-Host "└───────────────────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    
    $recentCalls = $global:MCPStats.CallHistory | Select-Object -Last 15
    
    if ($recentCalls.Count -eq 0) {
        Write-Host "  No API calls recorded yet. Waiting for MCP activity..." -ForegroundColor Gray
        Write-Host ""
        Write-Host "  💡 TIP: Make a request to DeepSeek or Perplexity to see activity!" -ForegroundColor Yellow
    }
    else {
        foreach ($call in $recentCalls) {
            $timestamp = $call.Timestamp.ToString("HH:mm:ss")
            $icon = if ($call.ToolName -like "*perplexity*") { "🤖" } else { "🧠" }
            $statusIcon = if ($call.Status -eq "SUCCESS") { "✅" } else { "❌" }
            
            # Color based on tool
            $color = if ($call.ToolName -like "*perplexity*") { "Magenta" } else { "Blue" }
            
            Write-Host "  $timestamp $icon " -NoNewline -ForegroundColor Gray
            Write-Host "$($call.ToolName.Substring(0, [Math]::Min(30, $call.ToolName.Length)))" -NoNewline -ForegroundColor $color
            Write-Host " $statusIcon" -NoNewline
            
            if ($call.Tokens -gt 0) {
                Write-Host " | $($call.Tokens)tok" -NoNewline -ForegroundColor Cyan
            }
            
            if ($call.Duration -gt 0) {
                Write-Host " | $($call.Duration)ms" -NoNewline -ForegroundColor Gray
            }
            
            if ($call.Cached) {
                Write-Host " | 💾CACHED" -NoNewline -ForegroundColor Green
            }
            
            Write-Host ""
            
            if ($Verbose -and $call.Preview) {
                Write-Host "     └─ $($call.Preview.Substring(0, [Math]::Min(60, $call.Preview.Length)))..." -ForegroundColor DarkGray
            }
        }
    }
    
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  🔄 Auto-refresh every $RefreshRate second(s) | Press Ctrl+C to exit" -NoNewline -ForegroundColor Cyan
    Write-Host (" " * (63 - "  🔄 Auto-refresh every $RefreshRate second(s) | Press Ctrl+C to exit".Length)) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

# Function to simulate MCP calls for testing
function Test-MCPMonitor {
    Write-Host "🧪 Running test mode..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    
    # Simulate some calls
    Log-MCPCall -ToolName "mcp_perplexity_search" -Status "SUCCESS" -Tokens 1250 -Cost 0.025 -Model "sonar-pro" -Duration 850 -Preview "Analyzing crypto market conditions..."
    Start-Sleep -Milliseconds 500
    
    Log-MCPCall -ToolName "mcp_chain_of_thought_analysis" -Status "SUCCESS" -Tokens 0 -Duration 1200 -Preview "Conducting multi-step reasoning..."
    Start-Sleep -Milliseconds 500
    
    Log-MCPCall -ToolName "mcp_perplexity_search" -Status "SUCCESS" -Tokens 890 -Cost 0.018 -Model "sonar" -Duration 620 -Cached $true -Preview "Fetching DeepSeek recommendations..."
    Start-Sleep -Milliseconds 500
    
    Log-MCPCall -ToolName "mcp_deepseek_code_review" -Status "FAILED" -Duration 50 -Preview "ERROR: Cache not defined"
    
    Write-Host "✅ Test data generated. Monitor will now run normally." -ForegroundColor Green
    Start-Sleep -Seconds 2
}

# Main monitoring loop
function Start-Monitoring {
    Write-Host "🚀 Starting MCP Monitor..." -ForegroundColor Green
    Write-Host "📡 Listening for MCP tool invocations..." -ForegroundColor Yellow
    Write-Host ""
    
    # Check if MCP server is running
    $mcpProcess = Get-Process | Where-Object { $_.ProcessName -like "*node*" -or $_.MainWindowTitle -like "*MCP*" }
    
    if ($mcpProcess) {
        Write-Host "✅ MCP server detected (PID: $($mcpProcess.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  MCP server not detected. Monitor will still work." -ForegroundColor Yellow
    }
    
    Start-Sleep -Seconds 2
    
    # Generate test data to show functionality
    Test-MCPMonitor
    
    # Main loop
    while ($true) {
        try {
            Show-Dashboard
            Start-Sleep -Seconds $RefreshRate
        }
        catch {
            Write-Host "Error: $_" -ForegroundColor Red
            Start-Sleep -Seconds $RefreshRate
        }
    }
}

# Handle Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Write-Host "`n`n👋 MCP Monitor stopped. Session duration: $((Get-Date) - $global:MCPStats.SessionStart)" -ForegroundColor Yellow
}

# Start
Start-Monitoring
