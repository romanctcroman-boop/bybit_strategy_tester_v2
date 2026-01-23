# ==============================================================================
# Environment Validation Script
# ==============================================================================
# Validates that all required environment variables are set
# Run before starting the application: .\scripts\validate_env.ps1
# ==============================================================================

$ErrorActionPreference = "Continue"

# Required environment variables
$requiredVars = @(
    @{ Name = "BYBIT_API_KEY"; Description = "Bybit API Key (encrypted or plain)" },
    @{ Name = "BYBIT_API_SECRET"; Description = "Bybit API Secret (encrypted or plain)" }
)

# Optional but recommended
$recommendedVars = @(
    @{ Name = "DEEPSEEK_API_KEYS"; Description = "DeepSeek API keys for AI analysis" },
    @{ Name = "PERPLEXITY_API_KEYS"; Description = "Perplexity API keys for research" },
    @{ Name = "ENCRYPTION_KEY"; Description = "Key for encrypting API credentials" },
    @{ Name = "REDIS_URL"; Description = "Redis connection URL" },
    @{ Name = "DATABASE_URL"; Description = "Database connection URL" }
)

# Load .env file if exists
$envFile = ".env"
$envVars = @{}

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            $envVars[$key] = $value
        }
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Environment Validation" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# Check required variables
Write-Host "REQUIRED:" -ForegroundColor Yellow
foreach ($var in $requiredVars) {
    $value = $envVars[$var.Name]
    if ([string]::IsNullOrEmpty($value)) {
        Write-Host "  [X] $($var.Name)" -ForegroundColor Red
        Write-Host "      $($var.Description)" -ForegroundColor Gray
        $errors++
    }
    else {
        $maskedValue = if ($value.Length -gt 8) { $value.Substring(0, 4) + "****" + $value.Substring($value.Length - 4) } else { "****" }
        Write-Host "  [OK] $($var.Name) = $maskedValue" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "RECOMMENDED:" -ForegroundColor Yellow
foreach ($var in $recommendedVars) {
    $value = $envVars[$var.Name]
    if ([string]::IsNullOrEmpty($value)) {
        Write-Host "  [!] $($var.Name)" -ForegroundColor DarkYellow
        Write-Host "      $($var.Description)" -ForegroundColor Gray
        $warnings++
    }
    else {
        $maskedValue = if ($value.Length -gt 8) { $value.Substring(0, 4) + "****" + $value.Substring($value.Length - 4) } else { "****" }
        Write-Host "  [OK] $($var.Name) = $maskedValue" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan

if ($errors -gt 0) {
    Write-Host "  FAILED: $errors required variable(s) missing" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Copy .env.example to .env and fill in the values:" -ForegroundColor White
    Write-Host "    Copy-Item .env.example .env" -ForegroundColor Gray
    Write-Host ""
    exit 1
}
elseif ($warnings -gt 0) {
    Write-Host "  PASSED with $warnings warning(s)" -ForegroundColor Yellow
    Write-Host ""
}
else {
    Write-Host "  ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host ""
}
