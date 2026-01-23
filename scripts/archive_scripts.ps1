# ==============================================================================
# Archive Old Python Scripts from Root
# ==============================================================================
# Moves temporary/debug .py files from root to scripts/archive/
# Preserves: conftest.py, main.py
# ==============================================================================

$ErrorActionPreference = "Continue"

# Files to keep in root
$keepFiles = @(
    "conftest.py",
    "main.py"
)

# Patterns to archive (temporary/debug scripts)
$archivePatterns = @(
    "check_*.py",
    "test_*.py",
    "analyze_*.py",
    "compare_*.py",
    "debug_*.py",
    "verify_*.py",
    "fix_*.py",
    "clean*.py",
    "download_*.py",
    "export_*.py",
    "fetch_*.py",
    "find_*.py",
    "get_*.py",
    "list_*.py",
    "load_*.py",
    "run_*.py",
    "send_*.py",
    "sim*.py",
    "tv_*.py",
    "quick_*.py",
    "temp_*.py",
    "insert_*.py",
    "apply_*.py",
    "restore_*.py",
    "count_*.py",
    "scan_*.py",
    "trace_*.py",
    "tune_*.py",
    "parity_*.py",
    "full_*.py",
    "final_*.py",
    "exact_*.py",
    "deep_*.py",
    "direct_*.py",
    "demo_*.py",
    "diagnose_*.py",
    "consult_*.py",
    "call_*.py",
    "calc_*.py",
    "browser_*.py",
    "backtest_*.py",
    "audit_*.py",
    "ask_*.py",
    "agent_*.py",
    "ai_*.py",
    "add_*.py",
    "open_*.py",
    "monitor_*.py",
    "manage_*.py",
    "kill_*.py",
    "parallel_*.py",
    "phase*.py",
    "playwright_*.py",
    "ui_*.py",
    "simple_*.py"
)

# Create archive directory
$archiveDir = "scripts\archive"
if (-not (Test-Path $archiveDir)) {
    New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    Write-Host "[+] Created $archiveDir" -ForegroundColor Green
}

$movedCount = 0
$skippedCount = 0

# Get all .py files in root
$allPyFiles = Get-ChildItem -Path . -Filter "*.py" -File

foreach ($file in $allPyFiles) {
    # Skip files to keep
    if ($file.Name -in $keepFiles) {
        $skippedCount++
        continue
    }
    
    # Check if matches any archive pattern
    $shouldArchive = $false
    foreach ($pattern in $archivePatterns) {
        if ($file.Name -like $pattern) {
            $shouldArchive = $true
            break
        }
    }
    
    if ($shouldArchive) {
        $dest = Join-Path $archiveDir $file.Name
        Move-Item -Path $file.FullName -Destination $dest -Force
        $movedCount++
    }
    else {
        $skippedCount++
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Python Scripts Archive Complete!" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Moved to scripts/archive: $movedCount files" -ForegroundColor Yellow
Write-Host "  Kept in root: $skippedCount files" -ForegroundColor Green
Write-Host ""

# Show remaining files
$remaining = Get-ChildItem -Path . -Filter "*.py" -File
if ($remaining.Count -gt 0) {
    Write-Host "  Remaining .py files in root:" -ForegroundColor White
    foreach ($f in $remaining) {
        Write-Host "    - $($f.Name)" -ForegroundColor Gray
    }
}
Write-Host ""
