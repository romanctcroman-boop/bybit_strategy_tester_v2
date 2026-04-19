# DeepSeek proxy for Cursor (Base URL: http://localhost:5000)
# Key from DEEPSEEK_API_KEY env or .env in project root

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $root)) { $root = (Get-Location).Path }
Set-Location $root

$envPath = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"

if (-not (Test-Path $envPath)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envPath
        Write-Host "Created .env from .env.example" -ForegroundColor Green
        Write-Host "Open .env and set DEEPSEEK_API_KEY=sk-... (get key: https://platform.deepseek.com)" -ForegroundColor Yellow
        Write-Host "Then run again: .\scripts\run_deepseek_proxy.ps1" -ForegroundColor Cyan
        exit 1
    }
}

if (Test-Path $envPath) {
    Get-Content $envPath -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*DEEPSEEK_API_KEY\s*=\s*(.+)$') {
            $v = $matches[1].Trim().Trim('"').Trim("'")
            if ($v -and $v -notmatch 'YOUR_DEEPSEEK|sk-YOUR_|placeholder') { $env:DEEPSEEK_API_KEY = $v }
        }
    }
}

if (-not $env:DEEPSEEK_API_KEY -or $env:DEEPSEEK_API_KEY -match 'YOUR_|placeholder') {
    Write-Host "DEEPSEEK_API_KEY not set or still placeholder. Open .env and set DEEPSEEK_API_KEY=sk-..." -ForegroundColor Yellow
    Write-Host "Or: `$env:DEEPSEEK_API_KEY = 'sk-...'" -ForegroundColor Gray
    exit 1
}

Write-Host "Starting proxy on port 5000..." -ForegroundColor Cyan
Write-Host "Cursor: Base URL = http://localhost:5000 , API Key = any" -ForegroundColor Gray
$script = "scripts/deepseek_proxy.py"
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.14 $script } else { & python $script }
