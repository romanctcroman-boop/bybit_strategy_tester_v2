# Redis Cluster Setup Script for Windows
# ========================================
# 
# This script sets up a 6-node Redis Cluster (3 masters, 3 replicas)
# for high availability and horizontal scaling of TaskQueue
#
# Author: GitHub Copilot
# Date: November 5, 2025
# Reference: DEEPSEEK_PRODUCTION_RECOMMENDATIONS.md

param(
    [string]$RedisPath = "C:\Program Files\Redis",
    [string]$DataDir = "D:\redis_cluster_data",
    [int]$BasePort = 7000,
    [switch]$Clean,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

# Configuration
$Nodes = 6
$MasterCount = 3
$ReplicasPerMaster = 1

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Redis Cluster Setup Script" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check Redis installation
if (-not (Test-Path "$RedisPath\redis-server.exe")) {
    Write-Host "❌ Redis not found at: $RedisPath" -ForegroundColor Red
    Write-Host "Please install Redis or update RedisPath parameter" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Download from: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Redis found at: $RedisPath" -ForegroundColor Green

# Stop all nodes if requested
if ($Stop) {
    Write-Host ""
    Write-Host "🛑 Stopping all Redis Cluster nodes..." -ForegroundColor Yellow
    
    for ($i = 0; $i -lt $Nodes; $i++) {
        $port = $BasePort + $i
        
        try {
            $process = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | 
            Where-Object { $_.CommandLine -like "*$port*" }
            
            if ($process) {
                Stop-Process -Id $process.Id -Force
                Write-Host "  ✅ Stopped node on port $port" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "  ⚠️ Could not stop node on port $port" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    Write-Host "✅ All nodes stopped" -ForegroundColor Green
    exit 0
}

# Clean data directories if requested
if ($Clean) {
    Write-Host ""
    Write-Host "🧹 Cleaning cluster data..." -ForegroundColor Yellow
    
    if (Test-Path $DataDir) {
        Remove-Item -Path $DataDir -Recurse -Force
        Write-Host "  ✅ Removed data directory" -ForegroundColor Green
    }
    
    Write-Host ""
}

# Create data directories
Write-Host ""
Write-Host "📁 Creating data directories..." -ForegroundColor Cyan

for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeDir = "$DataDir\node_$port"
    
    if (-not (Test-Path $nodeDir)) {
        New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null
        Write-Host "  ✅ Created: $nodeDir" -ForegroundColor Green
    }
    else {
        Write-Host "  ℹ️ Exists: $nodeDir" -ForegroundColor Gray
    }
}

# Create Redis configuration files
Write-Host ""
Write-Host "⚙️ Creating configuration files..." -ForegroundColor Cyan

for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeDir = "$DataDir\node_$port"
    $configPath = "$nodeDir\redis.conf"
    
    $config = @"
# Redis Cluster Configuration - Node $port
# ==========================================

# Network
port $port
bind 127.0.0.1
protected-mode yes
tcp-backlog 511
timeout 0
tcp-keepalive 300

# General
daemonize no
supervised no
pidfile "$nodeDir/redis_$port.pid"
loglevel notice
logfile "$nodeDir/redis_$port.log"
databases 16

# Persistence
dir "$nodeDir"
dbfilename dump_$port.rdb

# AOF Persistence (for durability)
appendonly yes
appendfilename "appendonly_$port.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB Snapshots (for backup)
save 900 1      # After 900 sec if at least 1 key changed
save 300 10     # After 300 sec if at least 10 keys changed
save 60 10000   # After 60 sec if at least 10000 keys changed

# Cluster
cluster-enabled yes
cluster-config-file "$nodeDir/nodes_$port.conf"
cluster-node-timeout 5000
cluster-require-full-coverage yes

# Memory Management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Slow Log
slowlog-log-slower-than 10000
slowlog-max-len 128
"@

    $config | Out-File -FilePath $configPath -Encoding UTF8
    Write-Host "  ✅ Created config: redis_$port.conf" -ForegroundColor Green
}

# Start Redis nodes
Write-Host ""
Write-Host "🚀 Starting Redis nodes..." -ForegroundColor Cyan

$processes = @()

for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeDir = "$DataDir\node_$port"
    $configPath = "$nodeDir\redis.conf"
    
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "$RedisPath\redis-server.exe"
    $processInfo.Arguments = "`"$configPath`""
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    
    try {
        $process = [System.Diagnostics.Process]::Start($processInfo)
        $processes += $process
        Write-Host "  ✅ Started node on port $port (PID: $($process.Id))" -ForegroundColor Green
        Start-Sleep -Milliseconds 500
    }
    catch {
        Write-Host "  ❌ Failed to start node on port $port" -ForegroundColor Red
        Write-Host "     Error: $_" -ForegroundColor Red
    }
}

# Wait for nodes to start
Write-Host ""
Write-Host "⏳ Waiting for nodes to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Verify nodes are running
Write-Host ""
Write-Host "🔍 Verifying nodes..." -ForegroundColor Cyan

$allRunning = $true
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    
    try {
        $result = & "$RedisPath\redis-cli.exe" -p $port ping 2>$null
        if ($result -eq "PONG") {
            Write-Host "  ✅ Node $port is responding" -ForegroundColor Green
        }
        else {
            Write-Host "  ❌ Node $port is not responding" -ForegroundColor Red
            $allRunning = $false
        }
    }
    catch {
        Write-Host "  ❌ Node $port is not responding" -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Host ""
    Write-Host "❌ Some nodes failed to start. Check logs in: $DataDir" -ForegroundColor Red
    exit 1
}

# Create cluster
Write-Host ""
Write-Host "🔗 Creating Redis Cluster..." -ForegroundColor Cyan
Write-Host "   Cluster configuration: $MasterCount masters, $ReplicasPerMaster replicas per master" -ForegroundColor Gray

$nodeAddresses = @()
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeAddresses += "127.0.0.1:$port"
}

$clusterCmd = "$RedisPath\redis-cli.exe --cluster create $($nodeAddresses -join ' ') --cluster-replicas $ReplicasPerMaster --cluster-yes"

Write-Host ""
Write-Host "Executing: $clusterCmd" -ForegroundColor Gray
Write-Host ""

try {
    Invoke-Expression $clusterCmd
    Write-Host ""
    Write-Host "✅ Cluster created successfully!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "❌ Failed to create cluster" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual command:" -ForegroundColor Yellow
    Write-Host $clusterCmd -ForegroundColor Cyan
    exit 1
}

# Verify cluster status
Write-Host ""
Write-Host "🔍 Verifying cluster status..." -ForegroundColor Cyan

try {
    $clusterInfo = & "$RedisPath\redis-cli.exe" -p $BasePort cluster info
    
    Write-Host ""
    Write-Host "Cluster Info:" -ForegroundColor Gray
    Write-Host $clusterInfo
    
    Write-Host ""
    Write-Host "Cluster Nodes:" -ForegroundColor Gray
    & "$RedisPath\redis-cli.exe" -p $BasePort cluster nodes
    
}
catch {
    Write-Host "⚠️ Could not retrieve cluster status" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "✅ Redis Cluster Setup Complete!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "Cluster Configuration:" -ForegroundColor Cyan
Write-Host "  Masters:  $MasterCount" -ForegroundColor White
Write-Host "  Replicas: $($MasterCount * $ReplicasPerMaster)" -ForegroundColor White
Write-Host "  Total:    $Nodes nodes" -ForegroundColor White
Write-Host ""
Write-Host "Connection Endpoints:" -ForegroundColor Cyan
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $role = if ($i -lt $MasterCount) { "MASTER" } else { "REPLICA" }
    Write-Host "  Node $($i+1): 127.0.0.1:$port ($role)" -ForegroundColor White
}
Write-Host ""
Write-Host "Data Directory: $DataDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  Connect:      redis-cli -c -p $BasePort" -ForegroundColor Gray
Write-Host "  Status:       redis-cli -p $BasePort cluster info" -ForegroundColor Gray
Write-Host "  Nodes:        redis-cli -p $BasePort cluster nodes" -ForegroundColor Gray
Write-Host "  Stop All:     .\setup_redis_cluster.ps1 -Stop" -ForegroundColor Gray
Write-Host "  Clean and Restart: .\setup_redis_cluster.ps1 -Clean" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Update TaskQueue connection URL to cluster nodes" -ForegroundColor White
Write-Host "  2. Test failover: Stop a master node and verify replica promotion" -ForegroundColor White
Write-Host "  3. Run integration tests against cluster" -ForegroundColor White
Write-Host ""
