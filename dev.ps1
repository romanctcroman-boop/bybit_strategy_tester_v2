# ==============================================================================
# Bybit Strategy Tester v2 - Development Commands (PowerShell)
# ==============================================================================
# Usage: .\dev.ps1 <command>
# Example: .\dev.ps1 lint
# ==============================================================================

param(
    [Parameter(Position = 0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Continue"

function Show-Help {
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "         Bybit Strategy Tester v2 - Dev Commands                  " -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "DEVELOPMENT:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 install     - Install production dependencies"
    Write-Host "  .\dev.ps1 dev         - Install dev dependencies + pre-commit"
    Write-Host "  .\dev.ps1 run         - Start the application"
    Write-Host ""
    Write-Host "CODE QUALITY:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 lint        - Run ruff linter"
    Write-Host "  .\dev.ps1 format      - Format code with ruff"
    Write-Host "  .\dev.ps1 check       - Run all pre-commit hooks"
    Write-Host ""
    Write-Host "TESTING:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 test        - Run all tests"
    Write-Host "  .\dev.ps1 test-fast   - Run tests (skip slow)"
    Write-Host "  .\dev.ps1 test-cov    - Run tests with coverage"
    Write-Host ""
    Write-Host "DOCKER:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 docker      - Build Docker image"
    Write-Host "  .\dev.ps1 docker-run  - Run in Docker container"
    Write-Host ""
    Write-Host "MAINTENANCE:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 clean       - Remove cache and temp files"
    Write-Host ""
}

function Install-Deps {
    Write-Host "[*] Installing production dependencies..." -ForegroundColor Green
    pip install --upgrade pip
    pip install -r deployment/requirements-prod.txt
    Write-Host "[OK] Done!" -ForegroundColor Green
}

function Install-Dev {
    Install-Deps
    Write-Host "[*] Installing development dependencies..." -ForegroundColor Green
    pip install -r requirements-dev.txt
    pip install pre-commit ruff bandit mypy
    Write-Host "[*] Setting up pre-commit hooks..." -ForegroundColor Green
    pre-commit install
    Write-Host "[OK] Development environment ready!" -ForegroundColor Green
}

function Start-App {
    Write-Host "[*] Starting application..." -ForegroundColor Green
    & .\start_all.ps1
}

function Run-Lint {
    Write-Host "[*] Running ruff linter..." -ForegroundColor Yellow
    & .\.venv314\Scripts\ruff.exe check backend/ --fix
    Write-Host "[OK] Linting complete!" -ForegroundColor Green
}

function Run-Format {
    Write-Host "[*] Formatting code with ruff..." -ForegroundColor Yellow
    & .\.venv314\Scripts\ruff.exe format backend/
    Write-Host "[OK] Formatting complete!" -ForegroundColor Green
}

function Run-Check {
    Write-Host "[*] Running all pre-commit hooks..." -ForegroundColor Yellow
    pre-commit run --all-files
}

function Run-Tests {
    Write-Host "[*] Running tests..." -ForegroundColor Yellow
    pytest tests/ -v
}

function Run-TestsFast {
    Write-Host "[*] Running fast tests (skipping slow)..." -ForegroundColor Yellow
    pytest tests/ -v -m "not slow"
}

function Run-TestsCoverage {
    Write-Host "[*] Running tests with coverage..." -ForegroundColor Yellow
    pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing
    Write-Host "[*] Coverage report: htmlcov/index.html" -ForegroundColor Cyan
}

function Build-Docker {
    Write-Host "[*] Building Docker image..." -ForegroundColor Blue
    docker build -t bybit-strategy-tester:latest .
    Write-Host "[OK] Docker image built!" -ForegroundColor Green
}

function Run-Docker {
    Write-Host "[*] Running Docker container..." -ForegroundColor Blue
    docker run -p 8000:8000 --env-file .env bybit-strategy-tester:latest
}

function Clean-Project {
    Write-Host "[*] Cleaning project..." -ForegroundColor Yellow
    
    Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -File -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -File -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    $cacheDirs = @(".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov")
    foreach ($dir in $cacheDirs) {
        Get-ChildItem -Path . -Directory -Recurse -Filter $dir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "[OK] Cleanup complete!" -ForegroundColor Green
}

# ==============================================================================
# Main Execution
# ==============================================================================

switch ($Command) {
    "help" { Show-Help }
    "install" { Install-Deps }
    "dev" { Install-Dev }
    "run" { Start-App }
    "lint" { Run-Lint }
    "format" { Run-Format }
    "check" { Run-Check }
    "test" { Run-Tests }
    "test-fast" { Run-TestsFast }
    "test-cov" { Run-TestsCoverage }
    "docker" { Build-Docker }
    "docker-run" { Run-Docker }
    "clean" { Clean-Project }
    default { Show-Help }
}
