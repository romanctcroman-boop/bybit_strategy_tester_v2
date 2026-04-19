# Production Deployment Script
# For Bybit Strategy Tester v2
#
# Usage:
#   .\scripts\deploy.ps1 -Environment production
#   .\scripts\deploy.ps1 -Environment staging
#   .\scripts\deploy.ps1 -Environment local

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('local', 'staging', 'production')]
    [string]$Environment,
    
    [switch]$SkipTests,
    
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# Configuration
$Config = @{
    local = @{
        Namespace = 'default'
        Replicas = 1
        ImageTag = 'local'
        URL = 'http://localhost:8000'
    }
    staging = @{
        Namespace = 'staging'
        Replicas = 2
        ImageTag = 'staging'
        URL = 'https://staging.bybit-strategy-tester.com'
    }
    production = @{
        Namespace = 'production'
        Replicas = 3
        ImageTag = 'latest'
        URL = 'https://api.bybit-strategy-tester.com'
    }
}

$EnvConfig = $Config[$Environment]

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester v2 - Production Deployment" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Namespace: $($EnvConfig.Namespace)" -ForegroundColor Yellow
Write-Host "Replicas: $($EnvConfig.Replicas)" -ForegroundColor Yellow
Write-Host "Image Tag: $($EnvConfig.ImageTag)" -ForegroundColor Yellow
Write-Host ""

# Step 1: Pre-deployment checks
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Step 1: Pre-deployment Checks" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check Docker
Write-Host "Checking Docker..." -NoNewline
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerVersion = docker --version
    Write-Host " ✅ $dockerVersion" -ForegroundColor Green
} else {
    Write-Host " ❌ Docker not installed!" -ForegroundColor Red
    exit 1
}

# Check kubectl
Write-Host "Checking kubectl..." -NoNewline
if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    $kubectlVersion = kubectl version --client 2>&1 | Select-Object -First 1
    Write-Host " ✅ $kubectlVersion" -ForegroundColor Green
} else {
    Write-Host " ❌ kubectl not installed!" -ForegroundColor Red
    exit 1
}

# Check Python (for smoke tests)
Write-Host "Checking Python..." -NoNewline
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Host " ✅ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host " ⚠️  Python not found (smoke tests will be skipped)" -ForegroundColor Yellow
}

Write-Host ""

