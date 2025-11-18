# Simple Redis Cluster Setup for Windows
# Quick setup script for development/testing

param(
    [switch]$Stop
)

$BasePort = 7000
$Nodes = 6

if ($Stop) {
    Write-Host "Stopping all Redis nodes..." -ForegroundColor Yellow
    Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "Done" -ForegroundColor Green
    exit 0
}

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "Redis Cluster Quick Setup" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Redis
$RedisPath = "C:\Program Files\Redis"
if (-not (Test-Path "$RedisPath\redis-server.exe")) {
    Write-Host "ERROR: Redis not found at: $RedisPath" -ForegroundColor Red
    Write-Host "Please install Redis first" -ForegroundColor Yellow
    exit 1
}

Write-Host "Redis found: $RedisPath" -ForegroundColor Green
Write-Host ""

# Create data directory
$DataDir = "D:\redis_cluster_data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

# Create node directories and configs
Write-Host "Creating node configurations..." -ForegroundColor Cyan
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeDir = "$DataDir\node_$port"
    
    New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null
    
    $config = @"
port $port
cluster-enabled yes
cluster-config-file nodes.conf
cluster-node-timeout 5000
appendonly yes
dir $nodeDir
logfile $nodeDir\redis.log
"@
    
    $config | Out-File -FilePath "$nodeDir\redis.conf" -Encoding ASCII
    Write-Host "  Created node $port configuration" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Starting Redis nodes..." -ForegroundColor Cyan

# Start all nodes
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodeDir = "$DataDir\node_$port"
    
    Start-Process -FilePath "$RedisPath\redis-server.exe" -ArgumentList "$nodeDir\redis.conf" -WindowStyle Hidden
    Write-Host "  Started node on port $port" -ForegroundColor Gray
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "Waiting for nodes to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Create cluster
Write-Host ""
Write-Host "Creating cluster..." -ForegroundColor Cyan

$nodes = @()
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    $nodes += "127.0.0.1:$port"
}

$clusterCmd = "& `"$RedisPath\redis-cli.exe`" --cluster create $($nodes -join ' ') --cluster-replicas 1 --cluster-yes"
Invoke-Expression $clusterCmd

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "Redis Cluster Setup Complete!" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Cluster nodes:" -ForegroundColor Cyan
for ($i = 0; $i -lt $Nodes; $i++) {
    $port = $BasePort + $i
    Write-Host "  127.0.0.1:$port" -ForegroundColor White
}
Write-Host ""
Write-Host "Test connection:" -ForegroundColor Cyan
Write-Host "  redis-cli -c -p $BasePort" -ForegroundColor Gray
Write-Host ""
Write-Host "Stop all nodes:" -ForegroundColor Cyan
Write-Host "  .\setup_redis_cluster_simple.ps1 -Stop" -ForegroundColor Gray
Write-Host ""
