# MCP Integration - Scenario Testing Script
# Tests various workflow scenarios

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

Write-Host "`n=============================================="  -ForegroundColor Cyan
Write-Host "  MCP INTEGRATION - SCENARIO TESTING" -ForegroundColor Cyan
Write-Host "==============================================`n" -ForegroundColor Cyan

$testResults = @{
    Passed = 0
    Failed = 0
    Total  = 0
}

function Test-Scenario {
    param(
        [string]$Name,
        [scriptblock]$Test
    )
    
    $testResults.Total++
    Write-Host "[$($testResults.Total)] Testing: $Name" -ForegroundColor Cyan
    
    try {
        & $Test
        Write-Host "    PASSED" -ForegroundColor Green
        $testResults.Passed++
        return $true
    }
    catch {
        Write-Host "    FAILED: $($_.Exception.Message)" -ForegroundColor Red
        $testResults.Failed++
        if ($Verbose) {
            Write-Host "    Details: $_" -ForegroundColor DarkRed
        }
        return $false
    }
}

# Test 1: Configuration Files
$test1 = {
    if (-not (Test-Path ".vscode\mcp.json")) {
        throw "mcp.json not found"
    }
    
    $config = Get-Content ".vscode\mcp.json" -Raw | ConvertFrom-Json
    
    if (-not $config.mcpServers) { throw "mcpServers not defined" }
    if (-not $config.mcpServers.perplexity) { throw "Perplexity not configured" }
    if (-not $config.mcpServers.'capiton-github') { throw "Capiton not configured" }
    
    Write-Host "    - mcp.json valid, 2 servers configured" -ForegroundColor Gray
}

# Test 2: Environment Setup
$test2 = {
    if (-not (Test-Path ".env.example")) { throw ".env.example not found" }
    
    $envExample = Get-Content ".env.example" -Raw
    if ($envExample -notmatch "PERPLEXITY_API_KEY") { throw "PERPLEXITY_API_KEY missing" }
    if ($envExample -notmatch "GITHUB_TOKEN") { throw "GITHUB_TOKEN missing" }
    
    Write-Host "    - .env.example valid" -ForegroundColor Gray
}

# Test 3: Scripts
$test3 = {
    $scripts = @(
        "scripts\install_mcp.ps1",
        "scripts\install_mcp.sh",
        "scripts\mcp_workflow.ps1"
    )
    
    foreach ($script in $scripts) {
        if (-not (Test-Path $script)) { throw "$script not found" }
    }
    
    Write-Host "    - All 3 scripts present" -ForegroundColor Gray
}

# Test 4: VS Code Tasks
$test4 = {
    if (-not (Test-Path ".vscode\tasks.json")) { throw "tasks.json not found" }
    
    $tasks = Get-Content ".vscode\tasks.json" -Raw | ConvertFrom-Json
    $mcpTasks = $tasks.tasks | Where-Object { $_.label -like "*MCP*" }
    
    if ($mcpTasks.Count -eq 0) { throw "No MCP tasks found" }
    
    Write-Host "    - $($mcpTasks.Count) MCP tasks found" -ForegroundColor Gray
}

# Test 5: Documentation
$test5 = {
    $docs = @(
        "QUICKSTART_MCP.md",
        "MCP_INTEGRATION.md",
        "MCP_DOCS_INDEX.md",
        ".vscode\MCP_SETUP_GUIDE.md"
    )
    
    foreach ($doc in $docs) {
        if (-not (Test-Path $doc)) { throw "$doc not found" }
    }
    
    Write-Host "    - All documentation files present" -ForegroundColor Gray
}