# Step 2: Run tests
if (-not $SkipTests) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Step 2: Running Tests" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    
    Write-Host "Running pytest..." -NoNewline
    $testResult = .\.venv\Scripts\python.exe -m pytest tests/ -x -q --tb=short 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ All tests passed" -ForegroundColor Green
    } else {
        Write-Host " ❌ Tests failed!" -ForegroundColor Red
        Write-Host $testResult
        exit 1
    }
    
    Write-Host ""
} else {
    Write-Host "⚠️  Skipping tests (--SkipTests)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 3: Build Docker image
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Step 3: Building Docker Image" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "[DRY RUN] Would build Docker image" -ForegroundColor Gray
} else {
    Write-Host "Building image: bybit-strategy-tester:$($EnvConfig.ImageTag)..." -NoNewline
    docker build -t bybit-strategy-tester:$($EnvConfig.ImageTag) . 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Image built successfully" -ForegroundColor Green
    } else {
        Write-Host " ❌ Docker build failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Step 4: Deploy to Kubernetes
if ($Environment -eq 'local') {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Step 4: Local Deployment (Docker Compose)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "[DRY RUN] Would start Docker Compose" -ForegroundColor Gray
    } else {
        Write-Host "Starting Docker Compose..." -NoNewline
        docker-compose up -d 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅ Docker Compose started" -ForegroundColor Green
        } else {
            Write-Host " ❌ Docker Compose failed!" -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Step 4: Kubernetes Deployment" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    
    # Check cluster connection
    Write-Host "Checking Kubernetes cluster connection..." -NoNewline
    if ($DryRun) {
        Write-Host "[DRY RUN]" -ForegroundColor Gray
    } else {
        $clusterInfo = kubectl cluster-info 2>&1 | Select-Object -First 1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅ Connected" -ForegroundColor Green
        } else {
            Write-Host " ❌ Cannot connect to cluster!" -ForegroundColor Red
            exit 1
        }
    }
    
    # Create namespace if not exists
    Write-Host "Creating namespace $($EnvConfig.Namespace)..." -NoNewline
    if ($DryRun) {
        Write-Host "[DRY RUN]" -ForegroundColor Gray
    } else {
        kubectl create namespace $($EnvConfig.Namespace) --dry-run=client -o yaml 2>&1 | kubectl apply -f - 2>&1 | Out-Null
        Write-Host " ✅ Namespace ready" -ForegroundColor Green
    }
    
    # Apply deployment
    Write-Host "Applying deployment..." -NoNewline
    if ($DryRun) {
        Write-Host "[DRY RUN]" -ForegroundColor Gray
    } else {
        # Update replicas in deployment
        $deploymentYaml = Get-Content "deployment\kubernetes\deployment.yml" -Raw
        $deploymentYaml = $deploymentYaml -replace 'replicas: \d+', "replicas: $($EnvConfig.Replicas)"
        $deploymentYaml | kubectl apply -f - -n $($EnvConfig.Namespace) 2>&1 | Out-Null
        Write-Host " ✅ Deployment applied" -ForegroundColor Green
    }
    
    # Wait for rollout
    Write-Host "Waiting for rollout..." -NoNewline
    if ($DryRun) {
        Write-Host "[DRY RUN]" -ForegroundColor Gray
    } else {
        kubectl rollout status deployment/bybit-strategy-tester -n $($EnvConfig.Namespace) --timeout=300s 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅ Rollout complete" -ForegroundColor Green
        } else {
            Write-Host " ⚠️  Rollout timeout (checking pods anyway)" -ForegroundColor Yellow
        }
    }
    
    # Check pod status
    Write-Host "Checking pod status..."
    if ($DryRun) {
        Write-Host "[DRY RUN] Would show pods" -ForegroundColor Gray
    } else {
        kubectl get pods -l app=bybit-strategy-tester -n $($EnvConfig.Namespace)
    }
}

Write-Host ""

# Step 5: Run smoke tests
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Step 5: Smoke Tests" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "[DRY RUN] Would run smoke tests" -ForegroundColor Gray
} else {
    Write-Host "Running smoke tests against $Environment..."
    
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $smokeResult = python scripts/smoke_tests.py --environment $Environment --output "smoke_test_results_$Environment.json" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Smoke tests passed!" -ForegroundColor Green
            Write-Host "Results saved to: smoke_test_results_$Environment.json" -ForegroundColor Gray
        } else {
            Write-Host "⚠️  Some smoke tests failed (review results)" -ForegroundColor Yellow
            Write-Host $smokeResult
        }
    } else {
        Write-Host "⚠️  Python not found, skipping smoke tests" -ForegroundColor Yellow
    }
}

Write-Host ""

# Step 6: Post-deployment summary
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Deployment Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Environment:     $Environment" -ForegroundColor White
Write-Host "Namespace:       $($EnvConfig.Namespace)" -ForegroundColor White
Write-Host "Replicas:        $($EnvConfig.Replicas)" -ForegroundColor White
Write-Host "Image Tag:       $($EnvConfig.ImageTag)" -ForegroundColor White
Write-Host "URL:             $($EnvConfig.URL)" -ForegroundColor White
Write-Host ""

if ($Environment -ne 'local' -and -not $DryRun) {
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  kubectl get pods -n $($EnvConfig.Namespace)" -ForegroundColor Gray
    Write-Host "  kubectl logs -l app=bybit-strategy-tester -n $($EnvConfig.Namespace)" -ForegroundColor Gray
    Write-Host "  kubectl describe deployment bybit-strategy-tester -n $($EnvConfig.Namespace)" -ForegroundColor Gray
    Write-Host "  kubectl rollout undo deployment/bybit-strategy-tester -n $($EnvConfig.Namespace)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ✅ Deployment Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
