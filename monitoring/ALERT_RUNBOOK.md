# Alert Runbooks - Response Procedures

## Table of Contents
1. [TestWatcher Alerts](#testwatcher-alerts)
2. [AuditAgent Alerts](#auditagent-alerts)
3. [API Alerts](#api-alerts)
4. [System Alerts](#system-alerts)
5. [General Procedures](#general-procedures)

---

## TestWatcher Alerts

### TestWatcherDown (Critical)
**Symptom**: TestWatcher service is not running

**Impact**: Automated testing is disabled, code changes won't trigger tests

**Diagnosis**:
```powershell
# Check if TestWatcher is running
Get-Process -Name python | Where-Object {$_.CommandLine -like "*test_watcher*"}

# Check TestWatcher logs
Get-Content backend\logs\test_watcher.log -Tail 50

# Check metrics
curl http://localhost:9090/api/v1/query?query=test_watcher_is_running
```

**Resolution**:
1. Check error logs in `backend/logs/test_watcher.log`
2. Restart TestWatcher: `python backend/test_watcher.py`
3. Verify metric: `test_watcher_is_running` should be 1
4. Check Grafana dashboard for recovery

**Prevention**: 
- Add process supervisor (systemd/supervisor)
- Implement health checks
- Add retry logic for transient failures

---

### TestWatcherHighErrorRate (Critical)
**Symptom**: More than 0.1 errors per second for 5+ minutes

**Impact**: Tests may be failing incorrectly, unreliable results

**Diagnosis**:
```powershell
# Check error metrics
curl "http://localhost:9090/api/v1/query?query=rate(test_watcher_errors_total[5m])"

# Check specific errors in logs
Select-String -Path backend\logs\test_watcher.log -Pattern "ERROR" | Select-Object -Last 20

# Check error types
curl "http://localhost:9090/api/v1/query?query=test_watcher_errors_total" | ConvertFrom-Json
```

**Resolution**:
1. Identify error type from logs
2. Common errors:
   - File system issues: Check disk space, permissions
   - Test execution failures: Review failing tests
   - Import errors: Check dependencies
3. If persistent, restart TestWatcher
4. Monitor error rate for 10 minutes

**Escalation**: If error rate > 1/s, page on-call engineer

---

### TestWatcherQueueBacklog (Warning)
**Symptom**: More than 10 files in processing queue for 10+ minutes

**Impact**: Delayed test feedback, resource pressure

**Diagnosis**:
```powershell
# Check queue size
curl "http://localhost:9090/api/v1/query?query=test_watcher_changed_files_current"

# Check test execution time
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(test_watcher_test_execution_duration_seconds_bucket[5m]))"

# Check system resources
curl "http://localhost:9090/api/v1/query?query=system_cpu_percent"
```

**Resolution**:
1. Check if tests are running slowly (see TestWatcherSlowTests)
2. Check CPU/memory usage (may need more resources)
3. Consider:
   - Parallelizing tests
   - Optimizing slow tests
   - Increasing worker processes

**Prevention**: Set up queue size monitoring, optimize test suite

---

### TestWatcherSlowTests (Warning)
**Symptom**: 95th percentile test execution > 2 minutes

**Impact**: Slow feedback loop, developer productivity affected

**Diagnosis**:
```powershell
# Find slowest tests
pytest --durations=10 tests/

# Check execution time distribution
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(test_watcher_test_execution_duration_seconds_bucket[5m]))"
```

**Resolution**:
1. Identify slow tests from pytest duration report
2. Optimize slow tests:
   - Remove unnecessary fixtures
   - Mock external API calls
   - Reduce test data size
3. Consider splitting large test files
4. Use pytest-xdist for parallelization

**Long-term**: Implement test performance regression monitoring

---

## AuditAgent Alerts

### TestCoverageDrop (Critical)
**Symptom**: Coverage < 70% and dropped > 5% in 1 hour

**Impact**: Code quality risk, potential untested bugs

**Diagnosis**:
```powershell
# Check current coverage
pytest --cov=backend --cov-report=term-missing tests/

# Check coverage history
curl "http://localhost:9090/api/v1/query?query=audit_agent_coverage_percent"

# Find uncovered code
pytest --cov=backend --cov-report=html tests/
# Open htmlcov/index.html
```

**Resolution**:
1. Review recent code changes (git log --since="1 hour ago")
2. Identify uncovered code paths
3. Add missing tests immediately
4. Run audit: `python scripts/audit_agent.py`
5. Verify coverage recovery

**Prevention**: 
- Pre-commit hooks for coverage checks
- CI/CD pipeline coverage gates
- Regular coverage reviews

---

### TestCoverageLow (Warning)
**Symptom**: Coverage < 80% for 1+ hour

**Impact**: Below target, technical debt accumulating

**Diagnosis**:
```powershell
# Generate coverage report
pytest --cov=backend --cov-report=term-missing --cov-report=html tests/

# Check coverage by module
pytest --cov=backend --cov-report=term tests/ | Select-String "backend/"
```

**Resolution**:
1. Review coverage report (htmlcov/index.html)
2. Prioritize critical modules (> 85% coverage)
3. Add tests for high-impact code paths
4. Schedule tech debt sprint if needed

**Target**: Maintain 85%+ coverage across all modules

---

## API Alerts

### DeepSeekAPIDown / PerplexityAPIDown (Critical)
**Symptom**: All API calls failing for 5+ minutes

**Impact**: AI features unavailable, automation degraded

**Diagnosis**:
```powershell
# Check API status
curl https://api.deepseek.com/v1/health  # Example endpoint
curl https://api.perplexity.ai/health

# Check error logs
Select-String -Path backend\logs\api_client.log -Pattern "ERROR" -Context 2,2 | Select-Object -Last 10

# Check metrics
curl "http://localhost:9090/api/v1/query?query=rate(deepseek_api_calls_total{status='error'}[5m])"
```

**Resolution**:
1. Verify API credentials in `.env`
2. Check API status pages:
   - DeepSeek: https://status.deepseek.com
   - Perplexity: https://status.perplexity.ai
3. Test API manually:
   ```powershell
   python -c "from backend.api.deepseek_client import DeepSeekClient; DeepSeekClient().test_connection()"
   ```
4. If credentials issue: rotate API keys
5. If API outage: enable fallback mode (if available)

**Escalation**: Contact API provider support, consider alternative providers

---

### APIRateLimitExceeded (Critical)
**Symptom**: Rate limits hit > 0.5 times/second for 10+ minutes

**Impact**: API calls throttled, features degraded

**Diagnosis**:
```powershell
# Check rate limit metrics
curl "http://localhost:9090/api/v1/query?query=rate(api_rate_limits_total[5m])"

# Check API call frequency
curl "http://localhost:9090/api/v1/query?query=rate(deepseek_api_calls_total[1m])"

# Check quota usage
curl "http://localhost:9090/api/v1/query?query=api_quota_used"
```

**Resolution**:
1. Implement exponential backoff:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential
   
   @retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(5))
   def api_call():
       # Your API call
   ```
2. Add request queuing/throttling
3. Consider upgrading API plan
4. Cache API responses where possible

**Prevention**: Monitor API usage trends, set usage alerts at 80%

---

### APIHighErrorRate (Warning)
**Symptom**: > 10% of API calls failing

**Impact**: Reduced reliability, user experience degraded

**Diagnosis**:
```powershell
# Check error types
curl "http://localhost:9090/api/v1/query?query=api_errors_total" | ConvertFrom-Json

# Check recent errors
Select-String -Path backend\logs\api_client.log -Pattern "status_code" | Select-Object -Last 20
```

**Resolution**:
1. Group errors by type:
   - 4xx: Client errors (check request format)
   - 5xx: Server errors (API issues)
   - Timeout: Network/performance issues
2. Implement retry logic for transient errors
3. Add circuit breaker pattern
4. Monitor for 30 minutes after mitigation

---

## System Alerts

### HighCPUUsage (Critical)
**Symptom**: CPU usage > 90% for 5+ minutes

**Impact**: System slowdown, potential crashes

**Diagnosis**:
```powershell
# Check CPU usage
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10

# Check Python processes
Get-Process python | Sort-Object CPU -Descending

# Check metrics
curl "http://localhost:9090/api/v1/query?query=system_cpu_percent"
```

**Resolution**:
1. Identify CPU-intensive process
2. Check if expected (e.g., backtest running)
3. If unexpected:
   - Kill runaway process
   - Investigate root cause
   - Apply fixes
4. Consider scaling up resources

**Prevention**: Profile code, optimize algorithms, add resource limits

---

### MemoryLeakDetected (Critical)
**Symptom**: Memory growing > 10 MB/10min, > 1 GB total

**Impact**: System instability, potential OOM crash

**Diagnosis**:
```powershell
# Check memory usage
Get-Process python | Select-Object Name,@{Name='Memory(MB)';Expression={$_.WS / 1MB}}

# Profile memory
python -m memory_profiler backend/your_module.py

# Check metrics
curl "http://localhost:9090/api/v1/query?query=rate(process_resident_memory_bytes[10m])"
```

**Resolution**:
1. Identify leaking component from logs
2. Restart affected service immediately
3. Investigate root cause:
   - Unreleased resources (files, connections)
   - Growing caches
   - Circular references
4. Apply fix and monitor for 1 hour

**Prevention**: Regular memory profiling, proper resource cleanup, add memory limits

---

### HighDiskUsage (Warning)
**Symptom**: Disk usage > 85%

**Impact**: Risk of disk full errors, service failures

**Diagnosis**:
```powershell
# Check disk usage
Get-PSDrive C | Select-Object Used,Free,@{Name='PercentFree';Expression={($_.Free/$_.Used)*100}}

# Find large directories
Get-ChildItem -Path . -Recurse -Directory | 
    ForEach-Object {
        $size = (Get-ChildItem $_.FullName -Recurse | Measure-Object -Property Length -Sum).Sum
        [PSCustomObject]@{
            Path = $_.FullName
            SizeGB = [math]::Round($size/1GB, 2)
        }
    } | Sort-Object SizeGB -Descending | Select-Object -First 10
```

**Resolution**:
1. Clean up:
   - Old logs: `Remove-Item backend\logs\*.log.old`
   - Temp files: `Remove-Item $env:TEMP\* -Recurse -Force`
   - Docker: `docker system prune -a`
2. Rotate logs: Configure logrotate
3. Archive old data
4. Consider expanding disk

**Threshold**: Alert at 85%, critical at 95%

---

## General Procedures

### Alert Silencing
```powershell
# Silence alert for 2 hours
curl -X POST http://localhost:9093/api/v1/silences -d '{
  "matchers": [
    {"name": "alertname", "value": "TestWatcherDown", "isRegex": false}
  ],
  "startsAt": "2024-01-01T00:00:00Z",
  "endsAt": "2024-01-01T02:00:00Z",
  "createdBy": "oncall-engineer",
  "comment": "Planned maintenance"
}'
```

### Alert History
```powershell
# View recent alerts
curl http://localhost:9093/api/v1/alerts | ConvertFrom-Json | Select-Object -First 10

# View alert in Prometheus
curl "http://localhost:9090/api/v1/query?query=ALERTS{alertname='TestWatcherDown'}"
```

### Escalation Matrix
| Severity | Response Time | Escalation Path |
|----------|---------------|-----------------|
| Critical | 5 minutes | On-call → Team Lead → Manager |
| Warning | 30 minutes | On-call → Team Lead |
| Info | Next business day | Team review |

### Contact Information
- On-call Engineer: See PagerDuty schedule
- Team Lead: [Slack @team-lead]
- Slack Channels:
  - #alerts-critical - Critical alerts
  - #alerts-warning - Warning alerts
  - #alerts-info - Info alerts
  - #monitoring - General monitoring discussion

### Tools
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- AlertManager: http://localhost:9093
- Logs: `backend/logs/`

---

## Testing Alerts

See `monitoring/test_alerts.py` for testing alert firing.
