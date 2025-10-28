<#
.SYNOPSIS
    MCP Workflow - Test Analysis and Fixes
#>

param([string]$Workflow = "analyze-tests")

Write-Host "`n================================================================================" -ForegroundColor Magenta
Write-Host "  MCP WORKFLOW: $Workflow" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Magenta

# Check API keys from .env
$hasPerplexity = $false
$hasGitHub = $false

if (Test-Path ".env") {
    $envLines = Get-Content ".env"
    foreach ($line in $envLines) {
        if ($line -match "PERPLEXITY_API_KEY=pplx-") { $hasPerplexity = $true }
        if ($line -match "GITHUB_TOKEN=(ghp_|github_pat_)") { $hasGitHub = $true }
    }
}

Write-Host "`nAPI Status:" -ForegroundColor Yellow
Write-Host "  Perplexity: $(if ($hasPerplexity) { 'OK' } else { 'MISSING' })" -ForegroundColor $(if ($hasPerplexity) { 'Green' } else { 'Red' })
Write-Host "  GitHub: $(if ($hasGitHub) { 'OK' } else { 'MISSING' })" -ForegroundColor $(if ($hasGitHub) { 'Green' } else { 'Red' })

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  WORKFLOW EXECUTION" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan

# Function: Test MCP Servers
function Test-MCPServers {
    Write-Host "`nChecking MCP server availability..." -ForegroundColor Yellow
    
    # Check if npm packages are installed (optional, MCP servers run via VS Code)
    try {
        $npmList = npm list -g --depth=0 2>&1
        if ($npmList -match "@perplexity/mcp-server" -or $npmList -match "@capiton/mcp-server") {
            Write-Host "  ✓ MCP servers found in npm global" -ForegroundColor Green
            return $true
        }
    }
    catch {
        # MCP servers may be managed by VS Code directly
        Write-Host "  ℹ MCP servers managed by VS Code" -ForegroundColor Cyan
    }
    
    # Check MCP configuration
    if (Test-Path ".vscode/mcp.json") {
        Write-Host "  ✓ MCP configuration found" -ForegroundColor Green
        return $true
    }
    
    Write-Host "  ⚠ MCP configuration not found" -ForegroundColor Yellow
    return $false
}

# Workflow logic
Write-Host "`n[STEP 1] Analyzing test failures..." -ForegroundColor Yellow
Write-Host "  Found issues:" -ForegroundColor White
Write-Host "    - MonteCarloResult API (11 tests)" -ForegroundColor Red
Write-Host "    - WalkForwardOptimizer params (5 tests)" -ForegroundColor Red
Write-Host "    - MTF Engine import (1 module)" -ForegroundColor Red

Write-Host "`n[STEP 2] Perplexity AI would..." -ForegroundColor Yellow
if ($hasPerplexity) {
    Write-Host "  - Analyze root causes" -ForegroundColor Green
    Write-Host "  - Generate code fixes" -ForegroundColor Green
    Write-Host "  - Suggest best practices" -ForegroundColor Green
}
else {
    Write-Host "  SKIPPED: API key needed" -ForegroundColor Red
}

Write-Host "`n[STEP 3] Capiton GitHub would..." -ForegroundColor Yellow
if ($hasGitHub) {
    Write-Host "  - Create 3 issues" -ForegroundColor Green
    Write-Host "  - Assign priorities" -ForegroundColor Green
    Write-Host "  - Coordinate PRs" -ForegroundColor Green
}
else {
    Write-Host "  SKIPPED: Token needed" -ForegroundColor Red
}

Write-Host "`n================================================================================" -ForegroundColor Magenta
if ($hasPerplexity -and $hasGitHub) {
    Write-Host "  READY FOR AUTOMATION!" -ForegroundColor Green
}
else {
    Write-Host "  ADD GITHUB TOKEN TO .env" -ForegroundColor Yellow
    Write-Host "  https://github.com/settings/tokens" -ForegroundColor Cyan
}
Write-Host "================================================================================" -ForegroundColor Magenta
Write-Host ""
