# 📊 Circuit Breaker V2 Monitoring Setup

**Production-Ready Monitoring for Circuit Breaker V2 with Prometheus Metrics**

**Version:** 2.0  
**Last Updated:** November 8, 2025  
**Status:** ✅ Production Ready

---

## 📁 Files in This Directory

```
monitoring/
├── grafana_dashboard_circuit_breaker.json  # Grafana dashboard (9 panels)
├── prometheus_alerting_rules.yml          # 11 alert rules (critical/warning/info)
├── README.md                              # This file (setup guide)
└── demo_prometheus_metrics.py             # Legacy demo (pre-V2)
```

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- ✅ Prometheus server running
- ✅ Grafana server running  
- ✅ Circuit Breaker V2 with prometheus_client installed
- ✅ Backend exposing `/metrics` endpoint

### Step 1: Verify Metrics Export

```bash
# Check backend metrics endpoint
curl http://localhost:8000/metrics | grep circuit_breaker

# Expected output:
# circuit_breaker_state{key_id="...",provider="deepseek"} 0
# circuit_breaker_trips_total{key_id="...",provider="deepseek"} 0
# circuit_breaker_failure_count{key_id="...",provider="deepseek"} 0
```

### 2. Start Grafana + Prometheus

```bash
# Navigate to monitoring directory
cd monitoring

# Start containers (detached mode)
docker-compose up -d

# Check logs
docker-compose logs -f
```

**Expected output**:
```
✅ prometheus is up and running on port 9090
✅ grafana is up and running on port 3000
✅ alertmanager is up and running on port 9093
```

### 3. Access Grafana

Open your browser and go to:
- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `admin`

On first login, you'll be prompted to change the password (optional for development).

### 4. View Dashboards

Click on **Dashboards** → **Browse** → **Automation Platform** folder

You'll see 4 dashboards:
1. **System Health** - CPU, Memory, Disk metrics
2. **TestWatcher Performance** - File processing, test runs
3. **AuditAgent Metrics** - Coverage, audit runs
4. **API Metrics** - DeepSeek/Perplexity calls

---

## 📊 Available Dashboards

### 1. System Health Dashboard
**URL**: http://localhost:3000/d/system-health

**Panels**:
- CPU Usage (gauge)
- Memory Usage (gauge)
- Process Memory Usage (timeseries)
- Process Threads (timeseries)
- CPU Usage Rate (timeseries)

**Use Case**: Monitor overall system resource usage

---

### 2. TestWatcher Performance Dashboard
**URL**: http://localhost:3000/d/test-watcher-performance

**Panels**:
- Files Processed (stat)
- TestWatcher Status (stat - Running/Stopped)
- Files in Queue (stat)
- Error Rate (stat)
- Test Runs by Status (timeseries)
- Test Execution Duration Percentiles (p50, p95, p99)
- API Calls (timeseries)
- Memory Usage (timeseries)

**Use Case**: Monitor file processing and test execution performance

---

### 3. AuditAgent Metrics Dashboard
**URL**: http://localhost:3000/d/audit-agent-metrics

**Panels**:
- Total Audit Runs (stat)
- Test Coverage (gauge)
- Completion Markers Found (stat)
- Audit Runs by Trigger (timeseries)
- Coverage Trend (timeseries)
- Audit Run Duration Percentiles (timeseries)
- Error Rate by Type (timeseries)

**Use Case**: Track test coverage and audit performance

---

### 4. API Metrics Dashboard
**URL**: http://localhost:3000/d/api-metrics

**Panels**:
- DeepSeek API Calls (timeseries)
- Perplexity API Calls (timeseries)
- API Response Time (percentiles)
- Rate Limit Hits (stat)
- API Errors (timeseries)

**Use Case**: Monitor external API usage and health

---

## 🔧 Configuration

### Prometheus Configuration

**File**: `monitoring/prometheus/prometheus.yml`

**Key Settings**:
```yaml
scrape_interval: 15s          # Scrape metrics every 15s
scrape_configs:
  - job_name: 'bybit-strategy-tester'
    scrape_interval: 10s
    static_configs:
      - targets: ['host.docker.internal:9090']  # Your metrics endpoint
```

**Note**: On Windows/Mac, use `host.docker.internal`. On Linux, use your host IP (e.g., `172.17.0.1`).