# Test 6: Workflow Pipeline
$test6 = {
    $config = Get-Content ".vscode\mcp.json" -Raw | ConvertFrom-Json
    $pipeline = $config.workflow.pipeline
    
    if ($pipeline.Count -ne 4) { throw "Expected 4 pipeline stages, found $($pipeline.Count)" }
    
    $stages = $pipeline | ForEach-Object { $_.stage }
    $expected = @('analysis', 'planning', 'execution', 'validation')
    
    for ($i = 0; $i -lt 4; $i++) {
        if ($stages[$i] -ne $expected[$i]) {
            throw "Stage mismatch at position $i"
        }
    }
    
    Write-Host "    - Pipeline has correct 4 stages" -ForegroundColor Gray
}

# Test 7: Routing Rules
$test7 = {
    $config = Get-Content ".vscode\mcp.json" -Raw | ConvertFrom-Json
    $routing = $config.workflow.routing
    
    # Capiton-only
    if ($routing.taskCreation -notcontains 'capiton-github') {
        throw "taskCreation should route to capiton-github"
    }
    
    # Perplexity-only
    if ($routing.deepAnalysis -notcontains 'perplexity') {
        throw "deepAnalysis should route to perplexity"
    }
    
    Write-Host "    - Routing rules valid" -ForegroundColor Gray
}

# Test 8: NPM Check
$test8 = {
    try {
        $npmVersion = npm --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "npm not available" }
        Write-Host "    - npm version $npmVersion detected" -ForegroundColor Gray
    }
    catch {
        throw "npm not installed"
    }
}

# Test 9: Project Integration
$test9 = {
    $context = Get-Content ".vscode\PROJECT_CONTEXT.md" -Raw
    
    $required = @('RBAC', 'Code Consolidation', 'DataManager', 'Position Sizing')
    foreach ($item in $required) {
        if ($context -notmatch $item) { throw "Missing: $item" }
    }
    
    Write-Host "    - Project context complete" -ForegroundColor Gray
}

# Test 10: Backward Compatibility
$test10 = {
    $tasks = Get-Content ".vscode\tasks.json" -Raw | ConvertFrom-Json
    
    $hasOriginal = $false
    foreach ($task in $tasks.tasks) {
        if ($task.label -match 'frontend|backend|uvicorn') {
            $hasOriginal = $true
            break
        }
    }
    
    if (-not $hasOriginal) { throw "Original tasks not preserved" }
    
    Write-Host "    - Original project tasks preserved" -ForegroundColor Gray
}

# Run all tests
Write-Host "Running tests...`n" -ForegroundColor Yellow

Test-Scenario -Name "Configuration Files" -Test $test1
Test-Scenario -Name "Environment Setup" -Test $test2
Test-Scenario -Name "Scripts Validation" -Test $test3
Test-Scenario -Name "VS Code Tasks" -Test $test4
Test-Scenario -Name "Documentation" -Test $test5
Test-Scenario -Name "Workflow Pipeline" -Test $test6
Test-Scenario -Name "Routing Rules" -Test $test7
Test-Scenario -Name "NPM Availability" -Test $test8
Test-Scenario -Name "Project Integration" -Test $test9
Test-Scenario -Name "Backward Compatibility" -Test $test10

# Summary
Write-Host "`n==============================================" -ForegroundColor Cyan
Write-Host "TEST RESULTS" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan

$passRate = [math]::Round(($testResults.Passed / $testResults.Total) * 100, 1)

Write-Host "`nPassed: $($testResults.Passed)/$($testResults.Total)" -ForegroundColor Green
Write-Host "Failed: $($testResults.Failed)/$($testResults.Total)" -ForegroundColor $(if ($testResults.Failed -eq 0) { 'Green' } else { 'Red' })
Write-Host "Pass Rate: $passRate%" -ForegroundColor $(
    if ($passRate -ge 90) { 'Green' }
    elseif ($passRate -ge 70) { 'Yellow' }
    else { 'Red' }
)

if ($testResults.Failed -eq 0) {
    Write-Host "`nALL TESTS PASSED! MCP Integration validated.`n" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`nSome tests failed. Review output above.`n" -ForegroundColor Yellow
    exit 1
}
