param(
    [int]$Port,
    [string]$PgHost = '127.0.0.1',
    [string]$Db = 'postgres',
    [string]$User = 'postgres',
    [securestring]$Password,
    [pscredential]$Credential
)

# Resolve Port from env if not provided
if (-not $PSBoundParameters.ContainsKey('Port')) {
    if ($env:POSTGRES_PORT) { try { $Port = [int]$env:POSTGRES_PORT } catch {} }
    if (-not $Port) { $Port = 5543 }
}

# Resolve credentials (prefer PSCredential, then SecureString, then ENV, then default)
$plainPassword = $null
if ($Credential) {
    # Use provided PSCredential (overrides $User if different)
    if ($Credential.UserName) { $User = $Credential.UserName }
    $plainPassword = $Credential.GetNetworkCredential().Password
}
elseif ($Password) {
    try {
        $plainPassword = ([System.Net.NetworkCredential]::new("", $Password)).Password
    }
    catch {
        Write-Warning "Failed to convert SecureString password."
    }
}
elseif ($env:POSTGRES_PASSWORD) {
    $plainPassword = $env:POSTGRES_PASSWORD
}
if (-not $plainPassword) { $plainPassword = 'postgres' }

Write-Host ("Checking Postgres on {0}:{1} ..." -f $PgHost, $Port) -ForegroundColor Cyan

# Show listeners on the chosen port
$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    if ($pids) {
        $procs = Get-Process -Id $pids -ErrorAction SilentlyContinue | Select-Object Id, Name, Path
        Write-Host "Listening processes:" -ForegroundColor Yellow
        $procs | Format-Table | Out-String | Write-Host
    }
}
else {
    Write-Host "No listeners detected on port $Port" -ForegroundColor Red
}

# Find a Python to use
$pythonCandidates = @(
    (Join-Path $PSScriptRoot '..\\.py313-test\\Scripts\\python.exe'),
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Source })
)
$python = $pythonCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $python) {
    Write-Warning "Python not found. Install Python or create a venv to perform a live DB query."
    return
}

# Build Python one-liner to connect and fingerprint the server
$dsn = ("postgresql://{0}:{1}@{2}:{3}/{4}?connect_timeout=5" -f $User, $plainPassword, $PgHost, $Port, $Db)
$py = @'
import sys, os
try:
    import psycopg
except Exception as e:
    print("psycopg not installed:", e)
    sys.exit(2)

dsn = os.environ.get('DSN')
try:
    conn = psycopg.connect(dsn)
except Exception as e:
    print("connect failed:", e)
    sys.exit(3)

cur = conn.cursor()
cur.execute("select version(), current_user, current_database(), inet_server_addr(), inet_client_addr(), (select setting from pg_settings where name='data_directory')")
version, user, db, saddr, caddr, data_dir = cur.fetchone()
print("version:", version)
print("current_user:", user)
print("current_database:", db)
print("server_addr:", saddr)
print("client_addr:", caddr)
print("data_directory:", data_dir)

kind = 'unknown'
if data_dir and ('/var/lib/postgresql/data' in data_dir or 'Debian' in version):
    kind = 'docker'
elif data_dir and (('\\' in data_dir) or (':' in data_dir)):
    kind = 'windows'
print("detected:", kind)
conn.close()
'@

$env:DSN = $dsn
$tmpPy = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmpPy, $py, [System.Text.Encoding]::UTF8)
& $python $tmpPy
$exit = $LASTEXITCODE
Remove-Item -Force $tmpPy -ErrorAction SilentlyContinue
Remove-Item Env:DSN -ErrorAction SilentlyContinue

if ($exit -eq 0) {
    Write-Host "Success: connected and fingerprinted." -ForegroundColor Green
}
else {
    Write-Host ("Failure: code {0} (see messages above)." -f $exit) -ForegroundColor Red
}
