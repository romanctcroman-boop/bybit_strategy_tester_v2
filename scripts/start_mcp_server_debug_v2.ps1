# Start Perplexity MCP Server - DEBUG MODE
# This script launches the MCP server with verbose console output for debugging
# Use start_mcp_server.ps1 for production (clean stdio for JSON-RPC)

# Set error action preference
$ErrorActionPreference = "Stop"

# Set project root
$projectRoot = "D:\bybit_strategy_tester_v2"
$venvPython = "$projectRoot\.venv\Scripts\python.exe"
$mcpServer = "$projectRoot\mcp-server\server.py"

# Ensure logs directory exists
$logsDir = "$projectRoot\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

# Console output for debugging
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  MCP SERVER - DEBUG MODE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
Write-Host "[CHECK] Python venv: " -NoNewline
if (-not (Test-Path $venvPython)) {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "        Path not found: $venvPython" -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green
Write-Host "        $venvPython" -ForegroundColor Gray

# Check if MCP server script exists
Write-Host "[CHECK] MCP Server: " -NoNewline
if (-not (Test-Path $mcpServer)) {
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "        Path not found: $mcpServer" -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green
Write-Host "        $mcpServer" -ForegroundColor Gray

# Set environment variables
Write-Host ""
Write-Host "[CONFIG] Setting environment variables..." -ForegroundColor Yellow
$env:PERPLEXITY_API_KEY = "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"
$env:DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"

Write-Host "         PERPLEXITY_API_KEY: " -NoNewline -ForegroundColor Gray
Write-Host "pplx-FSlOe...hTF2R" -ForegroundColor Green
Write-Host "         DEEPSEEK_API_KEY: " -NoNewline -ForegroundColor Gray
Write-Host "sk-1630f...37242" -ForegroundColor Green

# Create new log file with timestamp
$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$sessionLog = "$projectRoot\logs\mcp_debug_$timestamp.log"

Write-Host ""
Write-Host "[LOG] Output will be saved to:" -ForegroundColor Yellow
Write-Host "      $sessionLog" -ForegroundColor Gray

try {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Starting MCP server (DEBUG MODE)" | Out-File -FilePath $sessionLog -Force
}
catch {}

# Launch MCP server with Tee-Object for console + file output
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  STARTING MCP SERVER..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

try {
    & $venvPython $mcpServer 2>&1 | Tee-Object -FilePath $sessionLog
    
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    
    if ($exitCode -eq 0) {
        Write-Host "  SERVER STOPPED NORMALLY" -ForegroundColor Green
    }
    else {
        Write-Host "  SERVER EXITED WITH ERROR (CODE: $exitCode)" -ForegroundColor Red
    }
    
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[LOG] Full log saved to: $sessionLog" -ForegroundColor Yellow
    
    exit $exitCode
    
}
catch {
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host "  FATAL ERROR" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "[LOG] Error log saved to: $sessionLog" -ForegroundColor Yellow
    
    exit 1
}
