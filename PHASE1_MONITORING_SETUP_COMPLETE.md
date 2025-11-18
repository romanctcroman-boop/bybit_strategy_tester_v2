# Phase 1 Monitoring Setup - Deployment Guide

**Date**: 2025-11-18  
**Status**: ✅ Configuration Complete  
**Next Step**: Launch Monitoring Stack  

---

## ✅ Completed Configuration

### 1. Prometheus Scrape Target Added

**File**: `monitoring/prometheus/prometheus.yml`

**New job configuration**:
```yaml
# Phase 1 Backend (Circuit Breaker Monitoring)
- job_name: 'phase1-backend'
  scrape_interval: 15s
  scrape_timeout: 10s
  metrics_path: '/metrics'
  static_configs:
    - targets: ['host.docker.internal:8000']
      labels:
        service: 'phase1-backend'
        component: 'unified-agent-interface'
        environment: 'staging'
        phase: 'phase1'
```

**Target**: `http://127.0.0.1:8000/metrics` (FastAPI backend)

**Metrics exposed**:

- `circuit_breaker_state{provider="deepseek|perplexity|mcp_server"}`
- `circuit_breaker_open_total{service="deepseek_api|perplexity_api|mcp_server"}`
- `agent_request_latency_seconds{quantile="0.95"}`
- `agent_auto_recovery_success_total`
- `autonomy_score_current`
- MCP tasks metrics (if MCP available)
- Cache metrics (via `/metrics/cache`)

### 2. Grafana Dashboard Imported

**Source**: `monitoring/grafana_dashboard_circuit_breaker.json`  
**Destination**: `monitoring/grafana/dashboards/phase1_circuit_breaker.json`  
**Status**: ✅ Copied to Grafana provisioning directory

**Dashboard features**:

- Circuit Breaker States by Key
- API Request Latency (P50, P95, P99)
- Error Rate by Provider
- Total API Calls
- Circuit Breaker Open Count
- Auto-recovery success rate
- Autonomy score timeline

**Auto-provisioning**: Grafana will load dashboard automatically on startup via:

- Provisioning config: `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- Dashboard directory: `/var/lib/grafana/dashboards` (mounted volume)

---

## 🚀 Launch Monitoring Stack

### Prerequisites Check

```powershell
# 1. Backend running on port 8000
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing

# Expected: {"status":"healthy",...}

# 2. Docker Desktop running
docker --version

# Expected: Docker version 20.x or higher

# 3. No port conflicts (9090, 3000, 9093)
netstat -ano | findstr ":9090 :3000 :9093"

# Expected: Empty (no existing services on these ports)
```

### Step 1: Start Monitoring Stack

```powershell
# Navigate to monitoring directory
cd monitoring

# Start Prometheus + Grafana + Alertmanager
docker-compose up -d

# Expected output:
# Creating network "monitoring_monitoring" with driver "bridge"
# Creating bybit-prometheus ... done
# Creating bybit-grafana    ... done
# Creating bybit-alertmanager ... done
```

### Step 2: Verify Services

```powershell
# Check container status
docker-compose ps

# Expected output:
# NAME                   STATUS              PORTS
# bybit-prometheus       Up 10 seconds       0.0.0.0:9090->9090/tcp
# bybit-grafana          Up 10 seconds       0.0.0.0:3000->3000/tcp
# bybit-alertmanager     Up 10 seconds       0.0.0.0:9093->9093/tcp

# Wait 10 seconds for services to initialize
Start-Sleep -Seconds 10
```

### Step 3: Verify Prometheus Scraping

```powershell
# Open Prometheus UI
Start-Process "http://localhost:9090"

# Navigate to: Status → Targets
# Verify:
# - prometheus: UP (self-monitoring)
# - phase1-backend: UP (if backend running on 8000)

# Alternative: Check via PowerShell
$targets = Invoke-WebRequest -Uri "http://localhost:9090/api/v1/targets" -UseBasicParsing | ConvertFrom-Json
$phase1_target = $targets.data.activeTargets | Where-Object {$_.job -eq "phase1-backend"}
Write-Host "Phase 1 Backend Target: $($phase1_target.health)" -ForegroundColor $(if($phase1_target.health -eq "up"){"Green"}else{"Red"})

# Expected: "Phase 1 Backend Target: up"
```

### Step 4: Verify Metrics Collection

```powershell
# Query Prometheus for Phase 1 metrics
$query = "circuit_breaker_state"
$response = Invoke-WebRequest -Uri "http://localhost:9090/api/v1/query?query=$query" -UseBasicParsing | ConvertFrom-Json

