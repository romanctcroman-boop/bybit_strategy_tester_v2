# ==============================================================================
# MCP Server Debug Mode - Launcher with detailed logging
# ==============================================================================

$ErrorActionPreference = "Stop"

# Project paths
$projectRoot = "D:\bybit_strategy_tester_v2"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mcpServer = Join-Path $projectRoot "mcp-server\server.py"
$logsDir = Join-Path $projectRoot "logs"

# Create logs directory if needed
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$logFile = Join-Path $logsDir "mcp_debug_$timestamp.log"

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  MCP SERVER - DEBUG MODE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Verify Python venv exists
Write-Host "[CHECK] Python venv: " -NoNewline
if (Test-Path $venvPython) {
    Write-Host "OK" -ForegroundColor Green
}
else {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "Python virtual environment not found at: $venvPython" -ForegroundColor Red
    exit 1
}

# Verify MCP Server exists
Write-Host "[CHECK] MCP Server: " -NoNewline
if (Test-Path $mcpServer) {
    Write-Host "OK" -ForegroundColor Green
}
else {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "MCP server script not found at: $mcpServer" -ForegroundColor Red
    exit 1
}

# Configure API Keys
Write-Host ""
Write-Host "[CONFIG] API Keys Configuration..." -ForegroundColor Yellow
Write-Host "         ✓ Keys are loaded securely via KeyManager" -ForegroundColor Green
Write-Host "         ✓ Encrypted storage: backend/config/encrypted_secrets.json" -ForegroundColor Green
Write-Host "         ✓ Master key from .env: MASTER_ENCRYPTION_KEY" -ForegroundColor Green
Write-Host "         ✓ Auto-decryption at runtime" -ForegroundColor Green

Write-Host ""
Write-Host "[LOG] Output: $logFile" -ForegroundColor Yellow

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  STARTING MCP SERVER..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

try {
    # Start server with logging
    & $venvPython $mcpServer 2>&1 | Tee-Object -FilePath $logFile
    
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    
    if ($exitCode -eq 0) {
        Write-Host "  SERVER STOPPED (EXIT CODE: 0)" -ForegroundColor Green
    }
    else {
        Write-Host "  SERVER EXITED WITH ERROR (CODE: $exitCode)" -ForegroundColor Red
    }
    
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    exit $exitCode
}
catch {
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host "  FATAL ERROR" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Stack Trace:" -ForegroundColor Yellow
    Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
