# ═══════════════════════════════════════════════════════════════
# Clean Git History - Remove files with API keys
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "  GIT HISTORY CLEANUP - Remove API Keys" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""

# Files to remove from history
$filesToRemove = @(
    "CRITICAL_FIXES_FINAL_REPORT.md",
    "NEXT_STEPS.md",
    "query_perplexity.py"
)

Write-Host "⚠️  WARNING: This will rewrite Git history!" -ForegroundColor Red
Write-Host ""
Write-Host "Files to remove from history:" -ForegroundColor Yellow
foreach ($file in $filesToRemove) {
    Write-Host "  • $file" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "This operation:" -ForegroundColor Yellow
Write-Host "  ✓ Removes files from ALL commits" -ForegroundColor Green
Write-Host "  ✓ Changes commit hashes" -ForegroundColor Red
Write-Host "  ✓ Requires force push to remote" -ForegroundColor Red
Write-Host ""

$confirm = Read-Host "Continue? (type 'YES' to confirm)"

if ($confirm -ne "YES") {
    Write-Host ""
    Write-Host "❌ Operation cancelled" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "Starting cleanup..." -ForegroundColor Yellow
Write-Host ""

# Check if git-filter-repo is installed
$filterRepo = Get-Command git-filter-repo -ErrorAction SilentlyContinue

if (-not $filterRepo) {
    Write-Host "❌ git-filter-repo not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install with:" -ForegroundColor Yellow
    Write-Host "  pip install git-filter-repo" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Alternative: Use BFG Repo-Cleaner" -ForegroundColor Yellow
    Write-Host "  https://rtyley.github.io/bfg-repo-cleaner/" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# Create backup
Write-Host "Creating backup..." -ForegroundColor Yellow
$backupBranch = "backup-before-cleanup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
git branch $backupBranch
Write-Host "✓ Backup created: $backupBranch" -ForegroundColor Green
Write-Host ""

# Remove files from history
Write-Host "Removing files from history..." -ForegroundColor Yellow
foreach ($file in $filesToRemove) {
    Write-Host "  Processing: $file" -ForegroundColor Cyan
    git filter-repo --invert-paths --path $file --force
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify changes: git log --oneline" -ForegroundColor Cyan
Write-Host "  2. Force push: git push origin main --force" -ForegroundColor Cyan
Write-Host "  3. Team members need to: git pull --rebase" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backup branch: $backupBranch" -ForegroundColor Yellow
Write-Host "  To restore: git checkout $backupBranch" -ForegroundColor Gray
Write-Host ""
