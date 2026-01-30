<#
.SYNOPSIS
    Adds auto-event-binding.js script to all HTML files in frontend folder

.DESCRIPTION
    This script adds the auto-event-binding.js script to all HTML files
    to enable CSP-compliant event handling without inline onclick handlers.

.NOTES
    Audit Task: P2 onclick -> addEventListener migration
    Date: 2026-01-28
#>

param(
    [string]$FrontendPath = "D:\bybit_strategy_tester_v2\frontend"
)

$ScriptTag = '    <script src="js/core/auto-event-binding.js"></script>'

$htmlFiles = Get-ChildItem -Path $FrontendPath -Filter "*.html" -Recurse

$modifiedCount = 0
$skippedCount = 0

foreach ($file in $htmlFiles) {
    $content = Get-Content -Path $file.FullName -Raw
    
    # Skip if already has the script
    if ($content -match "auto-event-binding\.js") {
        Write-Host "[SKIP] $($file.Name) - already has auto-event-binding.js" -ForegroundColor Yellow
        $skippedCount++
        continue
    }
    
    # Find </head> and insert script before it
    if ($content -match "</head>") {
        $newContent = $content -replace "</head>", "$ScriptTag`n</head>"
        Set-Content -Path $file.FullName -Value $newContent -NoNewline
        Write-Host "[OK] $($file.Name) - added auto-event-binding.js" -ForegroundColor Green
        $modifiedCount++
    }
    else {
        Write-Host "[WARN] $($file.Name) - no </head> tag found" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Modified: $modifiedCount files"
Write-Host "  Skipped: $skippedCount files"
Write-Host ""
Write-Host "Done! onclick handlers will now be auto-converted to addEventListener." -ForegroundColor Green
<#
.SYNOPSIS
    Adds auto-event-binding.js script to all HTML files in frontend folder

.DESCRIPTION
    This script adds the auto-event-binding.js script to all HTML files
    to enable CSP-compliant event handling without inline onclick handlers.

.NOTES
    Audit Task: P2 onclick -> addEventListener migration
    Date: 2026-01-28
#>

param(
    [string]$FrontendPath = "D:\bybit_strategy_tester_v2\frontend"
)

$ScriptTag = '    <script src="js/core/auto-event-binding.js"></script>'

$htmlFiles = Get-ChildItem -Path $FrontendPath -Filter "*.html" -Recurse

$modifiedCount = 0
$skippedCount = 0

foreach ($file in $htmlFiles) {
    $content = Get-Content -Path $file.FullName -Raw
    
    # Skip if already has the script
    if ($content -match "auto-event-binding\.js") {
        Write-Host "[SKIP] $($file.Name) - already has auto-event-binding.js" -ForegroundColor Yellow
        $skippedCount++
        continue
    }
    
    # Find </head> and insert script before it
    if ($content -match "</head>") {
        $newContent = $content -replace "</head>", "$ScriptTag`n</head>"
        Set-Content -Path $file.FullName -Value $newContent -NoNewline
        Write-Host "[OK] $($file.Name) - added auto-event-binding.js" -ForegroundColor Green
        $modifiedCount++
    }
    else {
        Write-Host "[WARN] $($file.Name) - no </head> tag found" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Modified: $modifiedCount files"
Write-Host "  Skipped: $skippedCount files"
Write-Host ""
Write-Host "Done! onclick handlers will now be auto-converted to addEventListener." -ForegroundColor Green
