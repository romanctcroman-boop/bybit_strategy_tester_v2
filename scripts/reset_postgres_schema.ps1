param(
    [int]$Port = 5543,
    [string]$Db = 'bybit',
    [string]$User = 'postgres',
    [SecureString]$Password
)

# Prefer POSTGRES_PORT from environment if not explicitly passed
if (-not $PSBoundParameters.ContainsKey('Port') -and $env:POSTGRES_PORT) {
    try { $Port = [int]$env:POSTGRES_PORT } catch {}
}

# Resolve password securely; allow defaults via env or fallback
if (-not $Password) {
    $pwdSource = $env:POSTGRES_PASSWORD
    if (-not $pwdSource) { $pwdSource = 'postgres' }
    $Password = ConvertTo-SecureString -String $pwdSource -AsPlainText -Force
}

# Resolve docker-compose path
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$composeFile = Join-Path $scriptDir '..\docker-compose.postgres.yml'
if (-not (Test-Path $composeFile)) {
    Write-Error "docker-compose file not found at $composeFile"
    exit 1
}

# Ensure container is up
$env:POSTGRES_PORT = "$Port"
docker compose -f "$composeFile" up -d postgres | Out-Null

# Find container ID
$cid = $null
for ($i = 0; $i -lt 30; $i++) {
    $cid = docker compose -f "$composeFile" ps -q postgres 2>$null
    if ($cid) { break }
    Start-Sleep -Seconds 1
}
if (-not $cid) { Write-Error "Failed to start Postgres container"; exit 1 }

# Drop and recreate public schema
Write-Output "Resetting public schema in database '$Db' on port $Port..."

# Extract plaintext password just-in-time
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
try {
    $pwdPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

# Build SQL command string (inject $User safely using -f)
$sql = "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO {0}; GRANT ALL ON SCHEMA public TO public;" -f $User

# Execute psql inside the container with PGPASSWORD via docker exec env
docker exec --env "PGPASSWORD=$pwdPlain" $cid psql -U $User -d $Db -v ON_ERROR_STOP=1 -c "$sql"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to reset schema"; exit 1 }

# Run alembic upgrade head via venv
$root = Resolve-Path (Join-Path $scriptDir '..')
Push-Location $root
try {
    Write-Output "Running alembic upgrade heads..."
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    $alembicExe = Join-Path $root ".venv\Scripts\alembic.exe"
    if (Test-Path $alembicExe) {
        & $alembicExe upgrade heads
    }
    elseif (Test-Path $venvPython) {
        & $venvPython -m alembic upgrade heads
    }
    else {
        alembic upgrade heads
    }
    if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
Write-Output "Schema reset and migration completed."
