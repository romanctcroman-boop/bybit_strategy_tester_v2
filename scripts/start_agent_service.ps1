# ============================================
# AI Agent Service Launcher
# ============================================
# Wrapper script to run the AI Agent Service
# Redirects stderr to prevent PowerShell from treating logs as errors
# ============================================

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# Set UTF-8 encoding for proper emoji display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

Write-Host "Starting AI Agent Service..." -ForegroundColor Cyan
Write-Host "Python: $VenvPython" -ForegroundColor Gray

# Change to project root
Set-Location $ProjectRoot

# Run the service, redirecting stderr to stdout to prevent false errors
# The agent uses loguru which outputs to stderr by default
try {
    & $VenvPython -m backend.agents.agent_background_service 2>&1 | ForEach-Object {
        # Output each line (including what was stderr)
        Write-Host $_
    }
}
catch {
    Write-Host "Agent service stopped: $_" -ForegroundColor Yellow
}

# Keep window open on exit for debugging
Write-Host ""
Write-Host "Agent service has stopped." -ForegroundColor Yellow

# DEV MODE: Auto-close after 3 seconds (remove this block for production)
Write-Host "Press Enter to close (auto-closing in 3 sec)..." -ForegroundColor DarkGray
$timeout = 3
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
while ($stopwatch.Elapsed.TotalSeconds -lt $timeout) {
    if ([Console]::KeyAvailable) {
        [Console]::ReadKey($true) | Out-Null
        break
    }
    Start-Sleep -Milliseconds 100
}
