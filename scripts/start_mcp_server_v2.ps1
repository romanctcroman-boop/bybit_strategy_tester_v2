# MCP Server Launcher v2.0 - Production Ready
# Implements all Perplexity Agent recommendations

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = "D:\bybit_strategy_tester_v2"
$VenvPython = "$ProjectRoot\.venv\Scripts\python.exe"
$ServerScript = "$ProjectRoot\mcp-server\server.py"
$LogDir = "$ProjectRoot\logs"
$LogFile = "$LogDir\mcp_server_launcher.log"
$PidFile = "$LogDir\mcp_server.pid"
$MaxRestarts = 10
$RestartWindow = 3600  # 1 hour in seconds
$RestartDelay = 5      # seconds

# Ensure log directory exists
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Write-Log {
    param($Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] $Message"
    Add-Content -Path $LogFile -Value $LogMessage
    Write-Host $LogMessage
}

function Get-RestartCount {
    $RestartFile = "$LogDir\mcp_restarts.json"
    
    if (Test-Path $RestartFile) {
        $Data = Get-Content $RestartFile | ConvertFrom-Json
        $Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        
        # Filter restarts within window
        $RecentRestarts = $Data.restarts | Where-Object { ($Now - $_) -lt $RestartWindow }
        
        # Update file
        @{ restarts = $RecentRestarts } | ConvertTo-Json | Set-Content $RestartFile
        
        return $RecentRestarts.Count
    }
    
    return 0
}

function Add-RestartRecord {
    $RestartFile = "$LogDir\mcp_restarts.json"
    $Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    
    if (Test-Path $RestartFile) {
        $Data = Get-Content $RestartFile | ConvertFrom-Json
        $Restarts = @($Data.restarts) + @($Now)
    }
    else {
        $Restarts = @($Now)
    }
    
    @{ restarts = $Restarts } | ConvertTo-Json | Set-Content $RestartFile
}

function Stop-MCPServer {
    Write-Log "Stopping MCP server..."
    
    if (Test-Path $PidFile) {
        $Pid = Get-Content $PidFile
        
        try {
            $Process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
            
            if ($Process) {
                # Graceful shutdown (SIGTERM equivalent)
                $Process.CloseMainWindow() | Out-Null
                Start-Sleep -Seconds 2
                
                # Force kill if still running
                if (!$Process.HasExited) {
                    Stop-Process -Id $Pid -Force
                    Write-Log "Force killed process $Pid"
                }
                else {
                    Write-Log "Process $Pid exited gracefully"
                }
            }
        }
        catch {
            Write-Log "Process $Pid not found or already stopped"
        }
        
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-MCPServer {
    Write-Log "Starting MCP server..."
    
    # Check restart rate limiting
    $RestartCount = Get-RestartCount
    
    if ($RestartCount -ge $MaxRestarts) {
        Write-Log "ERROR: Too many restarts ($RestartCount in last hour)!"
        Write-Log "Manual intervention required. Check logs at: $LogFile"
        Write-Log "Server log: $LogDir\mcp_server.log"
        exit 1
    }
    
    # Record this restart
    Add-RestartRecord
    Write-Log "Restart count: $($RestartCount + 1)/$MaxRestarts in last hour"
    
    # Start server process
    $Process = Start-Process -FilePath $VenvPython `
        -ArgumentList $ServerScript `
        -WorkingDirectory $ProjectRoot `
        -PassThru `
        -WindowStyle Hidden
    
    # Save PID
    $Process.Id | Set-Content $PidFile
    
    Write-Log "MCP server started with PID: $($Process.Id)"
    Write-Log "Log file: $LogDir\mcp_server.log"
    
    # Wait and verify process is still running
    Start-Sleep -Seconds 3
    
    if ($Process.HasExited) {
        Write-Log "ERROR: Server process exited immediately!"
        Write-Log "Exit code: $($Process.ExitCode)"
        Write-Log "Check server log for errors"
        return $false
    }
    
    Write-Log "Server is running and stable"
    return $true
}

function Watch-MCPServer {
    Write-Log "Starting MCP server watchdog..."
    Write-Log "Max restarts: $MaxRestarts per hour"
    Write-Log "Restart delay: $RestartDelay seconds"
    
    while ($true) {
        try {
            if (!(Test-Path $PidFile)) {
                Write-Log "PID file not found, starting server..."
                if (!(Start-MCPServer)) {
                    Write-Log "Failed to start server, waiting before retry..."
                    Start-Sleep -Seconds $RestartDelay
                }
            }
            else {
                $Pid = Get-Content $PidFile
                $Process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
                
                if (!$Process) {
                    Write-Log "Server process died (PID: $Pid), restarting..."
                    Remove-Item $PidFile -Force
                    Start-Sleep -Seconds $RestartDelay
                }
            }
            
            # Check every 10 seconds
            Start-Sleep -Seconds 10
            
        }
        catch {
            Write-Log "Watchdog error: $_"
            Start-Sleep -Seconds $RestartDelay
        }
    }
}

# Main execution
Write-Log "=" * 80
Write-Log "MCP Server Launcher v2.0 - Production Ready"
Write-Log "=" * 80
Write-Log "Project: $ProjectRoot"
Write-Log "Python: $VenvPython"
Write-Log "Server: $ServerScript"
Write-Log ""

# Check if server is already running
if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile
    $OldProcess = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
    
    if ($OldProcess) {
        Write-Log "MCP server already running (PID: $OldPid)"
        Write-Log "Stop it first with: Stop-Process -Id $OldPid"
        exit 0
    }
    else {
        Write-Log "Stale PID file found, cleaning up..."
        Remove-Item $PidFile -Force
    }
}

# Start initial server
if (Start-MCPServer) {
    Write-Log ""
    Write-Log "=" * 80
    Write-Log "✅ MCP SERVER STARTED SUCCESSFULLY"
    Write-Log "=" * 80
    Write-Log ""
    Write-Log "Monitor logs with: Get-Content $LogDir\mcp_server.log -Wait"
    Write-Log "Stop server with: Stop-Process -Id $(Get-Content $PidFile)"
    Write-Log ""
    
    # Start watchdog if requested
    if ($args -contains "--watch") {
        Watch-MCPServer
    }
}
else {
    Write-Log "Failed to start MCP server"
    exit 1
}
