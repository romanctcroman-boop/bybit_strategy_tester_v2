# Bybit Strategy Tester v2 - Dev script (Windows PowerShell)
# Usage: .\dev.ps1 <command>
# Commands: run, lint, format, test, test-cov, clean, mypy, help

param(
    [Parameter(Position = 0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Invoke-Run {
    Set-Location $ProjectRoot
    & py -3.14 -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
}

function Invoke-Lint {
    Set-Location $ProjectRoot
    & py -3.14 -m ruff check . --fix
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Format {
    Set-Location $ProjectRoot
    & py -3.14 -m ruff format .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Test {
    Set-Location $ProjectRoot
    & py -3.14 -m pytest tests/ -v --tb=short
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-TestCov {
    Set-Location $ProjectRoot
    & py -3.14 -m pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Clean {
    Set-Location $ProjectRoot
    $dirs = @(".pytest_cache", ".ruff_cache", "*.egg-info", "dist", "build", "htmlcov", ".coverage")
    foreach ($d in $dirs) {
        if (Test-Path $d) {
            Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
            Write-Host "Removed $d"
        }
    }
    Write-Host "Clean done."
}

function Invoke-Mypy {
    Set-Location $ProjectRoot
    & py -3.14 -m mypy backend/ --no-error-summary 2>&1
    exit $LASTEXITCODE
}

function Show-Help {
    Write-Host @"
Bybit Strategy Tester v2 - Dev commands

Usage: .\dev.ps1 <command>

Commands:
  run       Start API server (uvicorn, port 8000, reload)
  lint      Run ruff check --fix
  format    Run ruff format
  test      Run pytest tests/
  test-cov  Run pytest with coverage
  clean     Remove .pytest_cache, .ruff_cache, htmlcov, etc.
  mypy      Run mypy on backend/
  help      Show this help

Python: py -3.14 (or interpreter from pyproject.toml)
"@
}

switch ($Command.ToLower()) {
    "run"      { Invoke-Run }
    "lint"     { Invoke-Lint }
    "format"   { Invoke-Format }
    "test"     { Invoke-Test }
    "test-cov" { Invoke-TestCov }
    "clean"    { Invoke-Clean }
    "mypy"     { Invoke-Mypy }
    "help"     { Show-Help }
    default    { Write-Host "Unknown command: $Command"; Show-Help; exit 1 }
}
