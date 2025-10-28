# Test Perplexity MCP Server
# Load API key from .env file
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$pythonPath = "D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe"

Write-Host "Testing Perplexity MCP Server..." -ForegroundColor Cyan

# Initialize request
$initRequest = @{
    jsonrpc = "2.0"
    id      = 1
    method  = "initialize"
    params  = @{}
} | ConvertTo-Json -Compress

Write-Host "`nSending initialize request..." -ForegroundColor Yellow
Write-Host $initRequest -ForegroundColor Gray

echo $initRequest | & $pythonPath mcp_perplexity_server.py

Write-Host "`nIf you see a response above, the MCP server is working!" -ForegroundColor Green
