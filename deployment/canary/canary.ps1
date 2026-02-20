#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Canary deployment management script.

.DESCRIPTION
    Manages progressive canary rollout stages for Bybit Strategy Tester.
    Stages: 10% → 25% → 50% → 100% with automatic health checks.

.PARAMETER Action
    One of: deploy, promote, rollback, status

.EXAMPLE
    .\canary.ps1 deploy    # Deploy canary at 10%
    .\canary.ps1 promote   # Advance to next stage
    .\canary.ps1 rollback  # Roll back canary
    .\canary.ps1 status    # Check current canary state
#>

param(
    [Parameter(Mandatory)]
    [ValidateSet("deploy", "promote", "rollback", "status")]
    [string]$Action,

    [string]$Namespace = "bybit",
    [string]$Image = "ghcr.io/romanctcroman-boop/bybit-strategy-tester:canary",
    [int]$HealthCheckWaitSeconds = 60
)

$ErrorActionPreference = "Stop"

$Stages = @(
    @{ Name = "Stage 1"; Canary = 10; Stable = 90 }
    @{ Name = "Stage 2"; Canary = 25; Stable = 75 }
    @{ Name = "Stage 3"; Canary = 50; Stable = 50 }
    @{ Name = "Stage 4"; Canary = 100; Stable = 0 }
)

function Get-CanaryStatus {
    Write-Host "`n=== Canary Deployment Status ===" -ForegroundColor Cyan
    kubectl get deployments -n $Namespace -l "app=bybit-strategy-tester" -o wide
    Write-Host ""
    kubectl get pods -n $Namespace -l "track=canary" -o wide
    Write-Host ""
    kubectl get virtualservice bybit-strategy-tester-vs -n $Namespace -o yaml 2>$null |
    Select-String "weight"
}

function Deploy-Canary {
    Write-Host "Deploying canary at Stage 1 (10% traffic)..." -ForegroundColor Yellow

    # Apply canary deployment
    kubectl apply -f "$PSScriptRoot\canary-deployment.yaml" -n $Namespace
    kubectl set image deployment/bybit-strategy-tester-canary `
        backend=$Image -n $Namespace

    # Wait for rollout
    kubectl rollout status deployment/bybit-strategy-tester-canary `
        -n $Namespace --timeout=120s

    # Apply traffic splitting (10%)
    kubectl apply -f "$PSScriptRoot\canary-virtualservice.yaml" -n $Namespace

    # Apply rollback rules
    kubectl apply -f "$PSScriptRoot\canary-rollback-rules.yaml" -n $Namespace

    Write-Host "`nCanary deployed at 10% traffic." -ForegroundColor Green
    Write-Host "Monitor for $HealthCheckWaitSeconds seconds before promoting..."
    Start-Sleep -Seconds $HealthCheckWaitSeconds

    # Health check
    $health = kubectl exec -n $Namespace deployment/bybit-strategy-tester-canary `
        -- curl -s http://localhost:8000/api/v1/health 2>$null
    if ($health -match '"status":\s*"healthy"') {
        Write-Host "Health check PASSED" -ForegroundColor Green
    }
    else {
        Write-Host "Health check FAILED - consider rolling back" -ForegroundColor Red
    }
}

function Rollback-Canary {
    Write-Host "Rolling back canary deployment..." -ForegroundColor Red

    # Scale canary to 0
    kubectl scale deployment/bybit-strategy-tester-canary --replicas=0 -n $Namespace

    # Route 100% to stable
    kubectl delete virtualservice bybit-strategy-tester-vs -n $Namespace 2>$null

    Write-Host "Canary rolled back. 100% traffic on stable." -ForegroundColor Green
}

switch ($Action) {
    "deploy" { Deploy-Canary }
    "promote" {
        Write-Host "Promote: update canary-virtualservice.yaml weights and re-apply." -ForegroundColor Yellow
        Write-Host "Stages: 10% → 25% → 50% → 100%"
        foreach ($s in $Stages) {
            Write-Host "  $($s.Name): canary=$($s.Canary)%, stable=$($s.Stable)%"
        }
    }
    "rollback" { Rollback-Canary }
    "status" { Get-CanaryStatus }
}
