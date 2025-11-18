# PM2 Full Autostart Script (PowerShell)
# This script starts PM2 daemon and resurrects saved processes

# Set error handling
$ErrorActionPreference = "Continue"

# Log file path
$LogFile = "D:\bybit_strategy_tester_v2\logs\pm2_autostart.log"

# Create logs directory if not exists
$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Function to write log
function Write-Log {
    param($Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] $Message"
    Add-Content -Path $LogFile -Value $LogMessage
    Write-Host $LogMessage
}

Write-Log "=== PM2 Autostart Script Started ==="

# Add npm to PATH
$env:PATH += ";C:\Users\roman\AppData\Roaming\npm"
Write-Log "PATH updated with npm location"

# Wait for system to stabilize
Write-Log "Waiting 10 seconds for system to stabilize..."
Start-Sleep -Seconds 10

# Check if PM2 is available
try {
    $pm2Version = & pm2 --version 2>&1
    Write-Log "PM2 version: $pm2Version"
}
catch {
    Write-Log "ERROR: PM2 not found in PATH"
    exit 1
}

# Ping PM2 daemon
Write-Log "Pinging PM2 daemon..."
& pm2 ping 2>&1 | Out-Null

# Resurrect saved processes
Write-Log "Resurrecting saved PM2 processes..."
$ResurrectOutput = & pm2 resurrect 2>&1 | Out-String
Write-Log "Resurrect output:"
Write-Log $ResurrectOutput

# Get process list
$ProcessList = & pm2 list 2>&1 | Out-String
Write-Log "Current process list:"
Write-Log $ProcessList

Write-Log "=== PM2 Autostart Script Completed ==="
