# Grafana Integration Guide

**Версия:** 1.0  
**Дата:** 2026-03-03  
**Статус:** 🔄 Beta

---

## 📊 Overview

Grafana + Prometheus monitoring stack for Bybit Strategy Tester v2.

### Components:

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Visualization and dashboards
- **Node Exporter** - System metrics
- **Prometheus Exporter** - Application metrics

---

## 🚀 Quick Start

### 1. Start Monitoring Stack

```bash
cd deployment
docker-compose -f docker-compose-monitoring.yml up -d
```

### 2. Access Dashboards

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Node Exporter:** http://localhost:9100

### 3. Import Dashboard

Dashboard is auto-provisioned from:
```
deployment/grafana/dashboards/bybit-overview.json
```

---

## 📡 Metrics

### HTTP Metrics:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency histogram

### AI Agent Metrics:

- `ai_agent_requests_total` - AI agent requests
- `ai_agent_request_duration_seconds` - AI request latency
- `ai_agent_tokens_total` - Tokens consumed
- `cost_usd_total` - Cost in USD

### Cache Metrics:

- `cache_hits_total` - Cache hits
- `cache_misses_total` - Cache misses

### Backtest Metrics:

- `backtest_total` - Total backtests
- `backtest_failures_total` - Failed backtests
- `backtest_duration_seconds` - Backtest latency

### System Metrics:

- CPU usage
- Memory usage
- Disk usage
- Network I/O

---

## 🚨 Alerting Rules

Configured in `deployment/prometheus_rules.yml`:

- API High Error Rate
- API Slow Response
- Backtest Failure Rate
- AI Agent High Latency
- Cache Low Hit Rate
- Database Connection Pool Exhausted
- High Daily Cost
- High Memory/Disk/CPU Usage

---

## 📈 Usage in Application

### Record Metrics:

```python
from backend.monitoring.prometheus_exporter import get_metrics_collector

collector = get_metrics_collector()

# Record HTTP request
collector.record_http_request(200, 0.15, method="GET", endpoint="/api/test")

# Record AI request
collector.record_ai_request(
    agent="qwen",
    duration_seconds=2.5,
    success=True,
    tokens_used=1000,
    cost_usd=0.01,
)

# Record cache
collector.record_cache_hit()
collector.record_cache_miss()

# Record backtest
collector.record_backtest(success=True, duration_seconds=5.0)
```

### Expose Metrics Endpoint:

```python
from fastapi import Response
from backend.monitoring.prometheus_exporter import get_metrics_collector

@app.get("/health/metrics")
def metrics():
    collector = get_metrics_collector()
    return Response(
        content=collector.get_metrics(),
        media_type="text/plain"
    )
```

---

## 🔧 Configuration

### Prometheus Scrape Config:

Edit `deployment/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'bybit-api'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/health/metrics'
    scrape_interval: 30s
```

### Grafana Datasources:

Auto-provisioned from `deployment/grafana/provisioning/datasources/datasources.yml`.

---

## 🐛 Troubleshooting

### Problem: Prometheus can't scrape metrics

**Solution:**
```bash
# Check if metrics endpoint is accessible
curl http://localhost:8000/health/metrics

# Check Prometheus targets
# Open http://localhost:9090/targets
```

### Problem: Grafana dashboard not showing

**Solution:**
```bash
# Check provisioning
docker-compose -f docker-compose-monitoring.yml restart grafana

# Check logs
docker-compose -f docker-compose-monitoring.yml logs grafana
```

---

**Grafana integration ready for production!** 📊
