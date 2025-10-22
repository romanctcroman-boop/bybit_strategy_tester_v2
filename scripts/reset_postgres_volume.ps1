param(
    [int]$Port = 5543,
    [string]$Db = 'bybit',
    [string]$User = 'postgres',
    [SecureString]$Password
)

$ErrorActionPreference = 'Continue'

# Prefer POSTGRES_PORT from environment if not explicitly passed
if (-not $PSBoundParameters.ContainsKey('Port') -and $env:POSTGRES_PORT) {
    try { $Port = [int]$env:POSTGRES_PORT } catch {}
}

# Resolve paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$root = Resolve-Path (Join-Path $scriptDir '..')
$composeFile = Join-Path $scriptDir '..\docker-compose.postgres.yml'
if (-not (Test-Path $composeFile)) { throw "docker-compose file not found: $composeFile" }

# Prepare password
if (-not $Password) {
    $pwdSource = $env:POSTGRES_PASSWORD
    if (-not $pwdSource) { $pwdSource = 'postgres' }
    $Password = ConvertTo-SecureString -String $pwdSource -AsPlainText -Force
}
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
try {
    $pwdPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

Write-Host "[1] Stopping and removing containers + volumes..." -ForegroundColor Yellow
Push-Location $root
try {
    docker compose -f "$composeFile" down -v 2>$null | Out-Null
}
catch {
    # ignore errors when nothing to remove
}
finally {
    Pop-Location
}

Write-Host "[2] Starting postgres service..." -ForegroundColor Yellow
Push-Location $root
try {
    $env:POSTGRES_PORT = "$Port"
    docker compose -f "$composeFile" up -d postgres | Out-Null
}
finally {
    Pop-Location
}

# Get container id
$cid = $null
for ($i = 0; $i -lt 60; $i++) {
    try {
        $out = docker compose -f "$composeFile" ps -q postgres 2>&1
        $cid = ($out | Where-Object { $_ -match '^[0-9a-f]{12,}$' } | Select-Object -First 1)
    }
    catch {
        $cid = $null
    }
    if ($cid) { break }
    Start-Sleep -Seconds 1
}
if (-not $cid) { throw "Failed to obtain postgres container id" }

Write-Host "[3] Waiting for Postgres readiness..." -ForegroundColor Yellow
for ($i = 0; $i -lt 60; $i++) {
    $ready = 0
    try {
        docker exec $cid pg_isready -U $User | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = 1 }
    }
    catch {}
    if ($ready -eq 1) { break }
    Start-Sleep -Seconds 2
}
if ($ready -ne 1) { throw "Postgres readiness check failed" }

# Ensure password inside container (fresh init should already apply env vars, but enforce just in case)
try {
    docker exec -u postgres $cid psql -U $User -d postgres -v ON_ERROR_STOP=1 -c "ALTER USER $User WITH PASSWORD '$pwdPlain';" | Out-Null
}
catch {}

Write-Host "[4] Running Alembic migrations in ephemeral Python container (shares postgres network namespace)..." -ForegroundColor Yellow

# Compose the inner bash command to install deps and run alembic
$inner = @(
    'set -e',
    'python --version || true',
    'pip install -U pip >/dev/null',
    'pip install alembic sqlalchemy "psycopg[binary]" >/dev/null',
    ("export DATABASE_URL='postgresql://${User}:${pwdPlain}@localhost:5432/${Db}'"),
    'python -m alembic upgrade heads'
) -join ' && '

# Run a python container sharing the network namespace of postgres; mount repo at /app
$networkArg = "container:$cid"
$mountArg = "${root}:/app"
Write-Host "    > docker run --rm --network $networkArg -v $mountArg -w /app python:3.11 bash -lc '<command>'" -ForegroundColor DarkGray

docker run --rm --network $networkArg -v $mountArg -w /app python:3.11 bash -lc "$inner"
if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed with exit code $LASTEXITCODE" }

Write-Host "[5] Done. Fresh volume initialized and migrations applied." -ForegroundColor Green
