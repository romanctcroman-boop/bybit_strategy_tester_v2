# Production Deployment Script for Windows
# Usage: .\deploy.ps1 -Action start|stop|deploy|status
# Example: .\deploy.ps1 -Action start

param(
    [ValidateSet('preflight', 'deploy', 'start', 'stop', 'status', 'restart')]
    [string]$Action = 'status',
    
    [ValidateSet('development', 'production')]
    [string]$Environment = 'production'
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Colors
function Write-Success {
    Write-Host "[SUCCESS] $args" -ForegroundColor Green
}

function Write-Error-Custom {
    Write-Host "[ERROR] $args" -ForegroundColor Red
}

function Write-Info {
    Write-Host "[INFO] $args" -ForegroundColor Blue
}

function Write-Warning-Custom {
    Write-Host "[WARNING] $args" -ForegroundColor Yellow
}

# ============================================
# Pre-flight Checks
# ============================================
function Invoke-PreflightChecks {
    Write-Info "Running pre-flight checks..."
    
    # Check Docker
    try {
        $dockerVersion = docker --version
        Write-Success "Docker found: $dockerVersion"
    }
    catch {
        Write-Error-Custom "Docker is not installed or not in PATH"
        return $false
    }
    
    # Check Docker Desktop
    if (-not (Get-Process | Where-Object { $_.Name -eq 'Docker' })) {
        Write-Warning-Custom "Docker Desktop may not be running"
    }
    
    # Check .env file
    if (-not (Test-Path "$ProjectRoot\.env.production")) {
        Write-Error-Custom ".env.production file not found"
        return $false
    }
    Write-Success ".env.production file found"
    
    # Check requirements files
    if (-not (Test-Path "$ProjectRoot\requirements-dev.txt")) {
        Write-Error-Custom "requirements-dev.txt not found"
        return $false
    }
    Write-Success "requirements-dev.txt found"
    
    Write-Success "All pre-flight checks passed!"
    return $true
}

# ============================================
# Deploy Monitoring Stack
# ============================================
function Deploy-MonitoringStack {
    Write-Info "Deploying monitoring stack..."
    
    Push-Location "$ProjectRoot\deployment"
    
    # Create config directories
    New-Item -ItemType Directory -Force -Path "config\grafana\provisioning\dashboards" | Out-Null
    New-Item -ItemType Directory -Force -Path "config\grafana\provisioning\datasources" | Out-Null
    
    # Start monitoring services
    Write-Info "Starting Docker containers..."
    docker-compose -f docker-compose-monitoring.yml up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Monitoring stack deployed"
    }
    else {
        Write-Error-Custom "Failed to deploy monitoring stack"
        Pop-Location
        return $false
    }
    
    # Wait for services
    Write-Info "Waiting 15 seconds for services to initialize..."
    Start-Sleep -Seconds 15
    
    # Check services
    $containers = docker ps --format "{{.Names}}"
    
    if ($containers -match "elasticsearch-prod") {
        Write-Success "Elasticsearch is running"
    }
    
    if ($containers -match "prometheus-prod") {
        Write-Success "Prometheus is running"
    }
    
    if ($containers -match "grafana-prod") {
        Write-Success "Grafana is running"
    }
    
    Pop-Location
    return $true
}

# ============================================
# Deploy Application
# ============================================
function Deploy-Application {
    Write-Info "Deploying application..."
    
    Push-Location $ProjectRoot
    
    # Copy production env
    Copy-Item ".env.production" ".env" -Force
    Write-Success "Environment file configured"
    
    # Create directories
    New-Item -ItemType Directory -Force -Path "logs" | Out-Null
    New-Item -ItemType Directory -Force -Path "data" | Out-Null
    Write-Success "Directories created"
    
    # Install Python dependencies
    Write-Info "Installing Python dependencies..."
    $pythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
    
    if (Test-Path $pythonExe) {
        & $pythonExe -m pip install -q --upgrade pip
        & $pythonExe -m pip install -q -r requirements-dev.txt
        Write-Success "Python dependencies installed"
    }
    else {
        Write-Error-Custom "Python virtual environment not found"
        Pop-Location
        return $false
    }
    
    Pop-Location
    return $true
}

