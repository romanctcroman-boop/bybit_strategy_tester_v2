# Запуск ngrok на порт 5000 (для прокси DeepSeek).
# Перед первым запуском:
#   1. Скачайте ngrok: https://ngrok.com/download
#   2. Добавьте токен: ngrok config add-authtoken ВАШ_ТОКЕН
#   3. Убедитесь, что прокси запущен: .\.venv\Scripts\python.exe scripts/deepseek_proxy.py
# Запуск: из корня проекта: .\scripts\run_ngrok_5000.ps1

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent

$ngrok = $null
foreach ($name in @("ngrok", "ngrok.exe")) {
    $ngrok = Get-Command $name -ErrorAction SilentlyContinue
    if ($ngrok) { break }
}
if (-not $ngrok) {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\ngrok\ngrok.exe",
        "$env:USERPROFILE\scoop\apps\ngrok\current\ngrok.exe",
        "$env:ProgramFiles\ngrok\ngrok.exe",
        "$ProjectRoot\scripts\ngrok.exe",
        "$ProjectRoot\scripts\ngrok\ngrok.exe"
    )
    if ($env:NGROK_EXE -and (Test-Path $env:NGROK_EXE)) {
        $paths += (Resolve-Path $env:NGROK_EXE).Path
    }
    foreach ($p in $paths) {
        if ($p -and (Test-Path $p)) { $ngrok = @{ Source = $p }; break }
    }
}

if (-not $ngrok) {
    Write-Host "ngrok not found." -ForegroundColor Red
    Write-Host "1. Download: https://ngrok.com/download" -ForegroundColor Yellow
    Write-Host "2. Put ngrok.exe in: $ProjectRoot\scripts\ (or add to PATH)" -ForegroundColor Yellow
    Write-Host "3. Add token: ngrok config add-authtoken YOUR_TOKEN" -ForegroundColor Yellow
    Write-Host "4. Run this script again or: ngrok http 5000" -ForegroundColor Yellow
    exit 1
}

$exe = if ($ngrok.Source) { $ngrok.Source } else { $ngrok.Path }
Write-Host "Starting: $exe http 5000" -ForegroundColor Cyan
Write-Host "Public URL will appear below. Put it in Cursor: Override OpenAI Base URL" -ForegroundColor Green
Write-Host ""

Set-Location $ProjectRoot
& $exe http 5000
