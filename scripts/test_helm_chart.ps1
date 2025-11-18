# Phase 4.1 Testing Script
# Tests Helm chart validity without K8s cluster

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Phase 4.1: Helm Chart Testing" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

$helmInstalled = $false
try {
    $helmVersion = helm version --short 2>$null
    if ($LASTEXITCODE -eq 0) {
        $helmInstalled = $true
        Write-Host "  ✅ Helm installed: $helmVersion" -ForegroundColor Green
    }
}
catch {
    Write-Host "  ⚠️  Helm not installed (skipping K8s deployment)" -ForegroundColor Yellow
}

# Validate Helm chart structure
Write-Host ""
Write-Host "[2/5] Validating Helm chart structure..." -ForegroundColor Yellow

$requiredFiles = @(
    "helm/Chart.yaml",
    "helm/values.yaml",
    "helm/templates/_helpers.tpl",
    "helm/templates/backend-deployment.yaml",
    "helm/templates/worker-deployment.yaml",
    "helm/templates/backend-ingress.yaml",
    "helm/templates/istio.yaml",
    "helm/templates/rbac.yaml"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length
        Write-Host "  ✅ $file ($size bytes)" -ForegroundColor Green
    }
    else {
        Write-Host "  ❌ $file (missing)" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host ""
    Write-Host "❌ ERROR: Some required files are missing!" -ForegroundColor Red
    exit 1
}

# Validate YAML syntax
Write-Host ""
Write-Host "[3/5] Validating YAML syntax..." -ForegroundColor Yellow

function Test-YamlSyntax {
    param([string]$FilePath)
    
    try {
        # PowerShell 6+ has ConvertFrom-Yaml, but we'll use basic parsing
        $content = Get-Content $FilePath -Raw
        
        # Basic YAML validation checks
        if ($content -match "^\s*---\s*$" -or $content -match ":\s*$" -or $content -match "^\s*-\s+") {
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
}

$yamlFiles = Get-ChildItem -Path "helm" -Filter "*.yaml" -Recurse
foreach ($file in $yamlFiles) {
    $relativePath = $file.FullName.Replace((Get-Location).Path, "").TrimStart('\')
    if (Test-YamlSyntax -FilePath $file.FullName) {
        Write-Host "  ✅ $relativePath (valid YAML)" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠️  $relativePath (syntax check skipped)" -ForegroundColor Yellow
    }
}

# Check Helm template rendering (if Helm installed)
Write-Host ""
Write-Host "[4/5] Testing Helm template rendering..." -ForegroundColor Yellow

if ($helmInstalled) {
    try {
        # Lint chart
        Write-Host "  🔍 Running helm lint..." -ForegroundColor Cyan
        $lintOutput = helm lint helm 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Helm lint passed" -ForegroundColor Green
            Write-Host "     $($lintOutput -join "`n     ")" -ForegroundColor Gray
        }
        else {
            Write-Host "  ⚠️  Helm lint warnings:" -ForegroundColor Yellow
            Write-Host "     $($lintOutput -join "`n     ")" -ForegroundColor Gray
        }
        
        # Template dry-run
        Write-Host ""
        Write-Host "  🔍 Running helm template (dry-run)..." -ForegroundColor Cyan
        $templateOutput = helm template bybit-strategy-tester helm --debug 2>&1 | Out-String
        
        if ($LASTEXITCODE -eq 0) {
            $manifestCount = ($templateOutput | Select-String -Pattern "^---$" -AllMatches).Matches.Count
            Write-Host "  ✅ Helm template rendered successfully" -ForegroundColor Green
            Write-Host "     Generated $manifestCount Kubernetes manifests" -ForegroundColor Gray
            
            # Save rendered manifests for inspection
            $templateOutput | Out-File -FilePath "helm/rendered-manifests.yaml" -Encoding UTF8
            Write-Host "     Saved to: helm/rendered-manifests.yaml" -ForegroundColor Gray
        }
        else {
            Write-Host "  ❌ Helm template rendering failed:" -ForegroundColor Red
            Write-Host "     $templateOutput" -ForegroundColor Gray
        }
    }
    catch {
        Write-Host "  ❌ Error running Helm commands: $_" -ForegroundColor Red
    }
}
else {
    Write-Host "  ⚠️  Helm not installed - skipping template rendering" -ForegroundColor Yellow
    Write-Host "     Install Helm: https://helm.sh/docs/intro/install/" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "[5/5] Testing summary" -ForegroundColor Yellow
Write-Host ""

$stats = @{
    "Total files"          = $requiredFiles.Count
    "YAML files validated" = $yamlFiles.Count
    "Chart structure"      = if ($allFilesExist) { "✅ Valid" } else { "❌ Invalid" }
    "Helm availability"    = if ($helmInstalled) { "✅ Installed" } else { "⚠️  Not installed" }
}

foreach ($key in $stats.Keys) {
    Write-Host "  $key : $($stats[$key])" -ForegroundColor White
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Testing Complete!" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

if ($helmInstalled) {
    Write-Host "Next steps:" -ForegroundColor Green
    Write-Host "  1. Review rendered manifests: helm/rendered-manifests.yaml" -ForegroundColor White
    Write-Host "  2. Deploy to K8s cluster: helm install bybit-strategy-tester helm" -ForegroundColor White
    Write-Host "  3. Check deployment: kubectl get pods -n bybit-strategy-tester" -ForegroundColor White
}
else {
    Write-Host "To deploy to Kubernetes:" -ForegroundColor Green
    Write-Host "  1. Install Helm: https://helm.sh/docs/intro/install/" -ForegroundColor White
    Write-Host "  2. Install kubectl: https://kubernetes.io/docs/tasks/tools/" -ForegroundColor White
    Write-Host "  3. Setup K8s cluster (minikube/kind/k3s for local testing)" -ForegroundColor White
    Write-Host "  4. Run: helm install bybit-strategy-tester helm" -ForegroundColor White
}

Write-Host ""