if ($response.data.result.Count -gt 0) {
    Write-Host "[OK] Circuit breaker metrics available" -ForegroundColor Green
    $response.data.result | ForEach-Object {
        Write-Host "  - $($_.metric.service): $($_.value[1])" -ForegroundColor Cyan
    }
} else {
    Write-Host "[WARN] No circuit breaker metrics yet (backend may need to expose metrics)" -ForegroundColor Yellow
}
```

### Step 5: Access Grafana Dashboard

```powershell
# Open Grafana UI
Start-Process "http://localhost:3000"

# Login credentials:
# Username: admin
# Password: admin
# (Change on first login if prompted)

# Navigate to: Dashboards → Automation Platform → phase1_circuit_breaker

# Expected panels:
# 1. Circuit Breaker States by Key
# 2. API Request Latency
# 3. Error Rate by Provider
# 4. Total API Calls
# 5. Circuit Breaker Open Count
```

---

## 🔍 Troubleshooting

### Problem: "phase1-backend target DOWN"

**Cause**: Backend not exposing metrics or port mismatch

**Solution**:
```powershell
# 1. Check backend health
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing

# 2. Check metrics endpoint
Invoke-WebRequest -Uri "http://127.0.0.1:8000/metrics" -UseBasicParsing

# Expected: Prometheus text format output

# 3. If 404, check backend routes
.\.venv\Scripts\python.exe -c "from backend.api.app import app; print([r.path for r in app.routes])" | Select-String "metrics"

# 4. If backend not running, start it
.\.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

### Problem: "Dashboard not visible in Grafana"

**Cause**: Provisioning delay or volume mount issue

**Solution**:
```powershell
# 1. Check Grafana logs
docker logs bybit-grafana | Select-Object -Last 30

# Look for: "Provisioned dashboard" messages

# 2. Manually verify dashboard file
docker exec bybit-grafana ls -l /var/lib/grafana/dashboards/

# Expected: phase1_circuit_breaker.json present

# 3. Force reload dashboards
docker restart bybit-grafana

# 4. Manually import if needed:
# Grafana UI → Dashboards → Import → Upload monitoring/grafana_dashboard_circuit_breaker.json
```

### Problem: "No data in Grafana panels"

**Cause**: Prometheus not scraping or metrics not generated yet

**Solution**:
```powershell
# 1. Verify Prometheus has data
# Open http://localhost:9090/graph
# Query: circuit_breaker_state
# Expected: Time series with values

# 2. Trigger agent request to generate metrics
.\.venv\Scripts\python.exe -c @"
import asyncio
from backend.agents.unified_agent_interface import get_agent_interface
async def test():
    agent = get_agent_interface()
    stats = agent.get_stats()
    print(f'Autonomy score: {stats[\"autonomy_score\"]}')
asyncio.run(test())
"@

# 3. Wait 15 seconds for Prometheus scrape
Start-Sleep -Seconds 15

# 4. Refresh Grafana dashboard
```

### Problem: "Docker Desktop not running"

**Solution**:
```powershell
# 1. Start Docker Desktop manually
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# 2. Wait for startup (30-60 seconds)
Start-Sleep -Seconds 60

# 3. Verify Docker is running
docker info

# Expected: Server info displayed

# 4. Retry monitoring stack startup
cd monitoring; docker-compose up -d
```

---

## 📊 Monitoring Verification Checklist

After launching monitoring stack, verify:

- [ ] **Prometheus UI accessible**: http://localhost:9090
- [ ] **Prometheus targets**:
  - [ ] `prometheus` target: UP
  - [ ] `phase1-backend` target: UP (or warning if backend offline)
- [ ] **Grafana UI accessible**: http://localhost:3000
- [ ] **Grafana datasource**: Prometheus connected (Settings → Data Sources)
- [ ] **Grafana dashboard**: `phase1_circuit_breaker` visible in dashboards list
- [ ] **Dashboard panels**: All 5+ panels rendering (may show "No data" if backend just started)
- [ ] **Alertmanager UI**: http://localhost:9093 (optional, for alert routing)

---

## 📈 Day 1 Monitoring Tasks

Once monitoring stack is running:

### 1. Capture Baseline Metrics

```powershell
# Create monitoring session log
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$logFile = "monitoring\phase1_session_$timestamp.log"

# Record initial state
@"
=== Phase 1 Monitoring Session Start ===
Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Backend: http://127.0.0.1:8000
Prometheus: http://localhost:9090
Grafana: http://localhost:3000

Initial Metrics:
"@ | Out-File $logFile -Encoding UTF8

# Get stats
.\.venv\Scripts\python.exe verify_phase1_direct.py 2>&1 | Out-File $logFile -Append -Encoding UTF8
```

