# ========================================
# MCPApi Module
# Интеграция с MCP сервером и API
# ========================================

using module .\MCPEventLog.psm1

class MCPConfig {
    [string]$ServerEndpoint
    [int]$ServerPort
    [string]$LogSource
    [bool]$EnableRemoteLogging
    
    MCPConfig() {
        $this.ServerEndpoint = "http://localhost"
        $this.ServerPort = 8000
        $this.LogSource = "file"  # file, http, stdio
        $this.EnableRemoteLogging = $false
    }
}

class LogFileWatcher {
    hidden [string]$LogFilePath
    hidden [System.IO.FileSystemWatcher]$Watcher
    hidden [scriptblock]$OnEventCallback
    hidden [long]$LastPosition
    
    LogFileWatcher([string]$logPath, [scriptblock]$callback) {
        $this.LogFilePath = $logPath
        $this.OnEventCallback = $callback
        $this.LastPosition = 0
        
        if (Test-Path $logPath) {
            $fileInfo = Get-Item $logPath
            $this.LastPosition = $fileInfo.Length
        }
    }
    
    [void] Start() {
        if (-not (Test-Path $this.LogFilePath)) {
            Write-Warning "Log file not found: $($this.LogFilePath)"
            return
        }
        
        $directory = Split-Path $this.LogFilePath -Parent
        $fileName = Split-Path $this.LogFilePath -Leaf
        
        $this.Watcher = New-Object System.IO.FileSystemWatcher
        $this.Watcher.Path = $directory
        $this.Watcher.Filter = $fileName
        $this.Watcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite
        $this.Watcher.EnableRaisingEvents = $true
        
        # Register event handler
        Register-ObjectEvent -InputObject $this.Watcher -EventName Changed -Action {
            param($sender, $e)
            # This will be handled in ProcessNewEntries
        } | Out-Null
    }
    
    [void] ProcessNewEntries() {
        if (-not (Test-Path $this.LogFilePath)) {
            return
        }
        
        try {
            $fileInfo = Get-Item $this.LogFilePath
            $currentSize = $fileInfo.Length
            
            if ($currentSize -gt $this.LastPosition) {
                $reader = [System.IO.StreamReader]::new($this.LogFilePath, [System.Text.Encoding]::UTF8)
                $reader.BaseStream.Seek($this.LastPosition, [System.IO.SeekOrigin]::Begin) | Out-Null
                
                while (-not $reader.EndOfStream) {
                    $line = $reader.ReadLine()
                    if (-not [string]::IsNullOrWhiteSpace($line)) {
                        try {
                            $eventData = $line | ConvertFrom-Json
                            $event = $this.ParseLogEntry($eventData)
                            if ($null -ne $event) {
                                & $this.OnEventCallback $event
                            }
                        }
                        catch {
                            # Skip malformed JSON lines
                        }
                    }
                }
                
                $this.LastPosition = $reader.BaseStream.Position
                $reader.Close()
                $reader.Dispose()
            }
        }
        catch {
            Write-Warning "Error processing log entries: $_"
        }
    }
    
    hidden [MCPEvent] ParseLogEntry([object]$data) {
        # Parse JSON log entry and create MCPEvent
        # Expected format: { "timestamp": "...", "api": "...", "tool": "...", "status": "...", ... }
        
        try {
            $api = if ($data.api) { $data.api } else { "Unknown" }
            $tool = if ($data.tool) { $data.tool } else { "Unknown" }
            $status = if ($data.status) { $data.status } else { "UNKNOWN" }
            $tokens = if ($data.tokens) { [int]$data.tokens } else { 0 }
            $cost = if ($data.cost) { [decimal]$data.cost } else { 0 }
            $duration = if ($data.duration_ms) { [int]$data.duration_ms } else { 0 }
            
            $event = [MCPEvent]::new($api, $tool, $status, $tokens, $cost, $duration)
            
            if ($data.timestamp) {
                $event.Timestamp = [datetime]::Parse($data.timestamp)
            }
            
            return $event
        }
        catch {
            return $null
        }
    }
    
    [void] Stop() {
        if ($null -ne $this.Watcher) {
            $this.Watcher.EnableRaisingEvents = $false
            $this.Watcher.Dispose()
        }
    }
}

class MCPApiClient {
    hidden [MCPConfig]$Config
    hidden [LogFileWatcher]$LogWatcher
    
    MCPApiClient([MCPConfig]$config) {
        $this.Config = $config
    }
    
    [void] StartWatching([scriptblock]$callback) {
        if ($this.Config.LogSource -eq "file") {
            $logPath = "D:\bybit_strategy_tester_v2\logs\mcp_session.log"
            $this.LogWatcher = [LogFileWatcher]::new($logPath, $callback)
            $this.LogWatcher.Start()
        }
    }
    
    [void] ProcessEvents() {
        if ($null -ne $this.LogWatcher) {
            $this.LogWatcher.ProcessNewEntries()
        }
    }
    
    [void] StopWatching() {
        if ($null -ne $this.LogWatcher) {
            $this.LogWatcher.Stop()
        }
    }
    
    [void] SendMetrics([hashtable]$metrics) {
        if (-not $this.Config.EnableRemoteLogging) {
            return
        }
        
        try {
            $endpoint = "$($this.Config.ServerEndpoint):$($this.Config.ServerPort)/api/metrics"
            $body = $metrics | ConvertTo-Json -Compress
            
            Invoke-RestMethod -Uri $endpoint -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5 | Out-Null
        }
        catch {
            Write-Warning "Failed to send metrics to MCP server: $_"
        }
    }
}

# Export module members
Export-ModuleMember -Function * -Cmdlet * -Variable * -Alias *
