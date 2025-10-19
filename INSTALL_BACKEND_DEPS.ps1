# Install Backend Dependencies
# Installs or updates Python packages for the backend

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLING BACKEND DEPENDENCIES" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$BackendPath = Join-Path $PSScriptRoot "backend"
Write-Host "Changing to: $BackendPath" -ForegroundColor Gray
Set-Location -Path $BackendPath

# Check if venv exists
if (-Not (Test-Path "venv")) {
    Write-Host "Virtual environment not found!" -ForegroundColor Red
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$BackendPath\venv\Scripts\Activate.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Upgrade pip
Write-Host "📦 Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Warning: pip upgrade failed" -ForegroundColor Yellow
}

Write-Host ""

# Install dependencies
Write-Host "📦 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host ""

pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ All dependencies installed successfully!" -ForegroundColor Green
Write-Host ""

# Run basic tests
Write-Host "🧪 Running basic tests..." -ForegroundColor Yellow
Write-Host ""

python test_basic.py

$TestResult = $LASTEXITCODE

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 59 -ForegroundColor Cyan

if ($TestResult -eq 0) {
    Write-Host "🎉 INSTALLATION SUCCESSFUL!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Setup PostgreSQL database" -ForegroundColor White
    Write-Host "  2. Run: .\START_BACKEND.ps1" -ForegroundColor White
    Write-Host "  3. Open: http://localhost:8000/docs" -ForegroundColor White
} else {
    Write-Host "⚠️  INSTALLATION COMPLETED WITH WARNINGS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please check the test results above" -ForegroundColor Yellow
}

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 59 -ForegroundColor Cyan
