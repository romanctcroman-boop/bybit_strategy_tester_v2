<#
.SYNOPSIS
    MCP-Powered Full Test Suite Runner
#>

param([switch]$StopOnError)

$ErrorActionPreference = "Continue"

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  MCP-POWERED FULL TEST SUITE" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Strategy: Perplexity AI analyzes -> Capiton GitHub tracks" -ForegroundColor Cyan
Write-Host ""

$StartTime = Get-Date
$OutputFile = "mcp_test_results_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

# Build pytest command
$pytestArgs = @("-v", "--tb=short", "-ra")
if ($StopOnError) { $pytestArgs += "-x" }

Write-Host "Running: py -3.13 -m pytest $($pytestArgs -join ' ')" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Run tests
py -3.13 -m pytest @pytestArgs > $OutputFile 2>&1

# Parse results
$TestsPassed = 0
$TestsFailed = 0
$TestsSkipped = 0
$FailedTests = @()

if (Test-Path $OutputFile) {
    $Output = Get-Content $OutputFile -Raw
    if ($Output -match "(\d+) passed") { $TestsPassed = [int]$Matches[1] }
    if ($Output -match "(\d+) failed") { $TestsFailed = [int]$Matches[1] }
    if ($Output -match "(\d+) skipped") { $TestsSkipped = [int]$Matches[1] }
    
    $FailedMatches = [regex]::Matches($Output, "FAILED (tests/[^\s]+)")
    foreach ($match in $FailedMatches) {
        $FailedTests += $match.Groups[1].Value
    }
}

$TotalTests = $TestsPassed + $TestsFailed + $TestsSkipped
$Duration = (Get-Date) - $StartTime
$PassRate = if ($TotalTests -gt 0) { [math]::Round(($TestsPassed / $TotalTests) * 100, 2) } else { 0 }

# Summary
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Total:     $TotalTests" -ForegroundColor White
Write-Host "  Passed:    $TestsPassed" -ForegroundColor Green
Write-Host "  Failed:    $TestsFailed" -ForegroundColor $(if ($TestsFailed -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped:   $TestsSkipped" -ForegroundColor Yellow
Write-Host "  Pass Rate: $PassRate%" -ForegroundColor $(if ($PassRate -ge 90) { "Green" } elseif ($PassRate -ge 75) { "Yellow" } else { "Red" })
Write-Host "  Duration:  $($Duration.ToString('mm\:ss'))" -ForegroundColor White
Write-Host ""

# MCP Analysis
if ($TestsFailed -gt 0) {
    Write-Host "================================================================================" -ForegroundColor Yellow
    Write-Host "  MCP - PERPLEXITY AI ANALYSIS" -ForegroundColor White
    Write-Host "================================================================================" -ForegroundColor Yellow
    Write-Host "`nFailed Tests:" -ForegroundColor Red
    foreach ($test in $FailedTests) {
        Write-Host "  - $test" -ForegroundColor White
    }
    Write-Host "`nPerplexity would analyze root cause and suggest fixes" -ForegroundColor Cyan
    Write-Host "Capiton would create GitHub issues and track progress" -ForegroundColor Cyan
    Write-Host ""
}

# Generate report
$ReportFile = "MCP_TEST_REPORT_$(Get-Date -Format 'yyyyMMdd_HHmmss').md"
$ReportText = "# MCP Test Report`n`n**Total:** $TotalTests | **Passed:** $TestsPassed | **Failed:** $TestsFailed | **Pass Rate:** $PassRate%`n`n## Failed Tests`n`n"
if ($FailedTests.Count -gt 0) {
    $FailedTests | ForEach-Object { $ReportText += "- ``$_```n" }
}
else {
    $ReportText += "None!`n"
}
$ReportText | Out-File -FilePath $ReportFile -Encoding UTF8

Write-Host "Report saved: $ReportFile" -ForegroundColor Green
Write-Host "Output saved: $OutputFile" -ForegroundColor Green

if ($TestsFailed -eq 0) {
    Write-Host "`n  SUCCESS! All tests passed!`n" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`n  WARNING: $TestsFailed test(s) failed`n" -ForegroundColor Yellow
    exit 1
}