---

### Grafana Configuration

**Datasource**: `monitoring/grafana/provisioning/datasources/prometheus.yml`

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

**Dashboards**: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

```yaml
providers:
  - name: 'Bybit Strategy Tester'
    folder: 'Automation Platform'
    options:
      path: /var/lib/grafana/dashboards
```

---

## 🛠️ Troubleshooting

### Problem: Grafana shows "No data"

**Solution 1**: Check metrics are being exported
```bash
# Test metrics endpoint
curl http://localhost:9090/metrics
```

Expected: You should see metrics like:
```
test_watcher_files_processed_total 5.0
test_watcher_is_running 1.0
system_cpu_percent 12.5
```

**Solution 2**: Check Prometheus is scraping
- Go to http://localhost:9090/targets
- Verify target `bybit-strategy-tester` is **UP**

**Solution 3**: Check Docker networking
```bash
# For Linux hosts, update prometheus.yml to use your host IP
# Find your IP:
ip addr show docker0
# Update targets to: ['172.17.0.1:9090']
```

---

### Problem: Cannot access Grafana at localhost:3000

**Solution**: Check if containers are running
```bash
docker-compose ps

# Expected output:
# bybit-grafana     running   0.0.0.0:3000->3000/tcp
# bybit-prometheus  running   0.0.0.0:9090->9090/tcp
```

If not running:
```bash
docker-compose up -d
docker-compose logs grafana
```

---

### Problem: Port 9090 already in use

**Solution 1**: Stop conflicting service
```bash
# Windows
netstat -ano | findstr :9090
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :9090
kill -9 <PID>
```

**Solution 2**: Change port in docker-compose.yml
```yaml
prometheus:
  ports:
    - "9091:9090"  # Changed to 9091
```

Then update Prometheus datasource URL in Grafana.

---

## 📈 Using the Dashboards

### Monitor Real-Time Performance

1. **Set Auto-Refresh**: Top-right corner → Select "10s"
2. **Time Range**: Top-right corner → Select "Last 15 minutes"
3. **Zoom In**: Click and drag on any graph to zoom

### Create Alerts (Coming in Phase 3)

For now, you can:
- **Visual Alerts**: Set threshold markers on gauge panels
- **Email**: Configure alert rules in Prometheus (Phase 3)

---

## 🔄 Updating Dashboards

### Export Dashboard
1. Open dashboard in Grafana
2. Click **Share** → **Export** → **Save to file**
3. Save to `monitoring/grafana/dashboards/<name>.json`

### Import Dashboard
1. Copy JSON file to `monitoring/grafana/dashboards/`
2. Restart Grafana: `docker-compose restart grafana`
3. Dashboard auto-loads from provisioning

---

## 🚨 Alert Rules (Phase 3)

### Alert System Overview

The monitoring stack includes AlertManager for automated alerting with 4 severity levels:

**Severity Levels**:
- 🔴 **Critical**: Immediate action required (5 min response time)
- 🟡 **Warning**: Action needed soon (30 min response time)
- 🔵 **Info**: Informational only (next business day)

### Alert Categories

#### TestWatcher Alerts
- **TestWatcherDown** (Critical): Service not running
- **TestWatcherHighErrorRate** (Critical): >10% error rate
- **TestWatcherQueueBacklog** (Warning): >10 files stuck
- **TestWatcherSlowTests** (Warning): p95 > 2 minutes

#### AuditAgent Alerts
- **TestCoverageDrop** (Critical): Coverage < 70% and dropped 5%
- **TestCoverageLow** (Warning): Coverage < 80%
- **AuditAgentHighErrors** (Warning): High error rate
- **AuditAgentSlowRuns** (Warning): p95 > 10 minutes

#### API Alerts
- **DeepSeekAPIDown** (Critical): All calls failing
- **PerplexityAPIDown** (Critical): All calls failing
- **APIRateLimitExceeded** (Critical): Frequent rate limit hits
- **APIHighErrorRate** (Warning): >10% error rate
- **APISlowResponses** (Warning): p95 > 10 seconds