### 2. Fill Daily Summary Template

```powershell
# Copy template for this week
$startDate = Get-Date -Format "yyyy-MM-dd"
$endDate = (Get-Date).AddDays(7).ToString("yyyy-MM-dd")
Copy-Item monitoring\daily_phase1_summary.md "monitoring\phase1_summary_${startDate}_to_${endDate}.md"

# Open in editor
code "monitoring\phase1_summary_${startDate}_to_${endDate}.md"

# Fill Day 1 section with:
# - Backend health snapshot
# - Circuit breaker states (all CLOSED expected)
# - Autonomy score (3.0 baseline expected)
# - No trips/recoveries yet (day 0 baseline)
```

### 3. Schedule Prometheus Queries

Key queries to run daily at 18:00 UTC:

```promql
# 1. Circuit breaker trips (last 24h)
increase(circuit_breaker_open_total[24h])

# 2. Recovery success rate (last 1h)
rate(agent_auto_recovery_success_total[1h]) / rate(circuit_breaker_open_total[1h])

# 3. Latency P95 (last 5m)
histogram_quantile(0.95, rate(agent_request_latency_seconds_bucket[5m]))

# 4. Autonomy score current
autonomy_score_current

# 5. Total API calls by provider
sum(rate(agent_request_total[1h])) by (provider)
```

### 4. Configure Alerts (Optional)

Edit `monitoring/prometheus/alerts/phase1_alerts.yml`:

```yaml
groups:
  - name: phase1_circuit_breaker
    interval: 1m
    rules:
      - alert: CircuitBreakerFlood
        expr: increase(circuit_breaker_open_total[10m]) > 8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker opening frequently"
          
      - alert: RecoveryDrop
        expr: rate(agent_auto_recovery_success_total[1h]) / rate(circuit_breaker_open_total[1h]) < 0.70
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Recovery rate below 70%"
```

Then reload Prometheus:

```powershell
# Reload Prometheus config (without restart)
Invoke-WebRequest -Uri "http://localhost:9090/-/reload" -Method POST
```

---

## 🎯 Success Criteria

After 24 hours of monitoring, you should observe:

- ✅ Prometheus scraping Phase 1 backend every 15 seconds
- ✅ Grafana dashboard updating in real-time (10s refresh)
- ✅ Circuit breakers: All CLOSED (no failures yet)
- ✅ Autonomy score: 3.0 (baseline, will increase with recoveries)
- ✅ No data gaps in Prometheus (continuous scraping)
- ✅ Grafana panels showing time series (even if flat lines initially)

---

## 📝 Quick Commands Reference

```powershell
# Start monitoring stack
cd monitoring; docker-compose up -d

# Stop monitoring stack
cd monitoring; docker-compose down

# View logs
docker logs bybit-prometheus -f   # Prometheus logs
docker logs bybit-grafana -f      # Grafana logs
docker logs bybit-alertmanager -f # Alertmanager logs

# Restart specific service
docker restart bybit-prometheus
docker restart bybit-grafana

# Check Prometheus targets
Invoke-WebRequest -Uri "http://localhost:9090/api/v1/targets" -UseBasicParsing | ConvertFrom-Json

# Query Prometheus metrics
Invoke-WebRequest -Uri "http://localhost:9090/api/v1/query?query=circuit_breaker_state" -UseBasicParsing | ConvertFrom-Json

# Test backend metrics endpoint
Invoke-WebRequest -Uri "http://127.0.0.1:8000/metrics" -UseBasicParsing | Select-Object -First 50

# Run verification script
.\.venv\Scripts\python.exe verify_phase1_direct.py

# Check monitoring stack status
cd monitoring; docker-compose ps
```

---

## ✅ Setup Complete!

**Monitoring stack configured**: ✅  
**Prometheus scrape target added**: ✅  
**Grafana dashboard imported**: ✅  

**Next action**: Run `cd monitoring; docker-compose up -d` to launch monitoring stack!

**Expected timeline**:

- **Now**: Launch monitoring stack (2 minutes)
- **+5 min**: Verify Prometheus scraping (15s intervals)
- **+10 min**: Verify Grafana dashboard loading
- **Day 1**: Capture baseline metrics
- **Day 2-7**: Daily monitoring per PHASE1_MONITORING_PLAN.md

---

**Ready? Execute:**

```powershell
cd monitoring
docker-compose up -d
Start-Sleep -Seconds 10
Start-Process "http://localhost:9090"  # Prometheus
Start-Process "http://localhost:3000"  # Grafana (admin/admin)
```

🚀 **Phase 1 Monitoring is GO!**
