# ==============================================================================
# Clean Up Temporary Data Files from Root
# ==============================================================================
# Moves temporary .json, .txt, .log files to data/archive/
# Keeps: essential config files
# ==============================================================================

$ErrorActionPreference = "Continue"

# Files to keep in root
$keepFiles = @(
    # Config
    ".env",
    ".env.example",
    ".env.production",
    ".gitignore",
    ".gitattributes",
    ".markdownlint.json",
    ".pre-commit-config.yaml",
    ".editorconfig",
    "alembic.ini",
    "pyproject.toml",
    "pytest.ini",
    "ruff.toml",
    "agents.yaml",
    "requirements-dev.txt",
    "requirements-ml.txt",
    "conftest.py",
    "main.py",
    # Docs
    "README.md",
    "QUICKSTART.md",
    "QUICK_REFERENCE.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "Dockerfile",
    # Russian
    "ЗАПУСК.txt"
)

# Create archive directory
$archiveDir = "data\archive"
if (-not (Test-Path $archiveDir)) {
    New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    Write-Host "[+] Created $archiveDir" -ForegroundColor Green
}

$movedCount = 0
$skippedCount = 0

# Get temp files in root
$tempFiles = Get-ChildItem -Path . -File | Where-Object {
    ($_.Extension -in @(".json", ".txt", ".log")) -and
    ($_.Name -notin $keepFiles)
}

foreach ($file in $tempFiles) {
    $dest = Join-Path $archiveDir $file.Name
    Move-Item -Path $file.FullName -Destination $dest -Force
    $movedCount++
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Temporary Files Cleanup Complete!" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Moved to data/archive: $movedCount files" -ForegroundColor Yellow
Write-Host ""

# Show remaining files in root
$remaining = Get-ChildItem -Path . -File | Where-Object { 
    $_.Extension -in @(".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini")
}
Write-Host "  Remaining config files in root:" -ForegroundColor White
foreach ($f in $remaining | Select-Object -First 15) {
    Write-Host "    - $($f.Name)" -ForegroundColor Gray
}
if ($remaining.Count -gt 15) {
    Write-Host "    ... and $($remaining.Count - 15) more" -ForegroundColor Gray
}
Write-Host ""
