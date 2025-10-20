param(
    [int]$Port = 5433,
    [System.Management.Automation.PSCredential]$Credential = $null,
    [string]$Db = 'bybit'
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
docker compose -f "$composeFile" up -d postgres

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
for ($i = 0; $i -lt 60; $i++) {
    $checkUser = if ($Credential) { $Credential.UserName } else { $env:POSTGRES_USER -or 'postgres' }
    docker exec $cid pg_isready -U $checkUser > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Write-Error "Postgres did not become ready in time"; docker compose -f "$composeFile" logs --no-color; exit 1 }

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
Write-Output "Running alembic upgrade head against $maskedUrl"
.venv\Scripts\alembic.exe upgrade head
