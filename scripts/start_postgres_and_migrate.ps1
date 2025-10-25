param(
    [int]$Port = 5433,
    [System.Management.Automation.PSCredential]$Credential = $null,
    [string]$Db = 'bybit',
    [ValidateSet('auto', 'host', 'container')]
    [string]$MigrationMode = 'container',
    [string]$MigratorImage = '',
    [string]$MigratorPython = '3.12-slim',
    [switch]$BuildMigrator
)

# Resolve paths relative to this script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$composeFile = Join-Path $scriptDir '..\docker-compose.postgres.yml'
if (-not (Test-Path $composeFile)) {
    Write-Error "docker-compose file not found at $composeFile"
    exit 1
}

Write-Output "Starting Postgres via docker-compose on port $Port (compose file: $composeFile)"
$env:POSTGRES_PORT = "$Port"
docker compose -f "$composeFile" up -d --remove-orphans postgres

# Wait for the postgres container id to appear
Write-Output "Waiting for Postgres container to appear..."
$cid = $null
for ($i = 0; $i -lt 30; $i++) {
    $cid = docker compose -f "$composeFile" ps -q postgres 2>$null
    if ($cid) { break }
    Start-Sleep -Seconds 1
}
if (-not $cid) { Write-Error "Failed to start Postgres container"; exit 1 }

Write-Output "Postgres container id: $cid"

# Wait for pg_isready inside the container
Write-Output "Waiting for Postgres to be ready (pg_isready)..."
$ready = $false
# Determine a safe username for readiness checks (do not use boolean -or; prefer explicit fallback)
$checkUser = if ([string]::IsNullOrEmpty($env:POSTGRES_USER)) { 'postgres' } else { $env:POSTGRES_USER }
for ($i = 0; $i -lt 60; $i++) {
    docker exec $cid pg_isready -U $checkUser > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Write-Error "Postgres did not become ready in time"; docker compose -f "$composeFile" logs --no-color; exit 1 }

