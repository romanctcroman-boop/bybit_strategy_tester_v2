# Build Docker Sandbox Image
# Usage: .\scripts\build_sandbox.ps1

param(
    [string]$ImageName = "bybit-sandbox:latest",
    [switch]$NoBuildCache = $false,
    [switch]$Verbose = $false
)

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  Building Sandbox Docker Image" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon not responding"
    }
    Write-Host "✓ Docker is running (version: $dockerVersion)" -ForegroundColor Green
}
catch {
    Write-Host "✗ Docker is not running or not installed" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Get project root
$projectRoot = Split-Path -Parent $PSScriptRoot
Write-Host "Project root: $projectRoot" -ForegroundColor Gray

# Check if Dockerfile exists
$dockerfilePath = Join-Path $projectRoot "docker\Dockerfile.sandbox"
if (-not (Test-Path $dockerfilePath)) {
    Write-Host "✗ Dockerfile not found: $dockerfilePath" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Dockerfile found: $dockerfilePath" -ForegroundColor Green

# Check if requirements file exists
$requirementsPath = Join-Path $projectRoot "docker\sandbox-requirements.txt"
if (-not (Test-Path $requirementsPath)) {
    Write-Host "✗ Requirements file not found: $requirementsPath" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Requirements file found: $requirementsPath" -ForegroundColor Green

Write-Host ""
Write-Host "Building image: $ImageName" -ForegroundColor Cyan

# Build command
$buildArgs = @(
    "build",
    "-f", $dockerfilePath,
    "-t", $ImageName
)

if ($NoBuildCache) {
    $buildArgs += "--no-cache"
    Write-Host "  (no cache)" -ForegroundColor Gray
}

if ($Verbose) {
    $buildArgs += "--progress=plain"
}

$buildArgs += $projectRoot

Write-Host "Command: docker $($buildArgs -join ' ')" -ForegroundColor Gray
Write-Host ""

# Execute build
$startTime = Get-Date
try {
    & docker @buildArgs
    
    if ($LASTEXITCODE -eq 0) {
        $duration = (Get-Date) - $startTime
        Write-Host ""
        Write-Host "=====================================================================" -ForegroundColor Green
        Write-Host "  ✓ Image built successfully in $($duration.TotalSeconds) seconds" -ForegroundColor Green
        Write-Host "=====================================================================" -ForegroundColor Green
        
        # Display image info
        Write-Host ""
        Write-Host "Image details:" -ForegroundColor Cyan
        docker images $ImageName --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedAt}}"
        
        # Test image
        Write-Host ""
        Write-Host "Testing image..." -ForegroundColor Yellow
        $testOutput = docker run --rm $ImageName python -c "import numpy, pandas, ta; print('OK')" 2>&1
        
        if ($testOutput -match "OK") {
            Write-Host "✓ Image test passed" -ForegroundColor Green
        }
        else {
            Write-Host "⚠ Image test failed: $testOutput" -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Run tests: pytest tests/integration/test_sandbox_executor.py -v" -ForegroundColor White
        Write-Host "  2. Manual test: python scripts/test_sandbox.py" -ForegroundColor White
        Write-Host "  3. Use in code: from backend.services.sandbox_executor import execute_code_in_sandbox" -ForegroundColor White
        
    }
    else {
        throw "Build failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Red
    Write-Host "  ✗ Build failed: $_" -ForegroundColor Red
    Write-Host "=====================================================================" -ForegroundColor Red
    exit 1
}
