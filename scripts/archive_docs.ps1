# ==============================================================================
# Archive Old Documentation Files
# ==============================================================================
# Moves old .md files from root to docs/archive/
# Preserves: README.md, README_FINAL.md, QUICKSTART.md, LICENSE
# ==============================================================================

$ErrorActionPreference = "Continue"

# Files to keep in root
$keepFiles = @(
    "README.md",
    "README_FINAL.md", 
    "QUICKSTART.md",
    "QUICK_REFERENCE.md",
    "LICENSE"
)

# Create archive directory
$archiveDir = "docs\archive"
if (-not (Test-Path $archiveDir)) {
    New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    Write-Host "[+] Created $archiveDir" -ForegroundColor Green
}

# Get all .md files in root (excluding those to keep)
$mdFiles = Get-ChildItem -Path . -Filter "*.md" -File | Where-Object { 
    $_.Name -notin $keepFiles 
}

$count = 0
foreach ($file in $mdFiles) {
    $dest = Join-Path $archiveDir $file.Name
    Move-Item -Path $file.FullName -Destination $dest -Force
    $count++
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Archive Complete!" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Moved: $count files to $archiveDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Kept in root:" -ForegroundColor Green
foreach ($f in $keepFiles) {
    if (Test-Path $f) {
        Write-Host "    - $f" -ForegroundColor White
    }
}
Write-Host ""