# If we intend to use host migrations (host or auto), ensure host port is reachable
if ($MigrationMode -in @('host', 'auto')) {
    try {
        Write-Output "Verifying host port 127.0.0.1:$Port is open..."
        $hostReady = $false
        for ($i = 0; $i -lt 30; $i++) {
            $tnc = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
            if ($tnc -and $tnc.TcpTestSucceeded) { $hostReady = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $hostReady) { Write-Warning "Host port 127.0.0.1:$Port did not open in time; host-side migrations may fail on first try" }
    }
    catch {
        Write-Verbose "Test-NetConnection unavailable, skipping host port check"
    }
}

# Resolve credential: prefer explicit PSCredential, then environment variables, then a default dev credential
if (-not $Credential) {
    $envUser = $env:POSTGRES_USER
    $envPass = $env:POSTGRES_PASSWORD
    if ($envPass) {
        $userForCred = if ($envUser) { $envUser } else { 'postgres' }
        $secure = ConvertTo-SecureString $envPass -AsPlainText -Force
        $Credential = New-Object System.Management.Automation.PSCredential($userForCred, $secure)
    }
    else {
        # Non-interactive default for local dev. Use PSCredential type to satisfy PSScriptAnalyzer.
        $Credential = New-Object System.Management.Automation.PSCredential('postgres', (ConvertTo-SecureString 'postgres' -AsPlainText -Force))
    }
}

# Safely convert SecureString to plain-text only for composing DATABASE_URL; zero memory afterwards
$plainPassword = ''
$bstr = [System.IntPtr]::Zero
try {
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Credential.Password)
    $plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $env:DATABASE_URL = "postgresql://$($Credential.UserName):$plainPassword@127.0.0.1:$Port/$Db"
}
finally {
    if ($bstr -ne [System.IntPtr]::Zero) {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

# Avoid printing the plaintext password in logs; mask it when showing the URL
$maskedUrl = "postgresql://$($Credential.UserName):****@127.0.0.1:$Port/$Db"

# Strong readiness: attempt an actual psycopg connection using the venv Python
if ($MigrationMode -in @('host', 'auto')) {
    try {
        Write-Output "Probing database connectivity with psycopg (SELECT 1)..."
        $probeScript = @'
import os, time, sys
try:
    import psycopg
except Exception as e:
    print("psycopg import failed:", e)
    sys.exit(3)

url = os.environ.get("DATABASE_URL")
deadline = time.time() + 40.0
last_err = None
while time.time() < deadline:
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        sys.exit(0)
    except Exception as e:
        last_err = e
        time.sleep(1.0)
print("DB probe failed:", repr(last_err))
sys.exit(2)
'@
        $tmpProbe = Join-Path $scriptDir "db_probe.py"
        Set-Content -Path $tmpProbe -Value $probeScript -Encoding UTF8
        & .venv\Scripts\python.exe $tmpProbe 1> $null 2> $null
        $probeExit = $LASTEXITCODE
        Remove-Item -Path $tmpProbe -ErrorAction SilentlyContinue
        if ($probeExit -ne 0) {
            Write-Warning "Database probe did not succeed within timeout; host migration may still fail"
        }
    }
    catch {
        Write-Verbose "DB probe step skipped due to error: $($_.Exception.Message)"
    }
}
# Decide migration strategy
switch ($MigrationMode) {
    'host' {
        Write-Output "Running alembic (host mode) against $maskedUrl"
        $alembicLog = Join-Path $scriptDir '..\logs\alembic_host_upgrade.log'
        if (-not (Test-Path (Join-Path $scriptDir '..\logs'))) { New-Item -ItemType Directory -Path (Join-Path $scriptDir '..\logs') -Force | Out-Null }
        & .venv\Scripts\alembic.exe upgrade head 1> $alembicLog 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Host alembic failed with exit code $LASTEXITCODE (see $alembicLog)"
        }
    }
    'auto' {
        Write-Output "Running alembic (auto: host→container) against $maskedUrl"
        $alembicLog = Join-Path $scriptDir '..\logs\alembic_host_upgrade.log'
        if (-not (Test-Path (Join-Path $scriptDir '..\logs'))) { New-Item -ItemType Directory -Path (Join-Path $scriptDir '..\logs') -Force | Out-Null }
        $hostAlembicOk = $false
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                & .venv\Scripts\alembic.exe upgrade head 1> $alembicLog 2>&1
                if ($LASTEXITCODE -eq 0) { $hostAlembicOk = $true; break } else { throw "alembic exited with code $LASTEXITCODE (see $alembicLog)" }
            }
            catch {
                if ($attempt -lt 3) { Write-Warning ("Alembic upgrade via host attempt {0}/3 failed; retrying shortly..." -f $attempt); Start-Sleep -Seconds 2 } else { Write-Warning ("Alembic upgrade via host attempt {0}/3 failed" -f $attempt) }
            }
        }
        if (-not $hostAlembicOk) {
            try { Write-Warning ("Alembic upgrade via host failed: {0}" -f (Get-Content $alembicLog -ErrorAction SilentlyContinue | Select-Object -First 1)) } catch {}
            Write-Output "Falling back to containerized migration (no data loss) ..."
            $root = Resolve-Path (Join-Path $scriptDir '..')
            $dbUser = $Credential.UserName
            # Ensure migrator image is available
            $image = $MigratorImage
            if (-not $image -or $BuildMigrator) {
                $image = "bybit-migrator:${MigratorPython}"
                $rootPath = Resolve-Path (Join-Path $scriptDir '..')
                if ($BuildMigrator) { Write-Output ("Building migrator image {0} (forced) ..." -f $image) }
                $needBuild = $BuildMigrator
                if (-not $needBuild) {
                    docker image inspect $image *> $null
                    if ($LASTEXITCODE -ne 0) { $needBuild = $true }
                }
                if ($needBuild) {
                    docker build -f (Join-Path $scriptDir 'migrator.Dockerfile') --build-arg ("PYTHON_IMAGE=python:{0}" -f $MigratorPython) -t $image $rootPath
                    if ($LASTEXITCODE -ne 0) { throw "Failed to build migrator image $image" }
                }
            }
            $envVar = "postgresql://${dbUser}:${plainPassword}@localhost:5432/${Db}"
            docker run --rm --network "container:${cid}" -e ("DATABASE_URL={0}" -f $envVar) -v "${root}:/app" -w /app $image python -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) { throw "Containerized alembic upgrade failed with exit code $LASTEXITCODE" }
        }
    }
    'container' {
        Write-Output "Running alembic (container mode) against service-local DB"
        $root = Resolve-Path (Join-Path $scriptDir '..')
        $dbUser = $Credential.UserName
        # Ensure migrator image is available
        $image = $MigratorImage
        if (-not $image -or $BuildMigrator) {
            $image = "bybit-migrator:${MigratorPython}"
            $rootPath = Resolve-Path (Join-Path $scriptDir '..')
            if ($BuildMigrator) { Write-Output ("Building migrator image {0} (forced) ..." -f $image) }
            $needBuild = $BuildMigrator
            if (-not $needBuild) {
                docker image inspect $image *> $null
                if ($LASTEXITCODE -ne 0) { $needBuild = $true }
            }
            if ($needBuild) {
                docker build -f (Join-Path $scriptDir 'migrator.Dockerfile') --build-arg ("PYTHON_IMAGE=python:{0}" -f $MigratorPython) -t $image $rootPath
                if ($LASTEXITCODE -ne 0) { throw "Failed to build migrator image $image" }
            }
        }
        $envVar = "postgresql://${dbUser}:${plainPassword}@localhost:5432/${Db}"
        docker run --rm --network "container:${cid}" -e ("DATABASE_URL={0}" -f $envVar) -v "${root}:/app" -w /app $image python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Containerized alembic upgrade failed with exit code $LASTEXITCODE" }
    }
}
