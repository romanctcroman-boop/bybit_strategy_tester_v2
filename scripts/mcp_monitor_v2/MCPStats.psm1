# ========================================
# MCPStats Module
# Агрегация статистики MCP событий
# ========================================

using module .\MCPEventLog.psm1

class APIStats {
    [int]$TotalCalls
    [int]$SuccessfulCalls
    [int]$FailedCalls
    [int]$TotalTokens
    [decimal]$TotalCost
    [long]$TotalDurationMs
    [datetime]$LastCallTime
    [hashtable]$ToolStats  # Tool name -> count
    
    APIStats() {
        $this.TotalCalls = 0
        $this.SuccessfulCalls = 0
        $this.FailedCalls = 0
        $this.TotalTokens = 0
        $this.TotalCost = 0
        $this.TotalDurationMs = 0
        $this.LastCallTime = [datetime]::MinValue
        $this.ToolStats = @{}
    }
    
    [void] UpdateFromEvent([MCPEvent]$event) {
        $this.TotalCalls++
        $this.TotalTokens += $event.Tokens
        $this.TotalCost += $event.Cost
        $this.TotalDurationMs += $event.DurationMs
        $this.LastCallTime = $event.Timestamp
        
        if ($event.Status -eq "SUCCESS") {
            $this.SuccessfulCalls++
        }
        else {
            $this.FailedCalls++
        }
        
        # Update tool stats
        if (-not $this.ToolStats.ContainsKey($event.Tool)) {
            $this.ToolStats[$event.Tool] = 0
        }
        $this.ToolStats[$event.Tool]++
    }
    
    [double] GetSuccessRate() {
        if ($this.TotalCalls -eq 0) { return 0 }
        return [math]::Round(($this.SuccessfulCalls / $this.TotalCalls) * 100, 2)
    }
    
    [double] GetAverageDurationMs() {
        if ($this.TotalCalls -eq 0) { return 0 }
        return [math]::Round($this.TotalDurationMs / $this.TotalCalls, 2)
    }
    
    [double] GetAverageCost() {
        if ($this.TotalCalls -eq 0) { return 0 }
        return [math]::Round($this.TotalCost / $this.TotalCalls, 4)
    }
}

class StatsAggregator {
    hidden [hashtable]$APIStats
    hidden [datetime]$StartTime
    hidden [int]$TotalEvents
    
    StatsAggregator() {
        $this.APIStats = @{}
        $this.StartTime = Get-Date
        $this.TotalEvents = 0
    }
    
    [void] ProcessEvent([MCPEvent]$event) {
        $this.TotalEvents++
        
        # Create stats object for API if not exists
        if (-not $this.APIStats.ContainsKey($event.API)) {
            $this.APIStats[$event.API] = [APIStats]::new()
        }
        
        # Update stats
        $this.APIStats[$event.API].UpdateFromEvent($event)
    }
    
    [APIStats] GetAPIStats([string]$api) {
        if ($this.APIStats.ContainsKey($api)) {
            return $this.APIStats[$api]
        }
        return [APIStats]::new()
    }
    
    [hashtable] GetAllStats() {
        return $this.APIStats
    }
    
    [string] GetUptime() {
        $elapsed = (Get-Date) - $this.StartTime
        return "{0}h {1}m {2}s" -f [int]$elapsed.TotalHours, $elapsed.Minutes, $elapsed.Seconds
    }
    
    [int] GetTotalEvents() {
        return $this.TotalEvents
    }
    
    [hashtable] GetSummary() {
        $summary = @{
            Uptime      = $this.GetUptime()
            TotalEvents = $this.TotalEvents
            APIs        = @{}
        }
        
        foreach ($api in $this.APIStats.Keys) {
            $stats = $this.APIStats[$api]
            $summary.APIs[$api] = @{
                TotalCalls  = $stats.TotalCalls
                SuccessRate = $stats.GetSuccessRate()
                TotalTokens = $stats.TotalTokens
                TotalCost   = $stats.TotalCost
                AvgDuration = $stats.GetAverageDurationMs()
                TopTools    = $stats.ToolStats.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 3
            }
        }
        
        return $summary
    }
}

# Export module members
Export-ModuleMember -Function * -Cmdlet * -Variable * -Alias *
