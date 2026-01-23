# ==============================================================================
# Reorganize Documentation by Category
# ==============================================================================
# Moves docs/*.md files into organized subdirectories
# Run from project root: .\scripts\reorganize_docs.ps1
# ==============================================================================

$ErrorActionPreference = "Continue"

$docsDir = "docs"

# Create category directories
$categories = @("api", "architecture", "guides", "reference", "ai")
foreach ($cat in $categories) {
    $path = Join-Path $docsDir $cat
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "[+] Created $path" -ForegroundColor Green
    }
}

# File mappings: filename pattern -> category
$mappings = @{
    # Architecture
    "ENGINE_*.md"          = "architecture"
    "STRATEGIES_*.md"      = "architecture"
    "DETAILED_CODE_*.md"   = "architecture"
    "OPTIMIZATION_*.md"    = "architecture"
    "BAR_MAGNIFIER_*.md"   = "architecture"
    
    # AI documentation
    "AI_AGENT_*.md"        = "ai"
    "DEEPSEEK_*.md"        = "ai"
    
    # Reference
    "TRADINGVIEW_*.md"     = "reference"
    "METRICS_*.md"         = "reference"
    "PARITY_*.md"          = "reference"
    "CIRCUIT_BREAKER_*.md" = "reference"
    "VECTORBT_*.md"        = "reference"
    
    # Guides
    "AUTOGENERATE_*.md"    = "guides"
    "DATABASE_*.md"        = "guides"
}

$movedCount = 0

# Get all .md files in docs root (not in subdirs)
$mdFiles = Get-ChildItem -Path $docsDir -Filter "*.md" -File

foreach ($file in $mdFiles) {
    if ($file.Name -eq "README.md" -or $file.Name -eq "QUICK_REFERENCE.md") {
        continue  # Keep these in root
    }
    
    $targetCategory = $null
    
    foreach ($pattern in $mappings.Keys) {
        if ($file.Name -like $pattern) {
            $targetCategory = $mappings[$pattern]
            break
        }
    }
    
    if ($targetCategory) {
        $destDir = Join-Path $docsDir $targetCategory
        $dest = Join-Path $destDir $file.Name
        Move-Item -Path $file.FullName -Destination $dest -Force
        Write-Host "  Moved: $($file.Name) -> $targetCategory/" -ForegroundColor Cyan
        $movedCount++
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  Documentation Reorganized!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Moved: $movedCount files" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Structure:" -ForegroundColor White
Write-Host "    docs/api/          - API documentation"
Write-Host "    docs/architecture/ - System design"
Write-Host "    docs/guides/       - User guides"
Write-Host "    docs/reference/    - Reference docs"
Write-Host "    docs/ai/           - AI agent docs"
Write-Host "    docs/archive/      - Historical docs"
Write-Host ""
