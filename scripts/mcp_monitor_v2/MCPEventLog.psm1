# ========================================
# MCPEventLog Module
# Структурированное хранение событий MCP
# ========================================

class MCPEvent {
    [datetime]$Timestamp
    [string]$EventId
    [string]$API          # DeepSeek, Perplexity, etc.
    [string]$Tool         # Tool name
    [string]$Status       # SUCCESS, FAILED, TIMEOUT
    [int]$Tokens
    [decimal]$Cost
    [int]$DurationMs
    [hashtable]$Metadata  # Additional data
    
    MCPEvent(
        [string]$api,
        [string]$tool,
        [string]$status,
        [int]$tokens = 0,
        [decimal]$cost = 0,
        [int]$durationMs = 0
    ) {
        $this.Timestamp = Get-Date
        $this.EventId = [guid]::NewGuid().ToString()
        $this.API = $api
        $this.Tool = $tool
        $this.Status = $status
        $this.Tokens = $tokens
        $this.Cost = $cost
        $this.DurationMs = $durationMs
        $this.Metadata = @{}
    }
    
    [string] ToString() {
        return "$($this.Timestamp.ToString('HH:mm:ss')) - $($this.API)/$($this.Tool) - $($this.Status)"
    }
    
    [hashtable] ToHashtable() {
        return @{
            Timestamp  = $this.Timestamp
            EventId    = $this.EventId
            API        = $this.API
            Tool       = $this.Tool
            Status     = $this.Status
            Tokens     = $this.Tokens
            Cost       = $this.Cost
            DurationMs = $this.DurationMs
            Metadata   = $this.Metadata
        }
    }
}

class RingBuffer {
    hidden [object[]]$Buffer
    hidden [int]$Head
    hidden [int]$Size
    hidden [int]$MaxSize
    
    RingBuffer([int]$maxSize) {
        $this.MaxSize = $maxSize
        $this.Buffer = @($null) * $maxSize
        $this.Head = 0
        $this.Size = 0
    }
    
    [void] Add([object]$item) {
        $this.Buffer[$this.Head] = $item
        $this.Head = ($this.Head + 1) % $this.MaxSize
        if ($this.Size -lt $this.MaxSize) {
            $this.Size++
        }
    }
    
    [object[]] GetAll() {
        if ($this.Size -eq 0) {
            return @()
        }
        
        $result = @()
        $start = if ($this.Size -lt $this.MaxSize) { 0 } else { $this.Head }
        
        for ($i = 0; $i -lt $this.Size; $i++) {
            $idx = ($start + $i) % $this.MaxSize
            if ($null -ne $this.Buffer[$idx]) {
                $result += $this.Buffer[$idx]
            }
        }
        
        return $result
    }
    
    [object[]] GetLast([int]$count) {
        $all = $this.GetAll()
        if ($all.Count -le $count) {
            return $all
        }
        return $all[($all.Count - $count)..($all.Count - 1)]
    }
}

class EventStore {
    hidden [RingBuffer]$RecentEvents
    hidden [string]$LogFilePath
    hidden [int]$EventCount
    hidden [System.IO.StreamWriter]$LogWriter
    
    EventStore([string]$logPath, [int]$bufferSize = 100) {
        $this.RecentEvents = [RingBuffer]::new($bufferSize)
        $this.LogFilePath = $logPath
        $this.EventCount = 0
        
        # Create log directory if not exists
        $logDir = Split-Path $logPath -Parent
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        
        # Open log file for appending
        $this.LogWriter = [System.IO.StreamWriter]::new($logPath, $true, [System.Text.Encoding]::UTF8)
        $this.LogWriter.AutoFlush = $true
    }
    
    [void] LogEvent([MCPEvent]$event) {
        # Add to ring buffer
        $this.RecentEvents.Add($event)
        $this.EventCount++
        
        # Write to file (JSON Lines format)
        try {
            $json = $event.ToHashtable() | ConvertTo-Json -Compress
            $this.LogWriter.WriteLine($json)
        }
        catch {
            Write-Warning "Failed to write event to log: $_"
        }
    }
    
    [object[]] GetRecentEvents([int]$count = 10) {
        return $this.RecentEvents.GetLast($count)
    }
    
    [int] GetTotalEventCount() {
        return $this.EventCount
    }
    
    [void] Close() {
        if ($null -ne $this.LogWriter) {
            $this.LogWriter.Close()
            $this.LogWriter.Dispose()
        }
    }
}

# Export module members
Export-ModuleMember -Function * -Cmdlet * -Variable * -Alias *
