# Quality Check Script - Code Linters Setup & Execution
# Automatically installs and runs all configured linters
# Recommended by AI agents for automated code quality control

Write-Host "🔍 CODE QUALITY CHECK - LINTERS SETUP" -ForegroundColor Cyan
Write-Host "=" * 70

# Activate virtual environment
Write-Host "`n📦 Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Install dev dependencies if needed
Write-Host "`n📥 Checking dev dependencies..." -ForegroundColor Yellow
$packages = @("pylint", "mypy", "bandit", "pytest-cov", "pre-commit")
foreach ($package in $packages) {
    $installed = pip show $package 2>$null
    if (-not $installed) {
        Write-Host "  Installing $package..." -ForegroundColor Gray
        pip install $package --quiet
    }
    else {
        Write-Host "  ✓ $package already installed" -ForegroundColor Green
    }
}

Write-Host "`n" + ("=" * 70)
Write-Host "🔍 RUNNING CODE QUALITY CHECKS" -ForegroundColor Cyan
Write-Host "=" * 70

# Run Ruff (fast linter)
Write-Host "`n[1/5] 🚀 Ruff - Fast Python Linter" -ForegroundColor Yellow
Write-Host "Target: backend/ (E, F, I, UP, B, SIM rules)" -ForegroundColor Gray
ruff check backend --config pyproject.toml
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Ruff: PASSED" -ForegroundColor Green
}
else {
    Write-Host "✗ Ruff: ISSUES FOUND (see above)" -ForegroundColor Red
}

# Run Black (code formatter check)
Write-Host "`n[2/5] 🎨 Black - Code Formatter Check" -ForegroundColor Yellow
Write-Host "Target: backend/" -ForegroundColor Gray
black backend --check --diff --color 2>&1 | Select-Object -First 20
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Black: PASSED (code is formatted)" -ForegroundColor Green
}
else {
    Write-Host "✗ Black: FORMATTING NEEDED (run: black backend)" -ForegroundColor Red
}

# Run Mypy (type checker)
Write-Host "`n[3/5] 🔬 Mypy - Static Type Checker" -ForegroundColor Yellow
Write-Host "Target: backend/agents/ backend/api/ backend/monitoring/" -ForegroundColor Gray
mypy backend/agents backend/api backend/monitoring --config-file mypy.ini 2>&1 | Select-Object -First 30
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Mypy: PASSED (no type errors)" -ForegroundColor Green
}
else {
    Write-Host "⚠ Mypy: TYPE ISSUES FOUND (see above)" -ForegroundColor Yellow
}

# Run Bandit (security linter)
Write-Host "`n[4/5] 🔒 Bandit - Security Linter" -ForegroundColor Yellow
Write-Host "Target: backend/" -ForegroundColor Gray
bandit -r backend -c pyproject.toml --severity-level medium 2>&1 | Select-Object -First 25
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Bandit: PASSED (no security issues)" -ForegroundColor Green
}
else {
    Write-Host "⚠ Bandit: SECURITY ISSUES FOUND (see above)" -ForegroundColor Yellow
}

# Run Pylint (code quality - errors only for speed)
Write-Host "`n[5/5] 📊 Pylint - Code Quality Analyzer" -ForegroundColor Yellow
Write-Host "Target: backend/agents/ backend/api/ backend/monitoring/ (errors only)" -ForegroundColor Gray
pylint backend/agents backend/api backend/monitoring --rcfile .pylintrc --errors-only 2>&1 | Select-Object -First 30
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Pylint: PASSED (no critical errors)" -ForegroundColor Green
}
else {
    Write-Host "✗ Pylint: ERRORS FOUND (see above)" -ForegroundColor Red
}

# Summary
Write-Host "`n" + ("=" * 70)
Write-Host "📋 QUALITY CHECK SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 70
Write-Host "Ruff:   Fast linting for style & imports" -ForegroundColor Gray
Write-Host "Black:  Code formatting consistency" -ForegroundColor Gray
Write-Host "Mypy:   Static type checking" -ForegroundColor Gray
Write-Host "Bandit: Security vulnerability scanning" -ForegroundColor Gray
Write-Host "Pylint: Comprehensive code quality analysis" -ForegroundColor Gray

Write-Host "`n💡 TIP: Install pre-commit hooks with: pre-commit install" -ForegroundColor Cyan
Write-Host "   This will run these checks automatically before each commit!" -ForegroundColor Gray

Write-Host "`n✨ Quality check complete!" -ForegroundColor Green
