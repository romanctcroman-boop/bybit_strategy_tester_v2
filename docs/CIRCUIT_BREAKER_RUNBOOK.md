# 📖 Circuit Breaker V2 Operational Runbook

**Production Deployment Guide & Troubleshooting**

**Version:** 2.0  
**Last Updated:** November 8, 2025  
**Status:** ✅ Production Ready  
**Maintained By:** RomanCTC

---

## 🎯 Quick Reference

| Alert | Severity | Response Time | Action |
|-------|----------|---------------|--------|
| `AllKeysCircuitBreakerOpen` | 🔴 CRITICAL | <5 min | [Jump to section](#alert-allkeyscircuitbreakeropen) |
| `MajorityKeysCircuitBreakerOpen` | 🔴 CRITICAL | <10 min | [Jump to section](#alert-majoritykeysc circuitbreakeropen) |
| `CircuitBreakerFlapping` | 🟡 WARNING | <30 min | [Jump to section](#alert-circuitbreakerflapping) |
| `CircuitBreakerStuckHalfOpen` | 🟡 WARNING | <30 min | [Jump to section](#alert-circuitbreakerstuckhalfopen) |

---

## � November 2025 Coverage Audit Snapshot

The circuit-breaker initiative now tracks every path that can reach DeepSeek, Perplexity, or MCP tooling without going through the unified agent interface. The table below shows the latest audit (Nov 19 2025 14:10 UTC):

| Surface | Current Protection | Notes / Next Action |
|---------|--------------------|---------------------|
| `backend/agents/unified_agent_interface.py` | ✅ Uses `AgentCircuitBreakerManager` on every HTTP hop (MCP + direct). | Baseline implementation; metrics already feeding Grafana. |
| `backend/api/perplexity_client.py` | ⚠️ Pending | Health-check helper still uses raw `httpx`. Needs manager + shared config and should reuse same breaker as production traffic. |
| `backend/api/deepseek_client.py` | ⚠️ Pending | Same issue as Perplexity client. Must register/consume breaker before calling `/models`. |
| `backend/mcp/mcp_integration.py` | ⚠️ Pending | Progressive timeouts exist, but repeated failures can still hammer MCP. Wrap `call_tool` with breaker + structured fallback. |
| `backend/agents/agent_background_service.py` | ⚠️ Partial | Health probes reuse unified interface but the direct MCP HTTP ping should respect breaker/open-state telemetry. |
| `backend/api/parallel_deepseek_client_v2.py` | ✅ Local breakers | Client ships with its own per-key breaker; verify alignment with manager before merging key metrics. |
| Celery + Redis workers | 🚧 Investigation | No direct HTTP usage discovered yet, but Celery orchestration will inherit breakers once the above modules are wired. |

📌 **Action Plan:**

1. Add breaker-aware wrappers to the standalone DeepSeek/Perplexity health clients so dashboards reflect outages even when only the health loop is running.
2. Inject `AgentCircuitBreakerManager` into the MCP bridge to prevent runaway retries when FastMCP tools degrade.
3. Teach the background service to consult breaker state before firing direct HTTP probes, emitting metrics when the breaker prevents a call.

This section should be updated after each hardening pass so operations can see, at a glance, where breakers are enforced versus still pending.

---

## �📊 Threshold Configuration Rationale

### Recommended Production Configuration

Based on load testing results (see `circuit_breaker_load_test_results.json`):

```python
CircuitBreaker(
    failure_threshold=5,      # Open circuit after 5 consecutive failures
    success_threshold=2,      # Close circuit after 2 consecutive successes
    timeout=60,               # Wait 60s before attempting recovery (HALF_OPEN)
    half_open_max_calls=3,    # Allow max 3 concurrent calls in HALF_OPEN state
    key_id="...",            # Unique identifier per API key
    provider="deepseek"      # Provider name for metrics
)
```

### Why These Values?

#### `failure_threshold=5` ✅
**Rationale:**
- **Too Low (3):** 18% false positive rate in mixed workload tests
- **Current (5):** <2% false positive rate, balanced detection
- **Too High (10):** Slower detection, 15s delay in persistent failure scenarios

**Load Test Results:**
- Transient failures: Trips in 0.8-1.2s (optimal)
- Mixed workload (95% success): 0 false positives over 5 minutes
- Persistent failures: Trips in 0.4-0.6s (excellent)

**Production Impact:**
- ~250ms at 50 requests/second before circuit opens
- Acceptable for API with occasional timeouts/errors

#### `success_threshold=2` ✅
**Rationale:**
- **Too Low (1):** Single successful request closes circuit (risky if API flaky)
- **Current (2):** Requires confirmation that API is stable
- **Too High (3):** Slower recovery (90s vs 60s), poor user experience

**Load Test Results:**
- Recovery time: 62-68s (near optimal 60s timeout)
- Flapping rate: 0.8 transitions/min (stable)
- Successful recovery rate: 98% (2 successes sufficient)

#### `timeout=60` ✅
**Rationale:**
- **Too Short (30s):** Frequent half-open attempts, higher load on failing API
- **Current (60s):** Balances recovery speed with API cooldown time
- **Too Long (120s):** Poor user experience, 2min wait for recovery

**Load Test Results:**
- Transient failures recovered in 62s (close to timeout)
- Persistent failures correctly stayed open for full timeout
- User-perceived downtime: acceptable for most use cases

#### `half_open_max_calls=3` ✅
**Rationale:**
- Limits concurrent load on recovering API
- If 3 calls succeed → API likely healthy
- If any fail → immediate return to OPEN (protective)

**Production Tuning:**
- High-traffic systems: Consider `half_open_max_calls=5`
- Low-traffic systems: `half_open_max_calls=2` sufficient

---

## 🚨 Alert Response Procedures

### Alert: AllKeysCircuitBreakerOpen
**Trigger:** All API keys have OPEN circuit breaker for 2+ minutes  
**Severity:** 🔴 CRITICAL  
**Response Time:** <5 minutes

#### Immediate Actions (First 5 Minutes)

1. **Check DeepSeek API Status**
   ```bash
   # Check official status page
   curl https://status.deepseek.com
   # OR visit https://platform.deepseek.com/status
   ```

2. **Review Recent Error Logs**
   ```bash
   # Check last 100 errors
   tail -n 100 /var/log/backend/error.log | grep "circuit_breaker"
   
   # Look for patterns:
   # - "429 Too Many Requests" = Rate limit
   # - "503 Service Unavailable" = API outage
   # - "Connection timeout" = Network issue
   ```

3. **Check Grafana Dashboard**
   - Navigate to: http://grafana:3000/d/circuit-breaker
   - Panel: "Circuit Breaker States by Key"
   - Look for: All keys = RED (state=2)

#### Root Cause Analysis (5-15 Minutes)

**Common Causes:**

| Cause | Identification | Resolution |
|-------|---------------|------------|
| **API Outage** | All keys failing simultaneously | Wait for API recovery, monitor status page |
| **Rate Limit** | 429 errors in logs | Wait for rate limit reset (usually 1 hour) |
| **Network Issue** | Connection timeouts | Check VPN/firewall/DNS |
| **Invalid API Keys** | 401/403 errors | Rotate/validate keys |
| **Bug in Code** | Unexpected errors | Rollback recent deployment |

#### Resolution Steps

**Option 1: Wait for Auto-Recovery (Recommended)**
- Circuit breakers automatically attempt recovery every 60s
- Monitor Grafana for state transitions: OPEN → HALF_OPEN → CLOSED
- Expected recovery time: 60-120s if API healthy

**Option 2: Manual Circuit Breaker Reset (Use with Caution)**
```bash
# Reset ALL circuit breakers
curl -X POST http://localhost:8000/api/v1/circuit-breaker/reset

# Reset specific key
curl -X POST http://localhost:8000/api/v1/circuit-breaker/<KEY_ID>/reset
```

**⚠️ Warning:** Only use manual reset if you've confirmed:
1. API is healthy (tested with curl)
2. Root cause has been fixed
3. No ongoing API outage

**Option 3: Rotate to Backup API Keys**
```bash
# If primary keys exhausted, activate backup keys
curl -X POST http://localhost:8000/api/v1/keys/rotate \
  -H "Content-Type: application/json" \
  -d '{"provider": "deepseek", "activate_backup": true}'
```

#### Post-Incident Actions

1. **Document Incident**
   - Time of occurrence
   - Root cause
   - Resolution method
   - Duration of outage

2. **Review Metrics**
   ```bash
   # Check total downtime
   curl -s 'http://prometheus:9090/api/v1/query?query=sum(circuit_breaker_state_duration_seconds{state="open"}[1h])' | jq .
   
   # Check request success rate during incident
   curl -s 'http://prometheus:9090/api/v1/query?query=rate(successful_requests[1h])' | jq .
   ```

3. **Adjust Thresholds (If Needed)**
   - If false positive: Increase `failure_threshold` to 7
   - If slow detection: Decrease `failure_threshold` to 3
   - If flapping: Increase `timeout` to 90s

---

### Alert: MajorityKeysCircuitBreakerOpen
**Trigger:** >50% of API keys have OPEN circuit breaker for 5+ minutes  
**Severity:** 🔴 CRITICAL  
**Response Time:** <10 minutes

#### Actions

Similar to `AllKeysCircuitBreakerOpen` but less urgent:

1. **Assess Capacity**
   - Remaining healthy keys: `count(circuit_breaker_state == 0)`
   - Current request load: Check Grafana "API Request Rate" panel

2. **Prioritize Traffic**
   - If capacity < demand: Enable rate limiting
   - Route critical requests to healthy keys
   - Reject non-critical requests (503 Service Temporarily Unavailable)

3. **Scale Up (If Possible)**
   - Add more API keys to pool
   - Distribute load across providers (if multi-provider setup)

---

### Alert: CircuitBreakerFlapping
**Trigger:** >0.5 state transitions/second over 10 minutes  
**Severity:** 🟡 WARNING  
**Response Time:** <30 minutes

#### Diagnosis

Flapping indicates circuit breaker is rapidly opening and closing.

**Root Causes:**

1. **Threshold Too Sensitive**
   ```bash
   # Check current failure_threshold
   curl http://localhost:8000/api/v1/circuit-breaker/stats | jq '.[] | .config.failure_threshold'
   
   # If threshold=3: Too sensitive, increase to 5-7
   ```

2. **Intermittent Network Issues**
   ```bash
   # Check network latency to DeepSeek API
   ping -c 10 api.deepseek.com
   
   # Check for packet loss
   # Expected: <1% packet loss
   ```

3. **API Endpoint Instability**
   - Check DeepSeek status page for partial outages
   - Review error logs for alternating success/failure pattern

#### Resolution

**Short-term (Immediate)**
```python
# Increase failure_threshold temporarily
circuit_breaker.config.failure_threshold = 7

# Increase timeout to reduce flapping
circuit_breaker.config.timeout = 90
```

**Long-term (After Investigation)**
- Run load tests to find optimal thresholds
- Consider adaptive thresholds based on time of day
- Implement exponential backoff for timeout

---

### Alert: CircuitBreakerStuckHalfOpen
**Trigger:** Circuit breaker in HALF_OPEN state for 5+ minutes  
**Severity:** 🟡 WARNING  
**Response Time:** <30 minutes

#### Diagnosis

Circuit breaker attempting recovery but not getting 2 consecutive successes.

**Possible Causes:**

1. **API Partially Degraded**
   - Some requests succeed, most fail
   - Check success rate: `circuit_breaker_success_count / half_open_calls`

2. **Low Traffic**
   - Not enough requests to accumulate 2 successes
   - Check request rate

3. **half_open_max_calls Too Restrictive**
   - Only 3 concurrent calls allowed
   - If high traffic: Increase to 5

#### Resolution

**Option 1: Wait (Recommended)**
- Circuit breaker will eventually transition
- Either 2 successes → CLOSED
- Or 1 failure → OPEN (try again in 60s)

**Option 2: Increase half_open_max_calls**
```python
circuit_breaker.config.half_open_max_calls = 5
```

**Option 3: Manual Reset (If API Confirmed Healthy)**
```bash
curl -X POST http://localhost:8000/api/v1/circuit-breaker/<KEY_ID>/reset
```

---

## 🔧 Manual Operations

### Reset Circuit Breaker

```bash
# Reset all circuit breakers
curl -X POST http://localhost:8000/api/v1/circuit-breaker/reset

# Reset specific key
curl -X POST http://localhost:8000/api/v1/circuit-breaker/<KEY_ID>/reset

# Verify state after reset
curl http://localhost:8000/api/v1/circuit-breaker/stats | jq '.[] | {key_id, state}'
```

### Get Circuit Breaker Stats

```bash
# Get stats for all keys
curl http://localhost:8000/api/v1/circuit-breaker/stats | jq .

# Example output:
# [
#   {
#     "key_id": "abc123",
#     "provider": "deepseek",
#     "state": "closed",
#     "failure_count": 0,
#     "success_count": 0,
#     "config": {
#       "failure_threshold": 5,
#       "success_threshold": 2,
#       "timeout": 60
#     }
#   }
# ]
```

### Update Configuration (Hot Reload)

```bash
# Update failure_threshold for specific key
curl -X PATCH http://localhost:8000/api/v1/circuit-breaker/<KEY_ID>/config \
  -H "Content-Type: application/json" \
  -d '{"failure_threshold": 7}'

# Update timeout globally
curl -X PATCH http://localhost:8000/api/v1/circuit-breaker/config \
  -H "Content-Type: application/json" \
  -d '{"timeout": 90}'
```

---

## 📊 Grafana Dashboard Interpretation

### Panel: Circuit Breaker States by Key

**Healthy System:**
```
All lines at y=0 (GREEN) = All circuit breakers CLOSED
```

**Warning Signs:**
```
Line jumps to y=1 (YELLOW) = Circuit breaker testing recovery (HALF_OPEN)
```

**Critical Issue:**
```
Line at y=2 (RED) = Circuit breaker OPEN
All lines at y=2 = CRITICAL - No API capacity
```

### Panel: Circuit Breaker Trip Counter

**Healthy:**
- Trip count < 5 per hour
- Steady state (no rapid increases)

**Warning:**
- Trip count 5-10 per hour = Investigate API stability
- Rapid increase = Ongoing issue

**Critical:**
- Trip count > 10 per hour = Systemic problem

### Panel: State Transitions

**Healthy:**
- < 2 transitions per minute
- Occasional CLOSED → OPEN → HALF_OPEN → CLOSED (expected recovery)

**Flapping:**
- > 5 transitions per minute
- Rapid oscillation between states

---

## 🐛 Troubleshooting Common Issues

### Issue: Circuit Breaker Opens Immediately After Deployment

**Symptoms:**
- All circuit breakers open within seconds of starting backend
- No apparent API issues

**Root Cause:**
- Initialization code triggering failures
- Invalid API keys
- Wrong endpoint URL

**Resolution:**
```bash
# 1. Check API keys are valid
curl -H "Authorization: Bearer YOUR_KEY" https://api.deepseek.com/v1/models

# 2. Check backend logs for initialization errors
tail -f /var/log/backend/app.log | grep "CircuitBreaker"

# 3. Verify environment variables
env | grep DEEPSEEK
```

### Issue: Circuit Breaker Never Opens (Even During Outage)

**Symptoms:**
- API failing but circuit breaker stays CLOSED
- No state transitions in Grafana

**Root Cause:**
- `record_failure()` not being called
- Bug in error handling

**Resolution:**
```bash
# 1. Check if record_failure() is being called
grep -r "record_failure" /var/log/backend/

# 2. Verify circuit breaker integration
python -c "from api.circuit_breaker import CircuitBreaker; print('OK')"

# 3. Check prometheus metrics
curl http://localhost:8000/metrics | grep circuit_breaker_failure_count
# Should increment during API failures
```

### Issue: Prometheus Metrics Not Appearing

**Symptoms:**
- Grafana panels show "No data"
- Prometheus query returns empty result

**Root Cause:**
- prometheus_client not installed
- Backend not exposing /metrics endpoint
- Prometheus not scraping backend

**Resolution:**
```bash
# 1. Verify prometheus_client installed
pip show prometheus-client

# 2. Check /metrics endpoint
curl http://localhost:8000/metrics | head -20

# 3. Check Prometheus scraping
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="bybit_strategy_tester")'

# 4. If not scraping, add to prometheus.yml:
# scrape_configs:
#   - job_name: 'bybit_strategy_tester'
#     static_configs:
#       - targets: ['localhost:8000']
```

---

## 📞 Escalation Procedures

### Level 1: On-Call Engineer (Self-Service)
- **Response Time:** <5 minutes
- **Tools:** Grafana, logs, manual circuit breaker reset
- **Scope:** Standard alert responses from this runbook

### Level 2: Backend Team Lead
- **Escalate When:**
  - Circuit breakers flapping for >30 minutes
  - Unable to identify root cause
  - Manual resets ineffective
- **Contact:** Slack #backend-oncall, PagerDuty

### Level 3: Infrastructure Team
- **Escalate When:**
  - Network-related issues (latency, packet loss)
  - Prometheus/Grafana outage
  - System-wide API provider issues
- **Contact:** infrastructure@company.com, PagerDuty

### Level 4: API Provider Support
- **Escalate When:**
  - Confirmed DeepSeek API outage >1 hour
  - Rate limits not resetting properly
  - Authentication issues
- **Contact:** support@deepseek.com

---

## 📚 Additional Resources

- **Load Test Results:** `circuit_breaker_load_test_results.json`
- **Grafana Dashboard:** http://grafana:3000/d/circuit-breaker
- **Prometheus Alerts:** http://prometheus:9090/alerts
- **Circuit Breaker V2 Source:** `backend/api/circuit_breaker.py`
- **Integration Tests:** `test_circuit_breaker_v2.py`
- **Load Tests:** `test_circuit_breaker_load.py`

---

**End of Runbook**

**Feedback:** If you encounter scenarios not covered in this runbook, please update it and submit a PR.
