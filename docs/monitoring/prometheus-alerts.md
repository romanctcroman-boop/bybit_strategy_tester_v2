# Prometheus Alerting Rules for MCP Production Hardening

This document contains deployment, validation, and runbook guidance for the Prometheus alert rules defined in `prometheus-alerts.yml`.

The YAML file now contains only the rules (no documentation blocks) to ensure schema-valid YAML and avoid IDE and Prometheus parser errors.

## 1. Prometheus Configuration

Add a scrape config to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "mcp-service"
    scrape_interval: 15s
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: "/metrics"
```

## 2. Load Rule Files

Copy the rules file to the Prometheus rules directory and reference it from `prometheus.yml`:

```bash
# Copy rules file
cp prometheus-alerts.yml /etc/prometheus/rules/

# In prometheus.yml
rule_files:
  - "/etc/prometheus/rules/prometheus-alerts.yml"
```

## 3. Reload Prometheus

```bash
# Validate Prometheus config
promtool check config prometheus.yml

# Reload via systemd (if applicable)
sudo systemctl reload prometheus

# Or via HTTP API
curl -X POST http://localhost:9090/-/reload
```

## 4. Verify Rules

- Open the Prometheus UI: <http://localhost:9090/rules>
- Confirm the MCP rule group is present and all rules are loaded without errors.

## 5. Alertmanager Example (Optional)

Route MCP alerts together and send them to a designated receiver (e.g., Slack):

```yaml
route:
  group_by: ["alertname", "component"]
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: "mcp-team"
  routes:
    - match:
        component: mcp
      receiver: "mcp-team"
      continue: true

receivers:
  - name: "mcp-team"
    slack_configs:
      - api_url: "YOUR_SLACK_WEBHOOK_URL"
        channel: "#mcp-alerts"
        title: "{{ .GroupLabels.alertname }}"
        text: "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"
```

## 6. Testing Alerts

Manually trigger or simulate conditions:

```bash
# Simulate high error rate (example endpoint)
for i in {1..100}; do
  curl -s -X POST http://localhost:8000/mcp/tools/call \
    -H "Content-Type: application/json" \
    -d '{"tool": "invalid_tool", "args": {}}' >/dev/null
done

# Verify health endpoint
curl -s http://localhost:8000/mcp/health
```

Check Prometheus UI → Status → Alerts to see if alerts are firing.

## 7. Grafana Dashboard Snippet (Optional)

```json
{
  "panels": [
    {
      "title": "MCP Active Alerts",
      "targets": [
        { "expr": "ALERTS{component=\\"mcp\\", alertstate=\\"firing\\"}" }
      ]
    }
  ]
}
```

## 8. Runbook URLs

Each rule in `prometheus-alerts.yml` references a `runbook_url`:

- MCPHighErrorRate → `MCP-Troubleshooting#high-error-rate`
- MCPHealthCheckFailing → `MCP-Troubleshooting#service-down`
- MCPLowTraffic → `MCP-Troubleshooting#low-traffic`
- MCPHighLatency → `MCP-Troubleshooting#high-latency`
- MCPHealthDegraded → `MCP-Troubleshooting#degraded-health`

Recommended sections for each runbook:

1. Symptom description
2. Potential root causes
3. Diagnostic steps (logs, metric queries)
4. Remediation actions
5. Escalation procedures

---

Created: 2025-11-16  
Author: GitHub Copilot + Agent Recommendations  
Version: 1.0
