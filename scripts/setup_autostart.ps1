<#
.SYNOPSIS
    Setup Windows auto-start for DB Maintenance services

.DESCRIPTION
    Creates Windows Scheduled Tasks to start services on system boot.
    Services will run even without VS Code open.

.PARAMETER Action
    install   - Install scheduled tasks
    uninstall - Remove scheduled tasks
    status    - Show current status
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "uninstall", "status")]
    [string]$Action = "status"
)

$ProjectRoot = "D:\bybit_strategy_tester_v2"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"  # pythonw = no console window
$TaskPrefix = "BybitStrategyTester"

$Services = @(
    @{
        Name        = "KlineDBService"
        Script      = Join-Path $ProjectRoot "backend\services\kline_db_service.py"
        Description = "Kline Database Service - handles market data storage"
    },
    @{
        Name        = "DBMaintenanceServer"
        Script      = Join-Path $ProjectRoot "backend\services\db_maintenance_server.py"
        Args        = "--port 8001"
        Description = "DB Maintenance Server - scheduled tasks, gap repair, retention"
    }
)

function Install-Services {
    Write-Host ""
    Write-Host "Installing Windows Scheduled Tasks..." -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan

    foreach ($svc in $Services) {
        $taskName = "$TaskPrefix-$($svc.Name)"
        
        # Remove existing task if exists
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Host "  Removed existing task: $taskName" -ForegroundColor Yellow
        }

        # Build arguments
        $taskArgs = $svc.Script
        if ($svc.Args) {
            $taskArgs = "$($svc.Script) $($svc.Args)"
        }

        # Create action
        $action = New-ScheduledTaskAction -Execute $VenvPython -Argument $taskArgs -WorkingDirectory $ProjectRoot

        # Trigger: at system startup + 60 seconds delay
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Delay = "PT60S"  # 60 second delay to let system settle

        # Settings
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1)

        # Principal (run as current user)
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

        # Register task
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description $svc.Description | Out-Null

        Write-Host "  Installed: $taskName" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "All services installed for auto-start on boot!" -ForegroundColor Green
    Write-Host ""
    Write-Host "NOTE: Services will start 60 seconds after Windows boots." -ForegroundColor Yellow
    Write-Host "      You can also start them manually from Task Scheduler." -ForegroundColor Yellow
    Write-Host ""
}

function Uninstall-Services {
    Write-Host ""
    Write-Host "Removing Windows Scheduled Tasks..." -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan

    foreach ($svc in $Services) {
        $taskName = "$TaskPrefix-$($svc.Name)"
        
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existing) {
            # Stop if running
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Host "  Removed: $taskName" -ForegroundColor Green
        }
        else {
            Write-Host "  Not found: $taskName" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "All scheduled tasks removed." -ForegroundColor Green
    Write-Host ""
}

function Show-Status {
    Write-Host ""
    Write-Host "Windows Scheduled Tasks Status" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host ""

    $anyInstalled = $false
    
    foreach ($svc in $Services) {
        $taskName = "$TaskPrefix-$($svc.Name)"
        
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        
        Write-Host "  $($svc.Name):" -NoNewline
        
        if ($task) {
            $anyInstalled = $true
            $state = $task.State
            $color = switch ($state) {
                "Running" { "Green" }
                "Ready" { "Cyan" }
                "Disabled" { "Yellow" }
                default { "Gray" }
            }
            Write-Host " $state" -ForegroundColor $color
            
            # Get last run info
            $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            if ($info.LastRunTime -and $info.LastRunTime -ne [DateTime]::MinValue) {
                Write-Host "    Last run: $($info.LastRunTime)" -ForegroundColor Gray
                Write-Host "    Result: $($info.LastTaskResult)" -ForegroundColor Gray
            }
        }
        else {
            Write-Host " NOT INSTALLED" -ForegroundColor Red
        }
    }

    Write-Host ""
    
    if (-not $anyInstalled) {
        Write-Host "No services installed for auto-start." -ForegroundColor Yellow
        Write-Host "Run '.\setup_autostart.ps1 install' to enable auto-start on boot." -ForegroundColor Yellow
    }
    
    Write-Host ""
}

# Main
switch ($Action) {
    "install" { Install-Services }
    "uninstall" { Uninstall-Services }
    "status" { Show-Status }
}
