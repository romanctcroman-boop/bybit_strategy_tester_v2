# Alert Runbooks - Week 1, Day 6

**Purpose**: Detailed troubleshooting guides for each alert type  
**Audience**: On-call engineers, SRE team, DevOps  
**Last Updated**: November 5, 2025

---

## Table of Contents

1. [Application Health Alerts](#application-health-alerts)
   - [APIUnresponsive](#1-apiunresponsive)
   - [HighErrorRate](#2-higherrorrate)
   - [SlowResponseTime](#3-slowresponsetime)

2. [Database Alerts](#database-alerts)
   - [DatabaseDown](#4-databasedown)
   - [ConnectionPoolExhausted](#5-connectionpoolexhausted)
   - [DatabaseHighConnections](#6-databasehighconnections)
   - [SlowQueries](#7-slowqueries)

3. [Resource Utilization Alerts](#resource-utilization-alerts)
   - [HighCPUUsage](#8-highcpuusage)
   - [HighMemoryUsage](#9-highmemoryusage)
   - [DiskSpaceCritical](#10-diskspacecritical)

4. [Backup & DR Alerts](#backup--dr-alerts)
   - [BackupFailed](#11-backupfailed)
   - [BackupSizeAnomaly](#12-backupsizeanomaly)
   - [BackupUploadFailed](#13-backupuploadfailed)

5. [Celery Worker Alerts](#celery-worker-alerts)
   - [CeleryWorkersDown](#14-celeryworkersdown)
   - [HighTaskQueueLength](#15-hightaskqueuelength)
   - [TaskFailureRateHigh](#16-taskfailureratehigh)

6. [Security Alerts](#security-alerts)
   - [HighFailedLoginAttempts](#17-highfailedloginattempts)
   - [SSLCertificateExpiring](#18-sslcertificateexpiring)

---

## Application Health Alerts

### 1. APIUnresponsive

**Alert**: Backend API is unresponsive  
**Severity**: CRITICAL  
**Threshold**: up{job="backend"} == 0 for 2 minutes

#### Impact
- Complete application failure
- Users cannot access the system
- All trading operations halted
- Revenue loss

#### Symptoms
- Health endpoint (http://localhost:8000/health) returns 503 or times out
- Users see "Service Unavailable" errors
- Frontend cannot connect to backend

#### Immediate Actions (First 5 minutes)

1. **Check container status**:
   ```bash
   docker-compose ps backend
   docker-compose logs backend --tail 100
   ```

2. **Check for crashes**:
   ```bash
   # Look for error messages
   docker-compose logs backend | grep -i "error\|exception\|fatal"
   
   # Check exit code
   docker inspect backend --format='{{.State.ExitCode}}'
   ```

3. **Verify database connectivity**:
   ```bash
   docker-compose exec postgres pg_isready
   ```

4. **Quick restart attempt** (if no obvious cause):
   ```bash
   docker-compose restart backend
   
   # Wait 30 seconds
   sleep 30
   
   # Verify health
   curl http://localhost:8000/health
   ```

#### Detailed Troubleshooting

**If restart doesn't help**:

1. **Check resource exhaustion**:
   ```bash
   # CPU usage
   docker stats backend --no-stream
   
   # Memory usage
   docker exec backend ps aux --sort=-%mem | head -10
   ```

2. **Check port binding**:
   ```bash
   # Verify port 8000 is not in use
   netstat -tulpn | grep 8000
   ```

3. **Check application logs**:
   ```bash
   # Last 200 lines
   docker-compose logs backend --tail 200
   
   # Follow logs in real-time
   docker-compose logs -f backend
   ```

4. **Check database connection pool**:
   ```bash
   curl http://localhost:8000/health/db_pool
   ```

#### Resolution Steps

**Option A: Container restart fixed the issue**
```bash
# Verify health
curl http://localhost:8000/health
curl http://localhost:8000/health/db_pool

# Test critical endpoints
curl http://localhost:8000/strategies
curl http://localhost:8000/backtests
```

**Option B: Need to rebuild container**
```bash
docker-compose down backend
docker-compose build backend
docker-compose up -d backend

# Monitor startup
docker-compose logs -f backend
```

**Option C: DR procedure required** (if above fails)
```bash
# Initiate disaster recovery
python backend/scripts/dr_automation.py recover-app --report recovery_report.txt
```

#### Prevention
- Monitor memory leaks
- Implement graceful shutdown
- Add health check retries
- Review recent code changes

#### Escalation Path
1. **0-5 min**: On-call engineer attempts restart
2. **5-15 min**: Escalate to senior engineer
3. **15-30 min**: Engage platform team lead
4. **30+ min**: Initiate DR procedure

---

### 2. HighErrorRate

**Alert**: High HTTP 5xx error rate detected  
**Severity**: CRITICAL  
**Threshold**: > 5% error rate for 5 minutes

#### Impact
- 5% or more requests failing
- User experience severely degraded
- Potential data corruption
- Trust in platform reduced

#### Symptoms
- Users seeing "Internal Server Error" messages
- Failed API requests in logs
- Error tracking showing spike in errors

#### Immediate Actions (First 5 minutes)

1. **Identify error types**:
   ```bash
   # Check recent errors
   docker-compose logs backend --tail 500 | grep "500\|ERROR"
   
   # Group by error type
   docker-compose logs backend | grep ERROR | awk '{print $NF}' | sort | uniq -c | sort -rn
   ```

2. **Check error rate per endpoint**:
   ```bash
   # If using Prometheus
   curl -s 'http://localhost:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m])' | jq
   ```

3. **Verify recent deployments**:
   ```bash
   # Check last git commit
   git log -1 --oneline
   
   # Check deployment time
   docker inspect backend --format='{{.State.StartedAt}}'
   ```

#### Detailed Troubleshooting

**Common Causes**:

1. **Database connectivity issues**:
   ```bash
   # Test database connection
   docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "SELECT 1;"
   
   # Check connection pool
   curl http://localhost:8000/health/db_pool
   ```

2. **External service failures**:
   ```bash
   # Check Bybit API
   curl https://api.bybit.com/v5/market/tickers
   
   # Check Redis
   docker-compose exec redis redis-cli ping
   ```

3. **Resource exhaustion**:
   ```bash
   # Check memory
   docker stats backend --no-stream
   
   # Check disk space
   df -h
   ```

#### Resolution Steps

**If caused by recent deployment**:
```bash
# Rollback to previous version
git log --oneline -5
git checkout <previous-commit>
docker-compose build backend
docker-compose restart backend
```

**If caused by database issues**:
```bash
# Restart connection pool
docker-compose restart pgbouncer

# If that doesn't help, restart database
docker-compose restart postgres
```

**If caused by external service**:
```bash
# Enable circuit breaker
# Wait for service to recover
# Monitor error rate decrease
```

#### Prevention
- Add circuit breakers for external services
- Implement retry logic with exponential backoff
- Add rate limiting
- Improve error handling

#### Escalation Path
1. **0-10 min**: On-call engineer investigates
2. **10-20 min**: Escalate to backend team
3. **20-30 min**: Consider rollback
4. **30+ min**: Engage incident commander

---

### 3. SlowResponseTime

**Alert**: API response time above threshold  
**Severity**: WARNING  
**Threshold**: 95th percentile > 1 second for 10 minutes

#### Impact
- User experience degraded
- Application feels slow
- Potential timeout errors
- Increased server load

#### Symptoms
- Users complaining about slow performance
- Timeout errors in client applications
- High response times in metrics

#### Immediate Actions

1. **Identify slow endpoints**:
   ```bash
   # Check Prometheus metrics
   curl 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'
   ```

2. **Check database query performance**:
   ```bash
   docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;"
   ```

3. **Check for N+1 queries**:
   ```bash
   # Enable SQL logging (temporarily)
   docker-compose exec postgres psql -U postgres -c "
   ALTER SYSTEM SET log_min_duration_statement = 100;
   SELECT pg_reload_conf();"
   ```

#### Resolution Steps

**Optimize slow queries**:
```sql
-- Identify missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY abs(correlation) DESC;

-- Add index if needed
CREATE INDEX CONCURRENTLY idx_strategies_user_id ON strategies(user_id);
```

**Scale if load-related**:
```bash
# Increase backend replicas
docker-compose scale backend=3
```

**Clear cache if stale**:
```bash
docker-compose exec redis redis-cli FLUSHDB
```

#### Prevention
- Regular query performance reviews
- Add database query monitoring
- Implement query timeout limits
- Use connection pooling efficiently

---

## Database Alerts

### 4. DatabaseDown

**Alert**: PostgreSQL database is down  
**Severity**: CRITICAL  
**Threshold**: pg_up == 0 for 1 minute

#### Impact
- Complete application failure
- No data operations possible
- All user requests fail
- Potential data loss if not recovered quickly

#### Immediate Actions (First 2 minutes)

1. **Check PostgreSQL container**:
   ```bash
   docker-compose ps postgres
   docker-compose logs postgres --tail 100
   ```

2. **Check for crashes**:
   ```bash
   # Look for panic or fatal errors
   docker-compose logs postgres | grep -i "fatal\|panic\|aborting"
   ```

3. **Check disk space** (common cause):
   ```bash
   df -h /var/lib/postgresql/data
   ```

4. **Quick restart attempt**:
   ```bash
   docker-compose restart postgres
   
   # Wait for startup
   sleep 10
   
   # Test connection
   docker-compose exec postgres pg_isready
   ```

#### Detailed Troubleshooting

**If restart fails**:

1. **Check PostgreSQL logs**:
   ```bash
   docker-compose logs postgres --tail 500
   ```

2. **Check data directory permissions**:
   ```bash
   docker-compose exec postgres ls -la /var/lib/postgresql/data
   ```

3. **Check for corruption**:
   ```bash
   docker-compose exec postgres pg_checksums --check --pgdata=/var/lib/postgresql/data
   ```

#### Resolution Steps

**Option A: Container restart successful**
```bash
# Verify database integrity
docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM strategies;
SELECT COUNT(*) FROM backtests;"

# Restart backend to reconnect
docker-compose restart backend
```

**Option B: Data corruption detected**
```bash
# Initiate database recovery from backup
python backend/scripts/dr_automation.py recover-db --report db_recovery_report.txt
```

**Option C: Disk space issue**
```bash
# Clean up old data
python backend/scripts/backup_database.py apply-retention

# Remove old Docker volumes
docker system prune -a --volumes
```

#### Prevention
- Monitor disk space proactively
- Regular backup verification
- Implement database health checks
- Set up replication for HA

#### Escalation Path
1. **0-5 min**: On-call engineer attempts restart
2. **5-10 min**: Engage DBA
3. **10-20 min**: Initiate DR procedure
4. **20+ min**: Escalate to platform lead

---

### 5. ConnectionPoolExhausted

**Alert**: Database connection pool near capacity  
**Severity**: WARNING  
**Threshold**: > 90% pool usage for 2 minutes

#### Impact
- New requests may fail to acquire connections
- Application slowdown imminent
- Potential cascade failure

#### Immediate Actions

1. **Check current pool usage**:
   ```bash
   curl http://localhost:8000/health/db_pool
   ```

2. **Identify connection sources**:
   ```bash
   docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "
   SELECT pid, usename, application_name, state, query_start, state_change, query
   FROM pg_stat_activity
   WHERE datname = 'bybit_strategy_tester'
   ORDER BY query_start;"
   ```

3. **Check for connection leaks**:
   ```bash
   # Long-running connections
   docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "
   SELECT pid, now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'idle in transaction'
   AND now() - query_start > interval '5 minutes';"
   ```

#### Resolution Steps

**Kill idle connections**:
```sql
-- Kill connections idle > 10 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND now() - state_change > interval '10 minutes'
AND datname = 'bybit_strategy_tester';
```

**Increase pool size** (if legitimate traffic):
```bash
# Edit docker-compose.yml
# Change PG_POOL_SIZE environment variable
docker-compose up -d pgbouncer
```

**Restart connection pool**:
```bash
docker-compose restart pgbouncer
```

#### Prevention
- Implement connection timeouts
- Review application connection handling
- Monitor connection patterns
- Add connection leak detection

---

## Resource Utilization Alerts

### 8. HighCPUUsage

**Alert**: High CPU usage detected  
**Severity**: WARNING  
**Threshold**: > 80% for 5 minutes

#### Immediate Actions

1. **Identify CPU-intensive processes**:
   ```bash
   docker stats --no-stream
   docker exec backend top -b -n 1 | head -20
   ```

2. **Check for runaway processes**:
   ```bash
   docker exec backend ps aux --sort=-%cpu | head -10
   ```

3. **Review application profiling**:
   ```bash
   # If profiling enabled
   docker-compose logs backend | grep "Profile"
   ```

#### Resolution Steps

**Kill runaway process**:
```bash
docker exec backend kill -9 <PID>
```

**Scale up if sustained**:
```bash
docker-compose scale backend=3
```

**Optimize code**:
- Review recent code changes
- Add caching where appropriate
- Optimize algorithms

---

### 10. DiskSpaceCritical

**Alert**: Disk space critically low  
**Severity**: CRITICAL  
**Threshold**: < 15% free space for 5 minutes

#### Immediate Actions

1. **Identify large files**:
   ```bash
   du -h / | sort -rh | head -20
   ```

2. **Clean up logs**:
   ```bash
   docker-compose logs > /dev/null
   find /var/log -type f -name "*.log" -mtime +7 -delete
   ```

3. **Apply backup retention**:
   ```bash
   python backend/scripts/backup_database.py --retention-only
   ```

4. **Remove unused Docker resources**:
   ```bash
   docker system prune -a --volumes
   ```

#### Resolution Steps

**Emergency cleanup**:
```bash
# Remove old Docker images
docker image prune -a -f

# Remove old backups
find /backups -type f -mtime +30 -delete

# Truncate large log files
truncate -s 0 /var/log/postgresql/*.log
```

**Expand disk if needed**:
```bash
# On cloud provider, expand volume
# Then resize filesystem
resize2fs /dev/sda1
```

---

## Backup & DR Alerts

### 11. BackupFailed

**Alert**: Database backup failed or missing  
**Severity**: CRITICAL  
**Threshold**: No successful backup in 24 hours

#### Immediate Actions

1. **Check backup service logs**:
   ```bash
   docker-compose logs backend | grep -i backup
   ```

2. **Verify S3 connectivity**:
   ```bash
   aws s3 ls s3://bybit-backups/ --profile backup
   ```

3. **Check disk space**:
   ```bash
   df -h /backups
   ```

4. **Run manual backup**:
   ```bash
   python backend/scripts/backup_database.py --type daily --verify
   ```

#### Resolution Steps

**If S3 upload failed**:
```bash
# Check AWS credentials
aws sts get-caller-identity

# Retry upload
python backend/scripts/backup_database.py --upload-only
```

**If backup creation failed**:
```bash
# Check PostgreSQL accessibility
docker-compose exec postgres pg_dump --version

# Create backup manually
docker-compose exec postgres pg_dump -U postgres -Fc bybit_strategy_tester > /tmp/manual_backup.dump
```

---

## Celery Worker Alerts

### 14. CeleryWorkersDown

**Alert**: No Celery workers available  
**Severity**: CRITICAL  
**Threshold**: celery_workers_total == 0 for 2 minutes

#### Immediate Actions

1. **Check worker status**:
   ```bash
   docker-compose ps celery
   docker-compose logs celery --tail 100
   ```

2. **Check Redis broker**:
   ```bash
   docker-compose exec redis redis-cli ping
   ```

3. **Restart workers**:
   ```bash
   docker-compose restart celery
   ```

#### Resolution Steps

**If Redis connectivity issue**:
```bash
docker-compose restart redis
docker-compose restart celery
```

**If worker crashed**:
```bash
# Check for memory issues
docker stats celery --no-stream

# Rebuild if needed
docker-compose build celery
docker-compose up -d celery
```

---

## Security Alerts

### 17. HighFailedLoginAttempts

**Alert**: High rate of failed login attempts  
**Severity**: WARNING  
**Threshold**: > 10 attempts/second for 5 minutes

#### Immediate Actions

1. **Review login attempt sources**:
   ```bash
   docker-compose logs backend | grep "Failed login" | awk '{print $NF}' | sort | uniq -c | sort -rn
   ```

2. **Check for automated attacks**:
   ```bash
   # Look for patterns
   docker-compose logs backend | grep "Failed login" | grep -oP '\d+\.\d+\.\d+\.\d+' | sort | uniq -c | sort -rn
   ```

3. **Block suspicious IPs** (if firewall available):
   ```bash
   # Add to blocklist
   iptables -A INPUT -s <suspicious_ip> -j DROP
   ```

#### Resolution Steps

**Enable rate limiting**:
```python
# Add to backend config
RATE_LIMIT_LOGIN = "5 per minute"
```

**Alert security team**:
```bash
# Send Slack notification
python backend/scripts/notify_security_team.py --incident "brute_force_attempt"
```

---

## General Troubleshooting Commands

### Docker Commands
```bash
# View all containers
docker-compose ps

# View logs
docker-compose logs <service> --tail 100 --follow

# Restart service
docker-compose restart <service>

# Rebuild service
docker-compose build <service>
docker-compose up -d <service>

# Execute command in container
docker-compose exec <service> <command>
```

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Database connection pool
curl http://localhost:8000/health/db_pool

# Database direct
docker-compose exec postgres pg_isready

# Redis
docker-compose exec redis redis-cli ping
```

### Prometheus Queries
```bash
# Current metric value
curl 'http://localhost:9090/api/v1/query?query=<metric_name>'

# Metric over time
curl 'http://localhost:9090/api/v1/query_range?query=<metric_name>&start=<timestamp>&end=<timestamp>&step=60s'
```

---

## Escalation Matrix

| Time | Action | Contact |
|------|--------|---------|
| 0-5 min | On-call engineer attempts immediate remediation | Primary on-call |
| 5-15 min | If unresolved, escalate to senior engineer | Senior on-call |
| 15-30 min | Engage relevant team lead (platform/backend/database) | Team leads |
| 30-60 min | Incident commander coordination | Incident commander |
| 60+ min | Executive notification for critical incidents | CTO/VP Engineering |

---

## Contact Information

**Platform Team**:
- On-call: +1-xxx-xxx-xxxx
- Slack: #platform-oncall
- Email: platform-oncall@example.com

**Database Team**:
- On-call: +1-xxx-xxx-xxxx
- Slack: #database-oncall
- Email: dba-oncall@example.com

**Security Team**:
- On-call: +1-xxx-xxx-xxxx
- Slack: #security-oncall
- Email: security@example.com

**Incident Commander**:
- Phone: +1-xxx-xxx-xxxx
- Slack: @incident-commander

---

**Last Updated**: November 5, 2025  
**Version**: 1.0  
**Maintained By**: Platform SRE Team
