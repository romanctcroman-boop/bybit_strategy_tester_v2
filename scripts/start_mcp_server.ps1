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
$journalDir = "$projectRoot\journal"
$journalFile = "$journalDir\mcp_server_journal.log"

# Ensure logs directory exists
$logsDir = "$projectRoot\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

if (-not (Test-Path $journalDir)) {
    New-Item -ItemType Directory -Path $journalDir -Force | Out-Null
}

# Try to route LLM traffic through the local Envoy sidecar if it's up
$envoyStatus = $null
$envoyHelperPath = Join-Path $projectRoot "scripts\set_envoy_proxy_env.ps1"
if (Test-Path $envoyHelperPath) {
    . $envoyHelperPath
    try {
        $envoyStatus = Set-EnvoyProxyEnv
    }
    catch {
        $envoyStatus = $null
    }
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

# Ensure encrypted_secrets.json is accessible in project root (temporary workaround)
$secretsSource = "$projectRoot\backend\config\encrypted_secrets.json"
$secretsTarget = "$projectRoot\encrypted_secrets.json"
if ((Test-Path $secretsSource) -and -not (Test-Path $secretsTarget)) {
    Copy-Item $secretsSource $secretsTarget -Force -ErrorAction SilentlyContinue
}

# NOTE: API keys are now loaded securely via KeyManager
# No need to set environment variables - keys are auto-decrypted from encrypted_secrets.json
# Master key is loaded from .env file (MASTER_ENCRYPTION_KEY)

# Create new log file with timestamp (avoid file locking issues)
$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$sessionLog = "$projectRoot\logs\mcp_server_$timestamp.log"
$stderrLog = "$projectRoot\logs\mcp-server.err.log"

# Reset stderr log for this session (stdout must remain untouched for JSON-RPC transport)
if (Test-Path $stderrLog) {
    Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue
}

try {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Starting MCP server" | Out-File -FilePath $sessionLog -Force
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Starting MCP server" | Out-File -FilePath $journalFile -Append -Force

    if ($envoyStatus) {
        if ($envoyStatus.PerplexityRouted) {
            $perplexityMode = 'routed'
        }
        else {
            $perplexityMode = 'direct'
        }

        if ($envoyStatus.DeepSeekRouted) {
            $deepseekMode = 'routed'
        }
        else {
            $deepseekMode = 'direct'
        }
        $envoyLine = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Envoy sidecar status: perplexity=$perplexityMode, deepseek=$deepseekMode, ports=P$($envoyStatus.PerplexityPortOpen)/D$($envoyStatus.DeepSeekPortOpen)"
        $envoyLine | Out-File -FilePath $sessionLog -Append -Force
        $envoyLine | Out-File -FilePath $journalFile -Append -Force
    }
}
catch {}

# Launch MCP server with clean stdout (JSON-RPC) while capturing stderr to file
$process = $null
try {
    $process = Start-Process -FilePath $venvPython `
        -ArgumentList $mcpServer `
        -WorkingDirectory $projectRoot `
        -NoNewWindow `
        -RedirectStandardError $stderrLog `
        -PassThru
    $process.WaitForExit()
}
catch {
    $errorMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Failed to start MCP server: $($_.Exception.Message)"
    $errorMessage | Out-File -FilePath $sessionLog -Append -Force
    $errorMessage | Out-File -FilePath $journalFile -Append -Force
}

$exitCode = if ($process) { $process.ExitCode } else { -1 }

# Log exit status
try {
    $exitLine = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - MCP Server exited with code $exitCode"
    $exitLine | Out-File -FilePath $sessionLog -Append -Force
    $exitLine | Out-File -FilePath $journalFile -Append -Force

    if ($exitCode -ne 0 -and (Test-Path $stderrLog)) {
        $errorSummary = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - stderr tail (last 40 lines):"
        $errorSummary | Out-File -FilePath $sessionLog -Append -Force
        Get-Content -Path $stderrLog -Tail 40 | Out-File -FilePath $sessionLog -Append -Force
    }
}
catch {}
