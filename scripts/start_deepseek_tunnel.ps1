# Туннель к прокси DeepSeek (обход ssrf_blocked в Cursor).
# Запуск: из корня проекта: .\scripts\start_deepseek_tunnel.ps1
# Требуется: прокси уже запущен (scripts/deepseek_proxy.py на порту 5000).

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent

Write-Host ""
Write-Host "DeepSeek tunnel (обход ssrf_blocked)" -ForegroundColor Cyan
Write-Host "Убедитесь, что прокси запущен: .\.venv\Scripts\python.exe scripts/deepseek_proxy.py" -ForegroundColor Yellow
Write-Host ""

# Пробуем localtunnel (npx)
Write-Host "Запуск localtunnel на порт 5000..." -ForegroundColor Cyan
Write-Host "Публичный URL появится ниже. Вставьте его в Cursor: Override OpenAI Base URL" -ForegroundColor Green
Write-Host ""

Set-Location $ProjectRoot
npx --yes localtunnel --port 5000
