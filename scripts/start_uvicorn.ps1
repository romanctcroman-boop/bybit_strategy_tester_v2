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
    [string]$DatabaseUrl = $null,
    [string]$PidFile = '.uvicorn.pid',
    [string]$OutLog = 'logs/uvicorn.out.log',
    [string]$ErrLog = 'logs/uvicorn.err.log'
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path $scriptDirectory -Parent
$envoyStatus = $null
$envoyHelper = Join-Path $projectRoot 'scripts\set_envoy_proxy_env.ps1'
if (Test-Path $envoyHelper) {
    . $envoyHelper
    try {
        $envoyStatus = Set-EnvoyProxyEnv
    }
    catch {
        $envoyStatus = $null
    }
}

function EnsureLogsDir {
    $dir = Split-Path $OutLog -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

switch ($Action) {
    'start' {
        EnsureLogsDir
        if ($envoyStatus -and ($envoyStatus.PerplexityRouted -or $envoyStatus.DeepSeekRouted)) {
            $perplexityMode = if ($envoyStatus.PerplexityRouted) { 'sidecar' } else { 'direct' }
            $deepseekMode = if ($envoyStatus.DeepSeekRouted) { 'sidecar' } else { 'direct' }
            Write-Output "Envoy sidecar in use (perplexity=$perplexityMode, deepseek=$deepseekMode). Override PERPLEXITY/DEEPSEEK_* env vars to bypass."
        }
        if ($DatabaseUrl) {
            $env:DATABASE_URL = $DatabaseUrl
            Write-Output "Using DATABASE_URL for uvicorn: $($DatabaseUrl -replace '://([^:]+):([^@]+)@', '://$1:****@')"
        }
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
        $pythonExe = Join-Path $PWD '.venv\Scripts\python.exe'
        $proc = $null
        if (Test-Path $uvicornExe) {
            $uvArgs = @($AppModule, '--host', $BindHost, '--port', $Port)
            $proc = Start-Process -FilePath $uvicornExe -ArgumentList $uvArgs -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        }
        elseif (Test-Path $pythonExe) {
            $uvArgs = @('-m', 'uvicorn', $AppModule, '--host', $BindHost, '--port', $Port)
            $proc = Start-Process -FilePath $pythonExe -ArgumentList $uvArgs -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        }
        else {
            Write-Warning "Neither $uvicornExe nor $pythonExe found. Falling back to system 'python -m uvicorn'"
            $uvArgs = @('-m', 'uvicorn', $AppModule, '--host', $BindHost, '--port', $Port)
            $proc = Start-Process -FilePath 'python' -ArgumentList $uvArgs -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        }
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
