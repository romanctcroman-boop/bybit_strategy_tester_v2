# Prometheus Alerting Runbook - P0-6
# MCP Orchestrator Production Monitoring

This runbook provides detailed response procedures for all Prometheus alerts.

---

## Table of Contents

1. [HighACKFailureRate](#1-highackfailurerate)
2. [ACKSuccessRateDegradation](#2-acksuccessratedegradation)
3. [HighConsumerLag](#3-highconsumerlag)
4. [QueueDepthSpike](#4-queuedepthspike)
5. [ExpressLatencyHigh](#5-expresslatencyhigh)
6. [ExpressLatencyCritical](#6-expresslatencycritical)
7. [WorkerCrashRateHigh](#7-workercrashratehigh)
8. [NoActiveWorkers](#8-noactiveworkers)
9. [TaskFailureRateHigh](#9-taskfailureratehigh)
10. [Alert Testing Procedures](#alert-testing-procedures)

---

## 1. HighACKFailureRate

**Severity**: Critical  
**Threshold**: ACK failure rate > 1% for 5 minutes  
**Impact**: Tasks may be processed multiple times or lost

### Symptoms
- Increasing `mcp_ack_failures_total` counter
- Tasks stuck in XPENDING
- Duplicate task processing
- DLQ filling up with ACK failures

### Diagnostic Steps

1. **Check Redis connectivity**:
   ```bash
   redis-cli PING
   # Expected: PONG
   
   redis-cli INFO replication
   # Check for connection errors
   ```

2. **Review ACK handler logs**:
   ```bash
   grep "ACK.*failed" logs/orchestrator.log | tail -50
   grep "RobustRedisACKHandler" logs/orchestrator.log | tail -50
   ```

3. **Check XPENDING counts**:
   ```bash
   redis-cli XPENDING mcp:queue:reasoning:express mcp_express_reasoning
   redis-cli XPENDING mcp:queue:codegen:express mcp_express_codegen
   redis-cli XPENDING mcp:queue:ml:express mcp_express_ml
   ```

4. **Verify consumer group health**:
   ```bash
   redis-cli XINFO GROUPS mcp:queue:reasoning:express
   # Check for duplicate consumer IDs or orphaned consumers
   ```

### Resolution Steps

**Option A: Transient Issue (most common)**
1. Monitor for 5 more minutes
2. Check if self-recovering via orphan recovery loop
3. If recovering, no action needed

**Option B: Redis Connection Issue**
1. Restart Redis connection:
   ```bash
   # Restart worker pool to reset connections
   supervisorctl restart mcp-orchestrator
   ```
2. Check network: `ping redis-host`
3. Review Redis logs: `tail -100 /var/log/redis/redis.log`

**Option C: High Load / Timeouts**
1. Check Redis latency:
   ```bash
   redis-cli --latency-history
   # Should be <10ms
   ```
2. If latency >50ms, consider:
   - Scaling up Redis instance
   - Reducing worker pool size temporarily
   - Adding Redis read replicas

**Option D: Consumer Group Conflict**
1. List all consumers:
   ```bash
   redis-cli XINFO CONSUMERS mcp:queue:reasoning:express mcp_express_reasoning
   ```
2. Remove stale/duplicate consumers:
   ```bash
   redis-cli XGROUP DELCONSUMER mcp:queue:reasoning:express mcp_express_reasoning <stale-consumer-id>
   ```

### Prevention
- ✅ Monitor Redis health proactively
- ✅ Set Redis connection timeout to 5s
- ✅ Enable Redis connection keepalive
- ✅ Use RobustRedisACKHandler retry logic (3 attempts)
- ✅ Enable orphan recovery loop (30s interval)

---

## 2. ACKSuccessRateDegradation

**Severity**: Warning  
**Threshold**: ACK success rate < 99% for 10 minutes  
**Impact**: Increased task reprocessing, higher resource usage

### Diagnostic Steps

1. **Check current ACK success rate**:
   ```bash
   curl -s localhost:8000/metrics | grep mcp_ack_success_rate
   ```

2. **Check for transient Redis issues**:
   ```bash
   grep "Redis.*timeout\|Redis.*connection" logs/orchestrator.log | tail -20
   ```

3. **Review orphan recovery effectiveness**:
   ```bash
   grep "orphan.*claimed" logs/orchestrator.log | tail -20
   ```

### Resolution Steps

1. **Monitor for 15 minutes** - Often self-recovering
2. If not improving:
   - Check Redis latency (see HighACKFailureRate)
   - Review network stability
   - Consider temporary worker pool restart

### Prevention
- ✅ P0-2 Orphan Recovery Loop (already implemented)
- ✅ Monitor Redis connection pool health
- ✅ Set aggressive retry timers

---

## 3. HighConsumerLag

**Severity**: Warning  
**Threshold**: Pending messages > 100 for 10 minutes  
**Impact**: Increased task latency, SLA violations

### Symptoms
- Tasks queueing up faster than processing
- `mcp_consumer_group_lag` increasing
- User-facing latency increase

### Diagnostic Steps

1. **Check worker pool status**:
   ```bash
   curl localhost:8000/api/v1/workers/status
   # Verify all 6 workers (2x3 types) are running
   ```

2. **Check task processing rate**:
   ```bash
   curl -s localhost:8000/metrics | grep rate.*mcp_tasks_completed_total
   ```

3. **Check task latency**:
   ```bash
   curl -s localhost:8000/metrics | grep mcp_task_latency_seconds | grep reasoning
   ```

4. **Review worker logs for slow tasks**:
   ```bash
   grep "EXPRESS SLOW\|took.*ms" logs/orchestrator.log | tail -50
   ```

### Resolution Steps

**Option A: Load Spike (temporary)**
1. Monitor for 15 minutes
2. Check if lag decreasing naturally
3. No action if self-recovering

**Option B: Worker Undersized**
1. Temporarily increase worker pool:
   ```python
   # In config or env vars
   WORKERS_PER_TYPE=4  # Increase from 2 to 4
   ```
2. Restart orchestrator:
   ```bash
   supervisorctl restart mcp-orchestrator
   ```
3. Monitor lag improvement

**Option C: Slow Task Processing**
1. Check external API latency (Perplexity, Bybit)
2. Review network issues: `ping api.perplexity.ai`
3. Check for stuck tasks:
   ```bash
   redis-cli XPENDING mcp:queue:reasoning:express mcp_express_reasoning
   # Look for messages idle >60s
   ```
4. Manually claim stuck tasks:
   ```bash
   redis-cli XCLAIM mcp:queue:reasoning:express mcp_express_reasoning express_reasoning_0 60000 <msg-id>
   ```

**Option D: Express Routing Not Working**
1. Verify high-priority tasks going to express queue:
   ```bash
   redis-cli XLEN mcp:queue:reasoning:express
   redis-cli XLEN mcp:queue:reasoning  # Should be 0 or low
   ```
2. Check task priority assignment in logs
3. Review express routing logic (priority >= 12)

### Prevention
- ✅ Autoscaling based on queue depth (future P1 task)
- ✅ Proper express routing (priority >= 12)
- ✅ Monitor external API health
- ✅ Set aggressive task timeouts

---

## 4. QueueDepthSpike

**Severity**: Critical  
**Threshold**: Queue depth > 500 for 5 minutes  
**Impact**: Memory pressure, message loss risk, SLA violations

### Symptoms
- Redis memory usage increasing rapidly
- Task latency spiking
- Workers can't keep up with incoming rate

### Diagnostic Steps

1. **URGENT: Check Redis memory**:
   ```bash
   redis-cli INFO memory | grep used_memory_human
   redis-cli INFO memory | grep maxmemory_policy
   # If >80% of max, critical situation
   ```

2. **Check incoming task rate**:
   ```bash
   curl -s localhost:8000/metrics | grep rate.*mcp_tasks_enqueued_total
   ```

3. **Check worker processing rate**:
   ```bash
   curl -s localhost:8000/metrics | grep rate.*mcp_tasks_completed_total
   ```

4. **Check queue depths per type**:
   ```bash
   redis-cli XLEN mcp:queue:reasoning:express
   redis-cli XLEN mcp:queue:codegen:express
   redis-cli XLEN mcp:queue:ml:express
   ```

### Resolution Steps

**IMMEDIATE ACTIONS (if Redis memory >80%)**:
1. **Emergency worker scaling**:
   ```bash
   # Temporarily 4x worker count
   export WORKERS_PER_TYPE=8
   supervisorctl restart mcp-orchestrator
   ```

2. **Enable rate limiting** (if available):
   ```bash
   # Reject new tasks temporarily
   curl -X POST localhost:8000/api/v1/admin/rate-limit/enable
   ```

3. **Contact on-call immediately**

**STANDARD ACTIONS**:
1. **Check if load spike or sustained**:
   - Review task enqueue rate over last hour
   - Check if spike is expected (e.g., batch job)

2. **Verify workers processing**:
   ```bash
   curl localhost:8000/api/v1/workers/status
   ps aux | grep express_pool
   ```

3. **Check for stuck workers**:
   ```bash
   grep "Worker.*stuck\|Worker.*timeout" logs/orchestrator.log
   ```

4. **If workers healthy, scale up**:
   ```bash
   # Increase worker count
   WORKERS_PER_TYPE=4 supervisorctl restart mcp-orchestrator
   ```

5. **Consider temporary routing bypass**:
   - Route express tasks to regular queues
   - Disable priority routing temporarily

### Prevention
- ✅ Set Redis maxmemory policy: `allkeys-lru`
- ✅ Monitor Redis memory: Alert at 70%
- ✅ Implement rate limiting on task enqueue
- ✅ Autoscaling worker pool (future P1 task)
- ✅ Queue depth alerts (this alert)

---

## 5. ExpressLatencyHigh

**Severity**: Warning  
**Threshold**: p95 latency > 100ms for 5 minutes  
**Impact**: SLA violations, user-facing latency

### Diagnostic Steps

1. **Check current latency**:
   ```bash
   curl -s localhost:8000/metrics | grep mcp_task_latency_seconds | grep reasoning
   ```

2. **Check system load**:
   ```bash
   top
   free -h
   iostat
   ```

3. **Check Redis latency**:
   ```bash
   redis-cli --latency
   # Should be <10ms
   ```

4. **Check external API latency**:
   ```bash
   curl -w "@curl-format.txt" -o /dev/null -s https://api.perplexity.ai/status
   # Format file shows timing breakdown
   ```

### Resolution Steps

1. **If system resource constrained**:
   - Scale up CPU/memory
   - Reduce worker count temporarily

2. **If Redis slow**:
   - Check Redis CPU/memory
   - Consider Redis read replicas
   - Review slow queries: `redis-cli SLOWLOG GET 10`

3. **If external API slow**:
   - Check Perplexity API status
   - Review API quotas/rate limits
   - Consider caching API responses

4. **If network issues**:
   - Check network latency: `ping api.perplexity.ai`
   - Review DNS resolution time
   - Check for packet loss: `mtr api.perplexity.ai`

### Prevention
- ✅ Monitor external API health
- ✅ Set aggressive timeouts
- ✅ Implement circuit breakers for external APIs
- ✅ Cache frequent API calls

---

## 6. ExpressLatencyCritical

**Severity**: Critical  
**Threshold**: p95 latency > 500ms for 5 minutes  
**Impact**: Severe SLA violations, possible service degradation

### URGENT ACTIONS

1. **Check if external APIs down**:
   ```bash
   curl -I https://api.perplexity.ai
   curl -I https://api.bybit.com
   ```

2. **Check Redis performance**:
   ```bash
   redis-cli --latency-history
   # Look for spikes >100ms
   ```

3. **Check for resource exhaustion**:
   ```bash
   top
   free -h
   df -h
   ```

4. **If APIs down**:
   - Enable fallback/degraded mode
   - Return cached responses
   - Notify users of degraded service

5. **If system overloaded**:
   - Emergency load shedding: Reject new tasks
   - Scale up resources immediately
   - Page on-call engineer

### Resolution
- See ExpressLatencyHigh for detailed steps
- Escalate to on-call if not resolved in 10 minutes

---

## 7. WorkerCrashRateHigh

**Severity**: Critical  
**Threshold**: >0.5 crashes/sec for 10 minutes  
**Impact**: Service instability, task processing failures

### Diagnostic Steps

1. **Check crash reasons**:
   ```bash
   grep "ERROR\|CRITICAL\|Worker.*crashed" logs/orchestrator.log | tail -100
   ```

2. **Check for memory leaks**:
   ```bash
   curl -s localhost:8000/metrics | grep process_resident_memory_bytes
   # Check if growing over time
   ```

3. **Check OOM killer**:
   ```bash
   dmesg | grep -i 'killed process'
   journalctl | grep -i 'out of memory'
   ```

4. **Check for unhandled exceptions**:
   ```bash
   grep "Traceback\|Exception" logs/orchestrator.log | tail -50
   ```

### Resolution Steps

1. **If memory leak**:
   - Rolling restart workers
   - Review code for memory leaks
   - Add memory limits to workers

2. **If unhandled exceptions**:
   - Review exception logs
   - Add try-catch blocks
   - Deploy hotfix

3. **If Redis connection failures**:
   - See HighACKFailureRate runbook
   - Check Redis health
   - Verify network stability

4. **If resource exhaustion**:
   - Scale up host resources
   - Reduce worker count
   - Add resource limits

### Prevention
- ✅ Comprehensive exception handling
- ✅ Memory profiling in tests
- ✅ Resource limits per worker
- ✅ Health checks with auto-restart

---

## 8. NoActiveWorkers

**Severity**: Critical (Page immediately)  
**Threshold**: Active workers = 0 for 2 minutes  
**Impact**: Complete service outage

### URGENT ACTIONS

1. **Restart worker pool IMMEDIATELY**:
   ```bash
   supervisorctl restart mcp-orchestrator
   ```

2. **Check if process running**:
   ```bash
   ps aux | grep express_pool
   ps aux | grep orchestrator
   ```

3. **Review startup logs**:
   ```bash
   tail -100 logs/orchestrator.log
   supervisorctl tail mcp-orchestrator
   ```

4. **Check Redis connectivity**:
   ```bash
   redis-cli PING
   ```

5. **Page on-call if not resolved in 5 minutes**

### Resolution
- Workers should auto-start on restart
- If failing to start, check:
  - Redis connectivity
  - Configuration errors
  - Resource availability
  - Permission issues

### Prevention
- ✅ Process monitoring (supervisor/systemd)
- ✅ Auto-restart on failure
- ✅ Health checks
- ✅ Startup validation

---

## 9. TaskFailureRateHigh

**Severity**: Warning  
**Threshold**: Failure rate > 5% for 10 minutes  
**Impact**: Reduced throughput, DLQ filling up

### Diagnostic Steps

1. **Check failure reasons**:
   ```bash
   # Review DLQ
   redis-cli XLEN mcp:queue:dlq
   redis-cli XRANGE mcp:queue:dlq - + COUNT 10
   ```

2. **Check external API health**:
   ```bash
   curl -I https://api.perplexity.ai
   curl -I https://api.bybit.com
   ```

3. **Review error logs**:
   ```bash
   grep "Task.*failed\|ERROR" logs/orchestrator.log | tail -100
   ```

4. **Check for invalid payloads**:
   ```bash
   grep "ValidationError\|Invalid.*payload" logs/orchestrator.log
   ```

### Resolution Steps

1. **If external API failures**:
   - Wait for API recovery
   - Enable fallback responses
   - Retry failed tasks from DLQ

2. **If payload validation errors**:
   - Review task submission logic
   - Add input validation
   - Fix malformed requests

3. **If timeout issues**:
   - Increase task timeout
   - Optimize task processing
   - Scale up resources

4. **If network problems**:
   - Check DNS resolution
   - Review firewall rules
   - Verify API endpoints accessible

### Prevention
- ✅ Input validation on task submission
- ✅ Circuit breakers for external APIs
- ✅ Retry logic with exponential backoff
- ✅ DLQ monitoring and alerting

---

## Alert Testing Procedures

### Manual Alert Testing

#### 1. Test HighACKFailureRate
```bash
# Generate fake ACK failures
for i in {1..100}; do
  redis-cli XACK mcp:queue:reasoning:express mcp_express_reasoning fake-msg-$i
done

# Expected: Alert fires after 5 minutes
# Resolution: Failures will clear after test
```

#### 2. Test QueueDepthSpike
```bash
# Add 600 messages to queue
for i in {1..600}; do
  redis-cli XADD mcp:queue:reasoning:express "*" \
    task_id "test_$i" \
    payload '{"test":1}' \
    priority "15" \
    type "reasoning" \
    timestamp "$(date -Iseconds)"
done

# Expected: Alert fires after 5 minutes
# Resolution: Workers will process messages
```

#### 3. Test WorkerCrashRateHigh
```bash
# Kill workers repeatedly
for i in {1..6}; do
  pkill -9 -f express_pool
  sleep 10
done

# Expected: Alert fires after 10 minutes
# Resolution: Workers auto-restart via supervisor
```

#### 4. Test NoActiveWorkers
```bash
# Stop all workers
supervisorctl stop mcp-orchestrator

# Expected: Alert fires after 2 minutes (CRITICAL)
# Resolution: supervisorctl start mcp-orchestrator
```

### Automated Alert Testing

Create test script: `scripts/test_alerts.sh`
```bash
#!/bin/bash
# Test all alerts automatically

echo "Testing P0-6 Prometheus Alerts"
echo "==============================="

# Test 1: Queue Depth Spike
echo "1. Testing QueueDepthSpike..."
./scripts/test_alert_queue_depth.sh

# Test 2: No Active Workers
echo "2. Testing NoActiveWorkers..."
./scripts/test_alert_no_workers.sh

# Add more tests...
```

---

## Alerting Configuration

### Alertmanager Configuration

Create `alertmanager.yml`:
```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'team-platform'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    # Critical alerts with page=true -> PagerDuty
    - match:
        severity: critical
        page: "true"
      receiver: pagerduty
      continue: true
    
    # Critical alerts -> Slack critical channel
    - match:
        severity: critical
      receiver: slack-critical
      continue: true
    
    # Warning alerts -> Slack warning channel
    - match:
        severity: warning
      receiver: slack-warnings

receivers:
  - name: 'team-platform'
    slack_configs:
      - channel: '#team-platform'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
  
  - name: 'slack-critical'
    slack_configs:
      - channel: '#alerts-critical'
        title: 'CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'slack-warnings'
    slack_configs:
      - channel: '#alerts-warning'
        title: 'WARNING: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
  
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<your-pagerduty-key>'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
```

---

## Dashboard Links

- **Grafana**: http://grafana/d/mcp-orchestrator
- **Prometheus**: http://prometheus:9090
- **Metrics Endpoint**: http://localhost:8000/metrics
- **Health Check**: http://localhost:8000/healthz

---

## Emergency Contacts

- **On-Call Engineer**: PagerDuty (automated)
- **Platform Team**: Slack #team-platform
- **Critical Alerts**: Slack #alerts-critical

---

## Document Version

- **Version**: 1.0
- **Last Updated**: 2025-11-03
- **Author**: AI Assistant (P0-6 Implementation)
- **Next Review**: 2025-12-01
