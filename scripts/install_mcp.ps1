<#
.SYNOPSIS
    Install MCP Servers for AI-powered automation
.DESCRIPTION
    Installs Perplexity AI and Capiton GitHub MCP servers
#>

param([switch]$SkipNpm)

$ErrorActionPreference = "Stop"

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  MCP SERVER INSTALLATION" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Installing: Perplexity AI + Capiton GitHub`n" -ForegroundColor White

# Step 1: Check Node.js and npm
Write-Host "[1/4] Checking Node.js and npm..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "  ✓ Node.js version: $nodeVersion" -ForegroundColor Green
    
    $npmVersion = npm --version
    Write-Host "  ✓ npm version: $npmVersion" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ ERROR: Node.js/npm not found!" -ForegroundColor Red
    Write-Host "  → Install Node.js from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Step 2: Check .env file
Write-Host "`n[2/4] Checking environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  WARNING: .env file not found" -ForegroundColor Yellow
    Write-Host "  Copy .env.example to .env and add your API keys" -ForegroundColor Cyan
}
else {
    Write-Host "  .env file found" -ForegroundColor Green
    
    # Check for required keys
    $envContent = Get-Content ".env" -Raw
    $hasPerplexity = $envContent -match "PERPLEXITY_API_KEY=pplx-"
    $hasGitHub = $envContent -match "GITHUB_TOKEN=ghp_" -or $envContent -match "GITHUB_TOKEN=github_pat_"
    
    if ($hasPerplexity) {
        Write-Host "  Perplexity API key found" -ForegroundColor Green
    }
    else {
        Write-Host "  WARNING: Perplexity API key not configured" -ForegroundColor Yellow
    }
    
    if ($hasGitHub) {
        Write-Host "  GitHub token found" -ForegroundColor Green
    }
    else {
        Write-Host "  WARNING: GitHub token not configured" -ForegroundColor Yellow
        Write-Host "  Create token at: https://github.com/settings/tokens" -ForegroundColor Cyan
    }
}

# Step 3: Install MCP servers via npm
if (-not $SkipNpm) {
    Write-Host "`n[3/4] Installing MCP servers..." -ForegroundColor Yellow
    
    Write-Host "  Installing @modelcontextprotocol/server-perplexity..." -ForegroundColor Cyan
    try {
        npm install -g @modelcontextprotocol/server-perplexity 2>&1 | Out-Null
        Write-Host "  Perplexity MCP server installed" -ForegroundColor Green
    }
    catch {
        Write-Host "  WARNING: Could not install Perplexity server" -ForegroundColor Yellow
        Write-Host "  Error: $_" -ForegroundColor Red
    }
    
    Write-Host "  Installing @capiton/mcp-server-github..." -ForegroundColor Cyan
    try {
        npm install -g @capiton/mcp-server-github 2>&1 | Out-Null
        Write-Host "  Capiton GitHub MCP server installed" -ForegroundColor Green
    }
    catch {
        Write-Host "  WARNING: Could not install Capiton server" -ForegroundColor Yellow
        Write-Host "  Error: $_" -ForegroundColor Red
    }
}
else {
    Write-Host "`n[3/4] Skipping npm install" -ForegroundColor Yellow
}

# Step 4: Verify installation
Write-Host "`n[4/4] Verifying installation..." -ForegroundColor Yellow

$mcpConfigPath = ".vscode/mcp.json"
if (Test-Path $mcpConfigPath) {
    Write-Host "  MCP configuration found: $mcpConfigPath" -ForegroundColor Green
}
else {
    Write-Host "  WARNING: MCP configuration not found" -ForegroundColor Yellow
}

# Summary
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Add GitHub token to .env file" -ForegroundColor White
Write-Host "  2. Restart VS Code: code ." -ForegroundColor White
Write-Host "  3. Run workflow: Ctrl+Shift+P -> Tasks: Run Task" -ForegroundColor White
Write-Host ""
Write-Host "Ready to automate!" -ForegroundColor Green
Write-Host ""
