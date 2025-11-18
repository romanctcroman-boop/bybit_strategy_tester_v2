param(
    [string]$PrometheusUrl = "http://localhost:9090",
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$OutDir = "monitoring/snapshots"
)

# Ensure output directory exists
$fullOutDir = Resolve-Path -LiteralPath $OutDir -ErrorAction SilentlyContinue
if (-not $fullOutDir) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null; $fullOutDir = Resolve-Path $OutDir }

# Helper: query Prometheus instant vector
function Invoke-PromQuery {
    param([string]$query)
    try {
        $url = "$PrometheusUrl/api/v1/query?query=$([uri]::EscapeDataString($query))"
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop | ConvertFrom-Json
        return $resp.data.result
    }
    catch {
        Write-Warning "Prometheus query failed: $query => $($_.Exception.Message)"; return @()
    }
}

# Collect metrics
$now = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$day = Get-Date -Format "yyyy-MM-dd"
$snapshotPath = Join-Path $fullOutDir "phase1_daily_$day.json"

Write-Host "[STEP] Collecting backend health..." -ForegroundColor Yellow
$health = $null
try {
    $health = Invoke-WebRequest -Uri "$BackendUrl/api/v1/health" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop | ConvertFrom-Json
}
catch {
    Write-Warning "Health fetch failed: $($_.Exception.Message)"; $health = @{ status = 'unknown' }
}

Write-Host "[STEP] Querying Prometheus metrics..." -ForegroundColor Yellow
$metrics = @{}
$metrics.circuit_breaker_state = Invoke-PromQuery "circuit_breaker_state"
$metrics.circuit_breaker_open_24h = Invoke-PromQuery "increase(circuit_breaker_open_total[24h])"
$metrics.recovery_ratio_1h = Invoke-PromQuery "rate(agent_auto_recovery_success_total[1h]) / rate(circuit_breaker_open_total[1h])"
$metrics.latency_p95_5m = Invoke-PromQuery "histogram_quantile(0.95, rate(agent_request_latency_seconds_bucket[5m]))"
$metrics.autonomy_score = Invoke-PromQuery "autonomy_score_current"

# Compose snapshot
$snapshot = [ordered]@{
    timestamp  = $now
    backend    = $BackendUrl
    prometheus = $PrometheusUrl
    health     = $health
    metrics    = $metrics
}

# Write JSON snapshot
$snapshot | ConvertTo-Json -Depth 8 | Out-File -FilePath $snapshotPath -Encoding UTF8
Write-Host "[OK] Snapshot written: $snapshotPath" -ForegroundColor Green

# Also echo a short summary
$cb_opens = ($metrics.circuit_breaker_open_24h | Measure-Object).Count
$cb_states = ($metrics.circuit_breaker_state | Measure-Object).Count
Write-Host ("[SUMMARY] cb_states={0} cb_opens_series={1}" -f $cb_states, $cb_opens) -ForegroundColor Cyan
