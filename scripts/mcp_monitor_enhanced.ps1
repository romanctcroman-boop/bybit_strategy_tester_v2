# ========================================
# MCP Monitor Enhanced v2.0
# Улучшенный Activity Tracker с модульной архитектурой
# ========================================

using module .\mcp_monitor_v2\MCPEventLog.psm1
using module .\mcp_monitor_v2\MCPStats.psm1
using module .\mcp_monitor_v2\MCPDashboard.psm1
using module .\mcp_monitor_v2\MCPApi.psm1

param(
    [string]$ConfigPath = "$PSScriptRoot\mcp_monitor_v2\config.json"
)

$ErrorActionPreference = "Stop"

# Load configuration
$config = Get-Content $ConfigPath | ConvertFrom-Json

# Initialize components
$dashboardConfig = [DashboardConfig]::new()
$dashboardConfig.RefreshIntervalSeconds = $config.dashboard.refreshIntervalSeconds
$dashboardConfig.RecentEventsCount = $config.dashboard.recentEventsCount
$dashboardConfig.ShowDetailedStats = $config.dashboard.showDetailedStats
$dashboardConfig.ColorOutput = $config.dashboard.colorOutput

$eventStore = [EventStore]::new($config.storage.logFilePath, $config.storage.ringBufferSize)
$statsAggregator = [StatsAggregator]::new()
$dashboard = [Dashboard]::new($statsAggregator, $eventStore, $dashboardConfig)

$mcpConfig = [MCPConfig]::new()
$mcpConfig.ServerEndpoint = $config.mcpServer.serverEndpoint
$mcpConfig.ServerPort = $config.mcpServer.serverPort
$mcpConfig.LogSource = $config.mcpServer.logSource
$mcpConfig.EnableRemoteLogging = $config.mcpServer.enableRemoteLogging

$apiClient = [MCPApiClient]::new($mcpConfig)

# Event handler
$eventHandler = {
    param($mcpEvent)
    
    $eventStore.LogEvent($mcpEvent)
    $statsAggregator.ProcessEvent($mcpEvent)
}

# Simulation mode for testing (if no real log file)
$simulationMode = $false
if (-not (Test-Path $config.mcpServer.sessionLogPath)) {
    Write-Host "No session log found. Starting in SIMULATION mode..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    $simulationMode = $true
}

# Generate test events for simulation
function New-TestEvent {
    param(
        [string]$api,
        [string]$tool
    )
    
    $statuses = @("SUCCESS", "SUCCESS", "SUCCESS", "FAILED")  # 75% success rate
    $status = $statuses | Get-Random
    
    $tokens = if ($api -eq "Perplexity") { Get-Random -Minimum 100 -Maximum 500 } else { 0 }
    $cost = if ($api -eq "Perplexity") { [decimal](Get-Random -Minimum 1 -Maximum 20) / 1000 } else { 0 }
    $duration = Get-Random -Minimum 500 -Maximum 8000
    
    $newEvent = [MCPEvent]::new($api, $tool, $status, $tokens, $cost, $duration)
    return $newEvent
}

# Start API client (file watcher or simulation)
if (-not $simulationMode) {
    $apiClient.StartWatching($eventHandler)
}

# Cleanup handler
$cleanupHandler = {
    Write-Host "`n`nShutting down MCP Monitor..." -ForegroundColor Yellow
    
    if ($null -ne $apiClient) {
        $apiClient.StopWatching()
    }
    
    if ($null -ne $eventStore) {
        $eventStore.Close()
    }
    
    Write-Host "Final statistics saved to: $($config.storage.logFilePath)" -ForegroundColor Green
    Write-Host "Total events processed: $($statsAggregator.GetTotalEvents())" -ForegroundColor Cyan
    
    exit 0
}

# Register cleanup on Ctrl+C
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupHandler | Out-Null
try {
    [Console]::TreatControlCAsInput = $false
}
catch {}

# Main loop
$iteration = 0
$testTools = @(
    @{API = "DeepSeek"; Tool = "quick_reasoning_analysis" },
    @{API = "DeepSeek"; Tool = "chain_of_thought_analysis" },
    @{API = "Perplexity"; Tool = "perplexity_search" },
    @{API = "Perplexity"; Tool = "perplexity_search_streaming" },
    @{API = "Perplexity"; Tool = "perplexity_analyze_crypto" }
)

Write-Host "Starting MCP Monitor Enhanced v2.0..." -ForegroundColor Green
Write-Host "Configuration: $ConfigPath" -ForegroundColor Gray
Write-Host ""
Start-Sleep -Seconds 1

try {
    while ($true) {
        # Process new events from log file
        if (-not $simulationMode) {
            $apiClient.ProcessEvents()
        }
        else {
            # Simulation: generate random events
            if ($iteration % 5 -eq 0) {
                $testEvent = $testTools | Get-Random
                $newEvent = New-TestEvent -api $testEvent.API -tool $testEvent.Tool
                & $eventHandler $newEvent
            }
        }
        
        # Render dashboard
        $dashboard.Render()
        
        # Send metrics to MCP server (if enabled)
        if ($iteration % 20 -eq 0 -and $mcpConfig.EnableRemoteLogging) {
            $summary = $statsAggregator.GetSummary()
            $apiClient.SendMetrics($summary)
        }
        
        # Check for Ctrl+C
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq [ConsoleKey]::C -and $key.Modifiers -eq [ConsoleModifiers]::Control) {
                & $cleanupHandler
            }
        }
        
        Start-Sleep -Seconds $dashboardConfig.RefreshIntervalSeconds
        $iteration++
    }
}
catch {
    Write-Host "`nError in main loop: $_" -ForegroundColor Red
    & $cleanupHandler
}
finally {
    & $cleanupHandler
}
