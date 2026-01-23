<#
Clean local build/test artifacts to keep the repo tidy (does NOT touch tracked source).

What it removes (recursively from repo root):
- __pycache__/ directories
- *.pyc, *.pyo, *.pyd
- .pytest_cache/
- .ruff_cache/
- htmlcov/
- coverage.xml (optional)
- logs/ directories
- marimo/_static/, marimo/_lsp/, __marimo__/

Exclusions:
- Skips the nested repo 'mcp-server' entirely.

Usage (PowerShell):
  pwsh -File scripts/clean_workspace.ps1
#>

$ErrorActionPreference = 'SilentlyContinue'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

$excludeDirs = @('mcp-server')

function Test-ShouldSkip($path) {
    foreach ($ex in $excludeDirs) {
        if ($path -like (Join-Path $repoRoot "$ex*")) { return $true }
    }
    return $false
}

# Remove __pycache__
Get-ChildItem -Path $repoRoot -Directory -Recurse -Force -Filter '__pycache__' | Where-Object { -not (Test-ShouldSkip $_.FullName) } | ForEach-Object { Remove-Item $_.FullName -Recurse -Force }

# Remove Python bytecode
Get-ChildItem -Path $repoRoot -Recurse -Force -Include *.pyc, *.pyo, *.pyd | Where-Object { -not (Test-ShouldSkip $_.DirectoryName) } | Remove-Item -Force

# Remove pytest/ruff caches
@('.pytest_cache', '.ruff_cache', 'htmlcov') | ForEach-Object {
    Get-ChildItem -Path $repoRoot -Directory -Recurse -Force -Filter $_ |
    Where-Object { -not (Test-ShouldSkip $_.FullName) } |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
}

# Remove common logs directories
Get-ChildItem -Path $repoRoot -Directory -Recurse -Force -Filter 'logs' | Where-Object { -not (Test-ShouldSkip $_.FullName) } | ForEach-Object { Remove-Item $_.FullName -Recurse -Force }

# Optional single files
@('coverage.xml') | ForEach-Object {
    Get-ChildItem -Path $repoRoot -Recurse -Force -Filter $_ |
    Where-Object { -not (Test-ShouldSkip $_.DirectoryName) } |
    Remove-Item -Force
}

# Marimo artifacts
@('marimo/_static', 'marimo/_lsp', '__marimo__') | ForEach-Object {
    $p = Join-Path $repoRoot $_
    if (Test-Path $p -and -not (Test-ShouldSkip $p)) { Remove-Item $p -Recurse -Force }
}

Write-Host "Workspace cleanup complete." -ForegroundColor Green
