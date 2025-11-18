# MCP Server Diagnostic & Fix Script
# Диагностика и исправление проблем с MCP Server

Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "🔍 MCP SERVER DIAGNOSTIC TOOL" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

$projectRoot = "D:\bybit_strategy_tester_v2"

# 1. Check Python environment
Write-Host "`n[1/6] Checking Python environment..." -ForegroundColor Yellow
$pythonExe = "$projectRoot\.venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    Write-Host "✅ Python found: $pythonExe" -ForegroundColor Green
    $pythonVersion = & $pythonExe --version 2>&1
    Write-Host "   Version: $pythonVersion" -ForegroundColor Gray
}
else {
    Write-Host "❌ Python not found at $pythonExe" -ForegroundColor Red
    exit 1
}

# 2. Check MCP server files
Write-Host "`n[2/6] Checking MCP server files..." -ForegroundColor Yellow
$serverFiles = @(
    "$projectRoot\mcp-server\server.py",
    "$projectRoot\mcp-server\server_integrated.py",
    "$projectRoot\mcp-server\deepseek_code_agent.py",
    "$projectRoot\mcp-server\multi_agent_router.py"
)

foreach ($file in $serverFiles) {
    if (Test-Path $file) {
        $fileName = Split-Path $file -Leaf
        Write-Host "✅ Found: $fileName" -ForegroundColor Green
    }
    else {
        Write-Host "❌ Missing: $file" -ForegroundColor Red
    }
}

# 3. Check API keys in .env
Write-Host "`n[3/6] Checking API keys..." -ForegroundColor Yellow
$envFile = "$projectRoot\.env"
if (Test-Path $envFile) {
    Write-Host "✅ .env file found" -ForegroundColor Green
    
    $envContent = Get-Content $envFile -Raw
    
    # Check PERPLEXITY_API_KEY
    $perplexityMatch = [regex]::Match($envContent, 'PERPLEXITY_API_KEY=([^\r\n]+)')
    if ($perplexityMatch.Success) {
        $key = $perplexityMatch.Groups[1].Value.Trim()
        if ($key -and $key.Length -gt 10) {
            $preview = $key.Substring(0, 10)
            Write-Host "OK PERPLEXITY_API_KEY: $preview..." -ForegroundColor Green
        }
        elseif ($key) {
            Write-Host "OK PERPLEXITY_API_KEY: $key" -ForegroundColor Green
        }
        else {
            Write-Host "FAIL PERPLEXITY_API_KEY is empty" -ForegroundColor Red
        }
    }
    else {
        Write-Host "FAIL PERPLEXITY_API_KEY not found in .env" -ForegroundColor Red
    }
    
    # Check DEEPSEEK_API_KEY
    $deepseekMatch = [regex]::Match($envContent, 'DEEPSEEK_API_KEY=([^\r\n]+)')
    if ($deepseekMatch.Success) {
        $key = $deepseekMatch.Groups[1].Value.Trim()
        if ($key -and $key.Length -gt 10) {
            $preview = $key.Substring(0, 10)
            Write-Host "OK DEEPSEEK_API_KEY: $preview..." -ForegroundColor Green
        }
        elseif ($key) {
            Write-Host "OK DEEPSEEK_API_KEY: $key" -ForegroundColor Green
        }
        else {
            Write-Host "FAIL DEEPSEEK_API_KEY is empty" -ForegroundColor Red
        }
    }
    else {
        Write-Host "FAIL DEEPSEEK_API_KEY not found in .env" -ForegroundColor Red
    }
}
else {
    Write-Host "❌ .env file not found" -ForegroundColor Red
}

