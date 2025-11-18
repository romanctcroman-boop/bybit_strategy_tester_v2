# Start Perplexity MCP Server
# This script launches the MCP server for Perplexity AI integration
# IMPORTANT: Minimal output to avoid stdio interference with JSON-RPC

# Set error action preference
$ErrorActionPreference = "Stop"

# Set project root
$projectRoot = "D:\bybit_strategy_tester_v2"
$venvPython = "$projectRoot\.venv\Scripts\python.exe"
$mcpServer = "$projectRoot\mcp-server\server.py"
$logFile = "$projectRoot\logs\mcp_server.log"

# Ensure logs directory exists
$logsDir = "$projectRoot\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

# Check if venv exists (log to file, not console)
if (-not (Test-Path $venvPython)) {
    try {
        "ERROR: Virtual environment not found at $venvPython" | Out-File -FilePath $logFile -Append -Force -ErrorAction SilentlyContinue
    }
    catch {}
    exit 1
}

# Check if MCP server script exists (log to file, not console)
if (-not (Test-Path $mcpServer)) {
    try {
        "ERROR: MCP server script not found at $mcpServer" | Out-File -FilePath $logFile -Append -Force -ErrorAction SilentlyContinue
    }
    catch {}
    exit 1
}

# NOTE: API keys are now loaded securely via KeyManager
# No need to set environment variables - keys are auto-decrypted from encrypted_secrets.json
# Master key is loaded from .env file (MASTER_ENCRYPTION_KEY)

# Create new log file with timestamp (avoid file locking issues)
$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$sessionLog = "$projectRoot\logs\mcp_server_$timestamp.log"

try {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Starting MCP server" | Out-File -FilePath $sessionLog -Force
}
catch {}

# Launch MCP server with clean stdio
& $venvPython $mcpServer

# Log exit status
try {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - MCP Server exited with code $LASTEXITCODE" | Out-File -FilePath $sessionLog -Append -Force
}
catch {}
