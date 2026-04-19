<#
.SYNOPSIS
  Start/stop/status for Redis server (optional service)

.DESCRIPTION
  Manages Redis server for caching, WebSocket, and Celery.
  Redis is OPTIONAL for local development but required for:
  - Live WebSocket trading
  - Celery background tasks
  - Production deployment

.EXAMPLE
  .\start_redis.ps1 start
  .\start_redis.ps1 status
  .\start_redis.ps1 stop
#>

param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('start', 'stop', 'status', 'check')]
    [string]$Action = 'check'
)

$RedisPort = 6379

function Test-RedisInstalled {
    # Check if redis-server is available
    $redis = Get-Command "redis-server" -ErrorAction SilentlyContinue
    if ($redis) {
        return $true
    }
    
    # Check common Windows Redis locations
    $commonPaths = @(
        "C:\Program Files\Redis\redis-server.exe",
        "C:\Redis\redis-server.exe",
        "$env:LOCALAPPDATA\Redis\redis-server.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            return $true
        }
    }
    
    return $false
}

function Test-RedisRunning {
    try {
        $connection = Get-NetTCPConnection -LocalPort $RedisPort -ErrorAction SilentlyContinue 2>$null
        return $null -ne $connection
    }
    catch {
        return $false
    }
}

function Get-RedisPath {
    $redis = Get-Command "redis-server" -ErrorAction SilentlyContinue
    if ($redis) {
        return $redis.Source
    }
    
    $commonPaths = @(
        "C:\Program Files\Redis\redis-server.exe",
        "C:\Redis\redis-server.exe",
        "$env:LOCALAPPDATA\Redis\redis-server.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    
    return $null
}

switch ($Action) {
    'check' {
        if (Test-RedisInstalled) {
            Write-Host "[OK] Redis is installed" -ForegroundColor Green
            if (Test-RedisRunning) {
                Write-Host "[OK] Redis is running on port $RedisPort" -ForegroundColor Green
            }
            else {
                Write-Host "[INFO] Redis is not running" -ForegroundColor Yellow
            }
            return
        }
        else {
            Write-Host "[INFO] Redis is not installed (optional for local development)" -ForegroundColor Yellow
            Write-Host "       Install from: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Gray
            return
        }
    }
    
    'start' {
        if (Test-RedisRunning) {
            Write-Host "[OK] Redis already running on port $RedisPort" -ForegroundColor Green
            return
        }
        
        $redisPath = Get-RedisPath
        if (-not $redisPath) {
            Write-Host "[SKIP] Redis not installed (optional service)" -ForegroundColor Yellow
            return
        }
        
        Write-Host "[INFO] Starting Redis server..." -ForegroundColor Cyan
        Start-Process -FilePath $redisPath -WindowStyle Hidden
        Start-Sleep -Seconds 2
        
        if (Test-RedisRunning) {
            Write-Host "[OK] Redis started on port $RedisPort" -ForegroundColor Green
        }
        else {
            Write-Host "[WARNING] Redis may have failed to start" -ForegroundColor Yellow
        }
    }
    
    'stop' {
        if (-not (Test-RedisRunning)) {
            Write-Host "[INFO] Redis is not running" -ForegroundColor Gray
            return
        }
        
        Write-Host "[INFO] Stopping Redis..." -ForegroundColor Yellow
        try {
            $connections = Get-NetTCPConnection -LocalPort $RedisPort -ErrorAction SilentlyContinue 2>$null
        }
        catch { $connections = $null }
        if ($connections) {
            foreach ($conn in $connections) {
                $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($process -and $process.ProcessName -like "*redis*") {
                    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                    Write-Host "[OK] Redis stopped (PID: $($process.Id))" -ForegroundColor Green
                }
            }
        }
    }
    
    'status' {
        if (Test-RedisRunning) {
            try {
                $connections = Get-NetTCPConnection -LocalPort $RedisPort -ErrorAction SilentlyContinue 2>$null
                $procId = $connections[0].OwningProcess
                Write-Host "[OK] Redis is running (PID: $procId, Port: $RedisPort)" -ForegroundColor Green
            }
            catch {
                Write-Host "[OK] Redis is running on port $RedisPort" -ForegroundColor Green
            }
        }
        else {
            Write-Host "[INFO] Redis is not running" -ForegroundColor Yellow
        }
    }
}