# 4. Check VS Code configuration
Write-Host "`n[4/6] Checking VS Code MCP configuration..." -ForegroundColor Yellow
$mcpConfigFile = "$projectRoot\.vscode\mcp.json"
if (Test-Path $mcpConfigFile) {
    Write-Host "✅ mcp.json found" -ForegroundColor Green
    
    try {
        $mcpConfig = Get-Content $mcpConfigFile -Raw | ConvertFrom-Json
        if ($mcpConfig.servers.'bybit-strategy-tester') {
            Write-Host "✅ MCP server configured: bybit-strategy-tester" -ForegroundColor Green
            $serverConfig = $mcpConfig.servers.'bybit-strategy-tester'
            Write-Host "   Command: $($serverConfig.command)" -ForegroundColor Gray
            Write-Host "   Args: $($serverConfig.args -join ' ')" -ForegroundColor Gray
        }
        else {
            Write-Host "❌ MCP server 'bybit-strategy-tester' not configured" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "❌ Failed to parse mcp.json: $_" -ForegroundColor Red
    }
}
else {
    Write-Host "❌ mcp.json not found" -ForegroundColor Red
}

# 5. Test MCP server startup (quick test)
Write-Host "`n[5/6] Testing MCP server startup..." -ForegroundColor Yellow
$env:PERPLEXITY_API_KEY = "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"
$env:DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"
$env:PYTHONPATH = $projectRoot

Write-Host "   Starting server with 5 seconds timeout..." -ForegroundColor Gray

$job = Start-Job -ScriptBlock {
    param($pythonExe, $serverScript)
    & $pythonExe $serverScript 2>&1
} -ArgumentList $pythonExe, "$projectRoot\mcp-server\server.py"

Start-Sleep -Seconds 5

$output = Receive-Job -Job $job -Keep
$jobState = $job.State

Stop-Job -Job $job -ErrorAction SilentlyContinue
Remove-Job -Job $job -ErrorAction SilentlyContinue

if ($jobState -eq "Running" -and $output -match "FastMCP") {
    Write-Host "✅ MCP server started successfully" -ForegroundColor Green
    Write-Host "   Server output:" -ForegroundColor Gray
    $output | Select-Object -Last 10 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
}
else {
    Write-Host "❌ MCP server failed to start" -ForegroundColor Red
    if ($output) {
        Write-Host "   Error output:" -ForegroundColor Gray
        $output | Select-Object -Last 10 | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
    }
}

# 6. Check for VS Code MCP extension
Write-Host "`n[6/6] Checking VS Code extensions..." -ForegroundColor Yellow
$codeCmd = Get-Command code -ErrorAction SilentlyContinue
if ($codeCmd) {
    Write-Host "✅ VS Code CLI found" -ForegroundColor Green
    
    Write-Host "   Checking for MCP/Copilot extensions..." -ForegroundColor Gray
    $extensions = & code --list-extensions 2>&1
    
    $mcpRelated = $extensions | Where-Object { $_ -match "mcp|copilot|model-context" }
    if ($mcpRelated) {
        Write-Host "✅ Found MCP-related extensions:" -ForegroundColor Green
        $mcpRelated | ForEach-Object { Write-Host "   - $_" -ForegroundColor Gray }
    }
    else {
        Write-Host "⚠️  No MCP-related extensions found" -ForegroundColor Yellow
        Write-Host "   Consider installing Model Context Protocol extension" -ForegroundColor Yellow
    }
}
else {
    Write-Host "⚠️  VS Code CLI not found in PATH" -ForegroundColor Yellow
}

# Summary and recommendations
Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "📋 DIAGNOSTIC SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

Write-Host "`n[INFO] RECOMMENDATIONS:" -ForegroundColor Cyan
Write-Host "   1. If MCP server started successfully, restart VS Code to activate it" -ForegroundColor White
Write-Host "   2. Ensure GitHub Copilot extension is installed and activated" -ForegroundColor White
Write-Host "   3. Check VS Code settings: Copilot - Advanced - MCP Enabled" -ForegroundColor White
Write-Host "   4. Use Ctrl+Shift+P -> MCP: Restart Server to manually restart" -ForegroundColor White
Write-Host "   5. Check VS Code Output panel (View - Output - MCP) for logs" -ForegroundColor White

Write-Host "`n[FIX] MANUAL FIX (if needed):" -ForegroundColor Cyan
Write-Host "   Run: scripts\start_mcp_server.ps1" -ForegroundColor White
Write-Host "   Or: python mcp-server\server.py" -ForegroundColor White

Write-Host "`n[SUCCESS] Diagnostic complete!`n" -ForegroundColor Green
