<#
.SYNOPSIS
  Start/stop/status/tail a uvicorn FastAPI app on Windows (PowerShell).

.DESCRIPTION
  Provides simple commands to start uvicorn in the background (writes PID to .uvicorn.pid),
  stop it, show status, and tail the stdout log.

  Usage examples:
    # start server
    .\start_uvicorn.ps1 start -AppModule 'backend.api.app:app' -Host '127.0.0.1' -Port 8000

    # check status
    .\start_uvicorn.ps1 status

    # stop server
    .\start_uvicorn.ps1 stop

    # tail logs
    .\start_uvicorn.ps1 tail

#>

param(
    [Parameter(Mandatory = $false)][ValidateSet('start', 'stop', 'status', 'tail')]
    [string]$Action = 'start',

    [string]$AppModule = 'backend.api.app:app',
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000,
    [string]$PidFile = '.uvicorn.pid',
    [string]$OutLog = 'logs/uvicorn.out.log',
    [string]$ErrLog = 'logs/uvicorn.err.log'
)

function EnsureLogsDir {
    $dir = Split-Path $OutLog -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

switch ($Action) {
    'start' {
    EnsureLogsDir
        if (Test-Path $PidFile) {
            try {
                $oldPid = Get-Content $PidFile -ErrorAction Stop
                if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
                    Write-Output "Uvicorn already running with PID $oldPid"
                    break
                }
                else {
                    Remove-Item $PidFile -ErrorAction SilentlyContinue
                }
            }
            catch { }
        }

        $uvicornExe = Join-Path $PWD '.venv\Scripts\uvicorn.exe'
        if (-not (Test-Path $uvicornExe)) {
            Write-Error "uvicorn executable not found at $uvicornExe"
            break
        }

    $uvArgs = @($AppModule, '--host', $BindHost, '--port', $Port)

    $proc = Start-Process -FilePath $uvicornExe -ArgumentList $uvArgs -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        Start-Sleep -Milliseconds 800
        $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
        Write-Output "Started uvicorn (PID $($proc.Id)). Logs: $OutLog, $ErrLog"
    }

    'status' {
        if (-not (Test-Path $PidFile)) { Write-Output "No pid file ($PidFile) found."; break }
        $pidVal = Get-Content $PidFile
        $p = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($p) { Write-Output "Running: PID $pidVal ($($p.ProcessName))" } else { Write-Output "PID $pidVal not running." }
    }

    'stop' {
        if (-not (Test-Path $PidFile)) { Write-Output "No pid file ($PidFile) found."; break }
        $pidVal = Get-Content $PidFile
        try { Stop-Process -Id $pidVal -Force -ErrorAction Stop; Remove-Item $PidFile -ErrorAction SilentlyContinue; Write-Output "Stopped PID $pidVal" } catch { Write-Output ('Failed to stop PID ' + $pidVal + ': ' + $_) }
    }

    'tail' {
        if (-not (Test-Path $OutLog)) { Write-Output "No output log at $OutLog"; break }
        Get-Content $OutLog -Tail 200 -Wait
    }
}
