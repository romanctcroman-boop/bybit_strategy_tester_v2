# ============================================
# Uvicorn Service Controller (Windows / PowerShell)
# ============================================
# Provides: start | stop | status | tail
#
# Why this exists:
# - VS Code tasks run scripts as plain commands. On Windows PowerShell you must
#   call scripts via the call operator (&) or with -File.
# - We keep PID/log files so status/stop work reliably.
# - We wait for port 8000 to start listening to avoid "task succeeded" while
#   the server immediately crashed.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'tail')]
    [string]$Action = 'status',

    [string]$AppModule = 'backend.api.app:app',
    [string]$BindHost = '0.0.0.0',
    [int]$Port = 8000,
    [int]$Workers = 4,

    [int]$StartupTimeoutSeconds = 120
)

$ErrorActionPreference = 'Continue'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Try .venv314 first, then fall back to .venv
$VenvPython314 = Join-Path $ProjectRoot '.venv314\Scripts\python.exe'
$VenvPythonLegacy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (Test-Path $VenvPython314) {
    $VenvPython = $VenvPython314
}
else {
    $VenvPython = $VenvPythonLegacy
}

$StateDir = Join-Path $ProjectRoot '.run'
$PidFile = Join-Path $StateDir 'uvicorn.pid'
$LogFile = Join-Path $StateDir 'uvicorn.log'

function Set-StateDir {
    if (-not (Test-Path $StateDir)) {
        New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    }
}

function Get-UvicornPid {
    if (Test-Path $PidFile) {
        try {
            $uvicornPid = (Get-Content $PidFile -ErrorAction Stop | Select-Object -First 1).Trim()
            if ($uvicornPid -match '^\d+$') { return [int]$uvicornPid }
        }
        catch {}
    }
    return $null
}

function Test-PidAlive([int]$TargetPid) {
    try { Get-Process -Id $TargetPid -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}

function Get-ListenerPid([int]$port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($null -ne $conn) { return [int]$conn.OwningProcess }
    }
    catch {}
    return $null
}

function Wait-For-Listen([int]$port, [int]$timeoutSeconds) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSeconds) {
        $listenerPid = Get-ListenerPid -port $port
        if ($listenerPid) { return $listenerPid }
        Start-Sleep -Milliseconds 300
    }
    return $null
}

switch ($Action) {
    'start' {
        Set-StateDir

        # Add CUDA to PATH for GPU acceleration
        $cudaPath = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin"
        if (Test-Path $cudaPath) {
            $env:PATH = "$cudaPath;$env:PATH"
            Write-Host "[INFO] CUDA path added: $cudaPath" -ForegroundColor Cyan
        }

        if (-not (Test-Path $VenvPython)) {
            Write-Host "[ERROR] venv python not found: $VenvPython" -ForegroundColor Red
            exit 1
        }

        # If already listening, report and exit OK
        $listenerPid = Get-ListenerPid -port $Port
        if ($listenerPid) {
            Set-Content -Path $PidFile -Value $listenerPid -Encoding ascii
            Write-Host "[OK] Uvicorn already listening on port $Port (PID: $listenerPid)" -ForegroundColor Green
            exit 0
        }

        # Start in a new PowerShell window so it keeps running.
        # IMPORTANT: use -File to run the venv python reliably.
        # Add CUDA path to child process for GPU acceleration
        # --timeout-keep-alive 600 for long-running optimization requests
        $startArgs = @(
            '-NoExit',
            '-Command',
            "`$env:PYTHONPATH = '$ProjectRoot'; `$env:PATH = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin;' + `$env:PATH; cd '$ProjectRoot'; & '$VenvPython' -m uvicorn $AppModule --host $BindHost --port $Port --workers $Workers --timeout-keep-alive 600 2>&1 | Tee-Object -FilePath '$LogFile'"
        )

        Start-Process -FilePath 'powershell.exe' -ArgumentList $startArgs -WindowStyle Normal -PassThru | Out-Null
        # Note: powershell.exe PID is not the python PID; we rely on port-listener PID.

        $listenerPid = Wait-For-Listen -port $Port -timeoutSeconds $StartupTimeoutSeconds
        if (-not $listenerPid) {
            Write-Host "[ERROR] Uvicorn did not start listening on port $Port within ${StartupTimeoutSeconds}s." -ForegroundColor Red
            Write-Host "        Check logs: $LogFile" -ForegroundColor Yellow
            exit 1
        }

        Set-Content -Path $PidFile -Value $listenerPid -Encoding ascii
        Write-Host "[OK] Uvicorn listening on port $Port (PID: $listenerPid)" -ForegroundColor Green
        Write-Host "[INFO] Logs: $LogFile" -ForegroundColor Gray
        exit 0
    }

    'stop' {
        Set-StateDir

        $uvicornPid = Get-UvicornPid
        if ($uvicornPid -and (Test-PidAlive $uvicornPid)) {
            Write-Host "[INFO] Stopping Uvicorn PID $uvicornPid..." -ForegroundColor Yellow
            try { Stop-Process -Id $uvicornPid -Force -ErrorAction Stop } catch {}
            Start-Sleep -Seconds 1
        }

        # Fallback: if something still listens on the port, kill that.
        $listenerPid = Get-ListenerPid -port $Port
        if ($listenerPid) {
            Write-Host "[INFO] Killing listener on port $Port (PID: $listenerPid)..." -ForegroundColor Yellow
            try { Stop-Process -Id $listenerPid -Force -ErrorAction Stop } catch {}
        }

        if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
        Write-Host "[OK] Uvicorn stopped" -ForegroundColor Green
        exit 0
    }

    'status' {
        $listenerPid = Get-ListenerPid -port $Port
        if ($listenerPid) {
            Write-Host "[OK] LISTENING :$Port (PID: $listenerPid)" -ForegroundColor Green
            exit 0
        }

        $uvicornPid = Get-UvicornPid
        if ($uvicornPid -and (Test-PidAlive $uvicornPid)) {
            Write-Host "[WARN] PID file exists ($uvicornPid) but port $Port is not listening" -ForegroundColor Yellow
            Write-Host "       Check logs: $LogFile" -ForegroundColor Yellow
            exit 1
        }

        Write-Host "[DOWN] Not listening on :$Port" -ForegroundColor Red
        exit 1
    }

    'tail' {
        Set-StateDir
        if (-not (Test-Path $LogFile)) {
            Write-Host "[INFO] Log file not found yet: $LogFile" -ForegroundColor Yellow
            exit 0
        }
        Get-Content -Path $LogFile -Wait
    }
}
