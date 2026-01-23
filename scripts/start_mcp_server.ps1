# ============================================
# MCP Server Startup Script
# ============================================
# Starts the Model Context Protocol server for AI integration
# Provides AI tools for trading strategies, backtests, and optimization
# ============================================

param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$McpRoot = Join-Path $ProjectRoot "mcp-server"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "mcp_server.log"
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '')]
$McpPidFile = Join-Path $LogDir "mcp_server.pid"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Get-McpServerPid {
    if (Test-Path $McpPidFile) {
        $mcpProcId = Get-Content $McpPidFile -ErrorAction SilentlyContinue
        if ($mcpProcId) {
            $process = Get-Process -Id $mcpProcId -ErrorAction SilentlyContinue
            if ($process -and $process.ProcessName -like "*python*") {
                return [int]$mcpProcId
            }
        }
        # Clean up stale PID file
        Remove-Item $McpPidFile -Force -ErrorAction SilentlyContinue
    }
    return $null
}

function Start-McpServer {
    $existingPid = Get-McpServerPid
    if ($existingPid) {
        Write-Host "[INFO] MCP Server is already running (PID: $existingPid)" -ForegroundColor Yellow
        return
    }

    Write-Host "[INFO] Starting MCP Server..." -ForegroundColor Cyan

    # Check if mcp-server directory exists
    if (-not (Test-Path $McpRoot)) {
        Write-Host "[ERROR] MCP Server directory not found: $McpRoot" -ForegroundColor Red
        return
    }

    # Check if server.py exists
    $serverScript = Join-Path $McpRoot "server.py"
    if (-not (Test-Path $serverScript)) {
        Write-Host "[ERROR] MCP Server script not found: $serverScript" -ForegroundColor Red
        return
    }

    # Load .env file
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }

    # Set UTF-8 encoding for Python output
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")

    # Start MCP Server in background
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $VenvPython
    $startInfo.Arguments = "`"$serverScript`""
    $startInfo.WorkingDirectory = $McpRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    
    try {
        $process.Start() | Out-Null
        $process.Id | Out-File -FilePath $McpPidFile -Force
        
        # Wait a moment to check if it started successfully
        Start-Sleep -Seconds 2
        
        if (-not $process.HasExited) {
            Write-Host "[OK] MCP Server started (PID: $($process.Id))" -ForegroundColor Green
            Write-Host "     Log file: $LogFile" -ForegroundColor Gray
        }
        else {
            $exitCode = $process.ExitCode
            $stderr = $process.StandardError.ReadToEnd()
            Write-Host "[ERROR] MCP Server failed to start (exit code: $exitCode)" -ForegroundColor Red
            if ($stderr) {
                Write-Host "[ERROR] $stderr" -ForegroundColor Red
            }
            Remove-Item $McpPidFile -Force -ErrorAction SilentlyContinue
        }
    }
    catch {
        Write-Host "[ERROR] Failed to start MCP Server: $_" -ForegroundColor Red
    }
}

function Stop-McpServer {
    $existingPid = Get-McpServerPid
    if (-not $existingPid) {
        Write-Host "[INFO] MCP Server is not running" -ForegroundColor Yellow
        return
    }

    Write-Host "[INFO] Stopping MCP Server (PID: $existingPid)..." -ForegroundColor Cyan
    
    try {
        Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
        Remove-Item $McpPidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] MCP Server stopped" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERROR] Failed to stop MCP Server: $_" -ForegroundColor Red
    }
}

function Get-McpServerStatus {
    $existingPid = Get-McpServerPid
    if ($existingPid) {
        $process = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($process) {
            $cpu = $process.CPU
            $memory = [math]::Round($process.WorkingSet64 / 1MB, 2)
            Write-Host "[STATUS] MCP Server is RUNNING" -ForegroundColor Green
            Write-Host "         PID: $existingPid" -ForegroundColor White
            Write-Host "         Memory: $memory MB" -ForegroundColor White
            Write-Host "         CPU: $cpu seconds" -ForegroundColor White
            return
        }
    }
    Write-Host "[STATUS] MCP Server is NOT RUNNING" -ForegroundColor Yellow
}

# Main logic
switch ($Action) {
    "start" { Start-McpServer }
    "stop" { Stop-McpServer }
    "status" { Get-McpServerStatus }
    "restart" {
        Stop-McpServer
        Start-Sleep -Seconds 2
        Start-McpServer
    }
}
