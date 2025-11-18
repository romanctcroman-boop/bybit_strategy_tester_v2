# Disable Docker Extension in VS Code Workspace
# This script creates a workspace-specific settings to disable Docker extension

$settingsPath = ".vscode\settings.json"

Write-Host "================================================================================"
Write-Host "  Disabling Docker Extension"
Write-Host "================================================================================"

Write-Host "`nCurrent settings file: $settingsPath"

if (Test-Path $settingsPath) {
    Write-Host "[OK] Settings file exists"
    
    # Read current settings
    $content = Get-Content $settingsPath -Raw
    
    # Check if Docker settings already exist
    if ($content -match '"docker\.') {
        Write-Host "[INFO] Docker settings already present in file"
    }
    
    Write-Host "`n[ACTION REQUIRED] Manual steps to disable Docker extension:"
    Write-Host ""
    Write-Host "1. Press: Ctrl+Shift+X (Open Extensions)"
    Write-Host "2. In search box, type: @installed docker"
    Write-Host "3. Find: 'Docker' or 'Docker Labs AI Tools'"
    Write-Host "4. Click gear icon (settings)"
    Write-Host "5. Select: 'Disable (Workspace)'"
    Write-Host "6. Reload VS Code: Ctrl+Shift+P -> 'Developer: Reload Window'"
    Write-Host ""
    
    Write-Host "================================================================================"
    Write-Host "  Alternative: Add to Extensions Ignore List"
    Write-Host "================================================================================"
    
    Write-Host "`nYou can also add this to .vscode/extensions.json:"
    Write-Host ""
    Write-Host '  "unwantedRecommendations": ['
    Write-Host '    "ms-azuretools.vscode-docker",'
    Write-Host '    "docker.labs-ai-tools-vscode"'
    Write-Host '  ]'
    Write-Host ""
    
}
else {
    Write-Host "[ERROR] Settings file not found: $settingsPath"
}

Write-Host "================================================================================"
Write-Host "  Quick Check: Is Docker Desktop Running?"
Write-Host "================================================================================"

$dockerProcess = Get-Process | Where-Object { $_.ProcessName -like "*Docker*" }

if ($dockerProcess) {
    Write-Host "`n[INFO] Docker Desktop is running:"
    $dockerProcess | Select-Object ProcessName, Id | Format-Table
    Write-Host "[INFO] If you don't need Docker, you can close Docker Desktop"
}
else {
    Write-Host "`n[INFO] Docker Desktop is NOT running"
    Write-Host "[INFO] This is why the Docker LSP extension is crashing"
}

Write-Host "`n================================================================================"
Write-Host ""
Write-Host "[RECOMMENDATION] Since you don't use Docker in this project:"
Write-Host "  1. Disable the Docker extension (steps above)"
Write-Host "  2. OR close Docker Desktop if it's running"
Write-Host "  3. Reload VS Code"
Write-Host ""
Write-Host "================================================================================"
