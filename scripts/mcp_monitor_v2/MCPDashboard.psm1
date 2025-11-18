# ========================================
# MCPDashboard Module
# UI отображение MCP статистики
# ========================================

using module .\MCPEventLog.psm1
using module .\MCPStats.psm1

class DashboardConfig {
    [int]$RefreshIntervalSeconds
    [int]$RecentEventsCount
    [bool]$ShowDetailedStats
    [bool]$ColorOutput
    
    DashboardConfig() {
        $this.RefreshIntervalSeconds = 3
        $this.RecentEventsCount = 10
        $this.ShowDetailedStats = $true
        $this.ColorOutput = $true
    }
}

class Dashboard {
    hidden [StatsAggregator]$Stats
    hidden [EventStore]$EventStore
    hidden [DashboardConfig]$Config
    hidden [datetime]$LastRefresh
    
    Dashboard(
        [StatsAggregator]$stats,
        [EventStore]$eventStore,
        [DashboardConfig]$config
    ) {
        $this.Stats = $stats
        $this.EventStore = $eventStore
        $this.Config = $config
        $this.LastRefresh = [datetime]::MinValue
    }
    
    [void] Render() {
        Clear-Host
        
        $this.RenderHeader()
        $this.RenderSummary()
        $this.RenderAPIStats()
        $this.RenderRecentActivity()
        $this.RenderFooter()
        
        $this.LastRefresh = Get-Date
    }
    
    hidden [void] RenderHeader() {
        $this.WriteColorLine("=" * 80, "Cyan", $false)
        $this.WriteColorLine("  MCP MONITOR v2.0 - Activity Tracker (Enhanced)", "Cyan", $true)
        $this.WriteColorLine("=" * 80, "Cyan", $false)
        Write-Host ""
    }
    
    hidden [void] RenderSummary() {
        $uptime = $this.Stats.GetUptime()
        $totalEvents = $this.Stats.GetTotalEvents()
        
        $this.WriteColorLine("Uptime: $uptime | Total Events: $totalEvents", "Yellow", $false)
        Write-Host ""
    }
    
    hidden [void] RenderAPIStats() {
        $allStats = $this.Stats.GetAllStats()
        
        if ($allStats.Count -eq 0) {
            $this.WriteColorLine("--- NO ACTIVITY YET ---", "Gray", $false)
            Write-Host ""
            return
        }
        
        $sortedKeys = $allStats.Keys | Sort-Object
        foreach ($apiName in $sortedKeys) {
            $apiStats = $allStats[$apiName]
            
            $apiUpper = $apiName.ToUpper()
            $this.WriteColorLine("--- $apiUpper ---", "Green", $true)
            
            $successInfo = "Success: $($apiStats.SuccessfulCalls) / Failed: $($apiStats.FailedCalls)"
            Write-Host "  Calls: $($apiStats.TotalCalls) ($successInfo)"
            
            $successRate = $apiStats.GetSuccessRate()
            Write-Host "  Success Rate: ${successRate}%"
            
            if ($apiStats.TotalTokens -gt 0) {
                $costRounded = [math]::Round($apiStats.TotalCost, 4)
                Write-Host "  Tokens: $($apiStats.TotalTokens) | Cost: `$${costRounded}"
            }
            
            if ($apiStats.TotalDurationMs -gt 0) {
                $avgDuration = $apiStats.GetAverageDurationMs()
                Write-Host "  Avg Duration: ${avgDuration}ms"
            }
            
            if ($this.Config.ShowDetailedStats -and $apiStats.ToolStats.Count -gt 0) {
                Write-Host "  Top Tools:"
                $topTools = $apiStats.ToolStats.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 3
                foreach ($toolStat in $topTools) {
                    Write-Host "    - $($toolStat.Key): $($toolStat.Value) calls"
                }
            }
            
            Write-Host ""
        }
    }
    
    hidden [void] RenderRecentActivity() {
        $activityHeader = "--- RECENT ACTIVITY (Last $($this.Config.RecentEventsCount)) ---"
        $this.WriteColorLine($activityHeader, "Magenta", $true)
        
        $recentEvents = $this.EventStore.GetRecentEvents($this.Config.RecentEventsCount)
        
        if ($recentEvents.Count -eq 0) {
            Write-Host "  No events yet..."
            Write-Host ""
            return
        }
        
        # Reverse to show newest first
        [array]::Reverse($recentEvents)
        
        foreach ($mcpEvent in $recentEvents) {
            $timeStr = $mcpEvent.Timestamp.ToString('HH:mm:ss')
            
            $statusColor = "Gray"
            $statusIcon = "?"
            
            if ($mcpEvent.Status -eq "SUCCESS") {
                $statusColor = "Green"
                $statusIcon = "OK"
            }
            elseif ($mcpEvent.Status -eq "FAILED") {
                $statusColor = "Red"
                $statusIcon = "ERROR"
            }
            elseif ($mcpEvent.Status -eq "TIMEOUT") {
                $statusColor = "Yellow"
                $statusIcon = "TIMEOUT"
            }
            
            $apiTool = "$($mcpEvent.API)/$($mcpEvent.Tool)"
            $statusText = "[$statusIcon]"
            
            Write-Host "  $timeStr - " -NoNewline
            Write-Host $apiTool -NoNewline -ForegroundColor Cyan
            Write-Host " " -NoNewline
            Write-Host $statusText -ForegroundColor $statusColor
            
            if ($mcpEvent.DurationMs -gt 0) {
                $durationText = "           Duration: $($mcpEvent.DurationMs)ms"
                Write-Host $durationText -ForegroundColor DarkGray
            }
        }
        
        Write-Host ""
    }
    
    hidden [void] RenderFooter() {
        $this.WriteColorLine("-" * 80, "DarkGray", $false)
        
        $refreshTime = $this.LastRefresh.ToString('yyyy-MM-dd HH:mm:ss')
        $refreshInterval = $this.Config.RefreshIntervalSeconds
        
        Write-Host "Last Refresh: $refreshTime | Press Ctrl+C to exit | Refresh: ${refreshInterval}s" -ForegroundColor DarkGray
    }
    
    hidden [void] WriteColorLine([string]$text, [string]$color, [bool]$bold = $false) {
        if ($this.Config.ColorOutput) {
            Write-Host $text -ForegroundColor $color
        }
        else {
            Write-Host $text
        }
    }
}

# Export module members
Export-ModuleMember -Function * -Cmdlet * -Variable * -Alias *