#### System Alerts
- **HighCPUUsage** (Critical): CPU > 90%
- **HighMemoryUsage** (Critical): Memory > 90%
- **MemoryLeakDetected** (Critical): Growing >10MB/10min, >1GB total
- **HighDiskUsage** (Warning): Disk > 85%
- **ElevatedCPUUsage** (Warning): CPU > 70%

### Access AlertManager

**URL**: http://localhost:9093

**Features**:
- View active alerts
- Silence alerts during maintenance
- View alert history
- Configure notification routing

### Configure Slack Notifications

1. **Create Slack Webhook**:
   - Go to https://api.slack.com/messaging/webhooks
   - Create webhook for your workspace
   - Copy webhook URL

2. **Update AlertManager config**:
   ```bash
   # Edit monitoring/alertmanager/config.yml
   # Replace 'YOUR/WEBHOOK/URL' with your webhook
   ```

3. **Create Slack channels**:
   - `#alerts-critical` - Critical alerts
   - `#alerts-warning` - Warning alerts
   - `#alerts-info` - Info alerts

4. **Restart AlertManager**:
   ```bash
   docker-compose restart alertmanager
   ```

### Test Alerts

Run the alert testing script:

```bash
# Interactive test menu
python monitoring/test_alerts.py
```

**Available Tests**:
1. Check system status
2. Test CRITICAL alerts (TestWatcherDown, High CPU, etc.)
3. Test WARNING alerts (Elevated resources, API errors)
4. Reset all to normal

### Alert Runbooks

See `monitoring/ALERT_RUNBOOK.md` for:
- Detailed diagnosis procedures
- Step-by-step resolution guides
- Escalation paths
- Contact information

**Quick Example**:
```bash
# Diagnose TestWatcherDown alert
Get-Process python | Where-Object {$_.CommandLine -like "*test_watcher*"}

# Check logs
Get-Content backend\logs\test_watcher.log -Tail 50

# Verify metrics
curl http://localhost:9090/api/v1/query?query=test_watcher_is_running
```

### Alert Rule Files

Alert rules are located in `monitoring/prometheus/alerts/`:
- `test_watcher.yml` - TestWatcher monitoring (7 rules)
- `audit_agent.yml` - AuditAgent monitoring (7 rules)
- `api.yml` - API health monitoring (8 rules)
- `system.yml` - System resources (8 rules)

**Total**: 30 alert rules across all components

---

## 🧹 Cleanup

### Stop Services
```bash
cd monitoring
docker-compose down
```

### Remove Data (full cleanup)
```bash
docker-compose down -v  # Removes volumes
```

---

## 📚 Advanced Usage

### Add Custom Panel

1. Open any dashboard
2. Click **Add panel** → **Add a new panel**
3. Configure query:
   ```promql
   # Example: API success rate
   sum(rate(deepseek_api_calls_total{status="success"}[5m]))
   / 
   sum(rate(deepseek_api_calls_total[5m]))
   * 100
   ```
4. Save dashboard

### Query Examples

**Test success rate**:
```promql
sum(test_watcher_tests_run_total{status="pass"})
/
sum(test_watcher_tests_run_total)
* 100
```

**Memory growth rate**:
```promql
rate(test_watcher_memory_usage_bytes[5m])
```

**API errors per minute**:
```promql
rate(api_errors_total[1m]) * 60
```

---

## 🎯 Next Steps

**Phase 3**: Alert Rules ✅ **COMPLETE**
- ✅ AlertManager configured and running
- ✅ 30 alert rules across 4 categories
- ✅ Slack notification integration ready
- ✅ Runbook documentation created
- ✅ Alert testing script provided

**Phase 4**: Health Checks (Next)
- Add `/health` and `/ready` endpoints
- Kubernetes liveness/readiness probes
- Automated recovery procedures

---

## 📞 Support

**Phase 2 Documentation**: See `WEEK4_PHASE2_GRAFANA_COMPLETE.md`  
**Phase 3 Documentation**: See `WEEK4_PHASE3_ALERTS_COMPLETE.md`  
**Alert Runbooks**: See `monitoring/ALERT_RUNBOOK.md`  
**Demo**: Run `python demo_prometheus_metrics.py`  

**Web UIs**:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000  
- AlertManager: http://localhost:9093

---

**Last Updated**: 2025-01-07  
**Version**: 2.0  
**Status**: Phase 3 Complete ✅
