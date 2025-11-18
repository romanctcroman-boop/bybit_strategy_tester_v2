# Quality Check Script - Code Linters Setup & Execution
Write-Host "CODE QUALITY CHECK - LINTERS SETUP" -ForegroundColor Cyan
Write-Host "======================================================================"

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "RUNNING CODE QUALITY CHECKS" -ForegroundColor Cyan
Write-Host "======================================================================"

# Run Ruff
Write-Host ""
Write-Host "[1/5] Ruff - Fast Python Linter" -ForegroundColor Yellow
ruff check backend --config pyproject.toml
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASSED: Ruff" -ForegroundColor Green
}
else {
    Write-Host "ISSUES: Ruff found problems" -ForegroundColor Red
}

# Run Black
Write-Host ""
Write-Host "[2/5] Black - Code Formatter Check" -ForegroundColor Yellow
black backend --check --diff --color
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASSED: Black" -ForegroundColor Green
}
else {
    Write-Host "ISSUES: Black found formatting problems" -ForegroundColor Red
}

# Run Mypy
Write-Host ""
Write-Host "[3/5] Mypy - Static Type Checker" -ForegroundColor Yellow
mypy backend/agents backend/api backend/monitoring --config-file mypy.ini
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASSED: Mypy" -ForegroundColor Green
}
else {
    Write-Host "ISSUES: Mypy found type problems" -ForegroundColor Yellow
}

# Run Bandit
Write-Host ""
Write-Host "[4/5] Bandit - Security Linter" -ForegroundColor Yellow
bandit -r backend -c pyproject.toml --severity-level medium
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASSED: Bandit" -ForegroundColor Green
}
else {
    Write-Host "ISSUES: Bandit found security problems" -ForegroundColor Yellow
}

# Run Pylint
Write-Host ""
Write-Host "[5/5] Pylint - Code Quality Analyzer" -ForegroundColor Yellow
pylint backend/agents backend/api backend/monitoring --rcfile .pylintrc --errors-only
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASSED: Pylint" -ForegroundColor Green
}
else {
    Write-Host "ISSUES: Pylint found errors" -ForegroundColor Red
}

Write-Host ""
Write-Host "======================================================================"
Write-Host "QUALITY CHECK COMPLETE" -ForegroundColor Green
Write-Host "======================================================================"
Write-Host "TIP: Install pre-commit hooks with: pre-commit install" -ForegroundColor Cyan