# ============================================
# Health Check
# ============================================
function Invoke-HealthCheck {
    Write-Info "Performing health checks..."
    
    $failed = 0
    
    # Check API
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "API health check passed"
        }
    }
    catch {
        Write-Error-Custom "API health check failed"
        $failed++
    }
    
    # Check Prometheus
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "Prometheus health check passed"
        }
    }
    catch {
        Write-Warning-Custom "Prometheus health check failed"
        $failed++
    }
    
    # Check Grafana
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "Grafana health check passed"
        }
    }
    catch {
        Write-Warning-Custom "Grafana health check failed"
        $failed++
    }
    
    # Check Elasticsearch
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9200/" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "Elasticsearch health check passed"
        }
    }
    catch {
        Write-Warning-Custom "Elasticsearch health check failed"
        $failed++
    }
    
    return $failed
}

# ============================================
# Show Status
# ============================================
function Show-Status {
    Write-Info "System Status"
    
    Write-Host ""
    Write-Host "Docker Containers:" -ForegroundColor Cyan
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    Write-Host ""
    Write-Host "Services URLs:" -ForegroundColor Cyan
    Write-Host "  API:        http://localhost:8000"
    Write-Host "  Prometheus: http://localhost:9090"
    Write-Host "  Grafana:    http://localhost:3000 (admin/changeme)"
    Write-Host "  Kibana:     http://localhost:5601"
    Write-Host "  Alertmanager: http://localhost:9093"
    
    Write-Host ""
    Write-Host "Database:" -ForegroundColor Cyan
    Write-Host "  SQLite: $ProjectRoot\data.sqlite3"
    Write-Host "  Redis:  localhost:6379"
    
    Write-Host ""
    Write-Host "Logs:" -ForegroundColor Cyan
    Get-ChildItem "$ProjectRoot\logs" -File | ForEach-Object {
        Write-Host "  $($_.Name) ($((Get-Item $_).Length | Format-FileSize))"
    }
}

# ============================================
# Start Services (PowerShell Tasks)
# ============================================
function Start-ApplicationServices {
    Write-Info "Starting application services via VS Code tasks..."
    
    # These should be already started by VS Code tasks
    # Just verify they're running
    Start-Sleep -Seconds 3
    
    Invoke-HealthCheck | Out-Null
}

# ============================================
# Stop Services
# ============================================
function Stop-AllServices {
    Write-Info "Stopping all services..."
    
    # Stop monitoring stack
    Push-Location "$ProjectRoot\deployment"
    Write-Info "Stopping monitoring stack..."
    docker-compose -f docker-compose-monitoring.yml down
    Pop-Location
    Write-Success "Monitoring stack stopped"
    
    # Try to stop API (if running in background)
    Get-Process | Where-Object { $_.ProcessName -match "python" -and $_.CommandLine -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Try to stop AI Agent
    Get-Process | Where-Object { $_.ProcessName -match "python" -and $_.CommandLine -match "agent_background_service" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

# ============================================
# Main
# ============================================
function Main {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  Bybit Strategy Tester - Production Deployment" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Environment: $Environment"
    Write-Host "Action: $Action"
    Write-Host ""
    
    switch ($Action) {
        'preflight' {
            Invoke-PreflightChecks
        }
        
        'deploy' {
            if (Invoke-PreflightChecks) {
                if (Deploy-MonitoringStack) {
                    if (Deploy-Application) {
                        Invoke-HealthCheck | Out-Null
                        Write-Success "Deployment completed!"
                    }
                }
            }
        }
        
        'start' {
            Start-ApplicationServices
            Show-Status
        }
        
        'stop' {
            Stop-AllServices
        }
        
        'status' {
            Show-Status
            Invoke-HealthCheck | Out-Null
        }
        
        'restart' {
            Stop-AllServices
            Start-Sleep -Seconds 5
            Start-ApplicationServices
            Show-Status
        }
        
        default {
            Write-Error-Custom "Unknown action: $Action"
        }
    }
    
    Write-Host ""
}

# Helper function to format file size
function Format-FileSize {
    param([int64]$Size)
    
    switch ($Size) {
        { $_ -gt 1GB } { "{0:N2} GB" -f ($_ / 1GB); break }
        { $_ -gt 1MB } { "{0:N2} MB" -f ($_ / 1MB); break }
        { $_ -gt 1KB } { "{0:N2} KB" -f ($_ / 1KB); break }
        default { "{0} B" -f $_ }
    }
}

# Run main
Main

