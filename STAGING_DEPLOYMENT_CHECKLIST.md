# Phase 1 Staging Deployment Checklist

**Date**: November 18, 2025  
**Target**: Staging Server  
**Phase**: Phase 1 - Self-Healing Infrastructure  

---

## Pre-Deployment Verification

### ✅ Code Readiness
- [x] Phase 1 implementation complete (7 tasks)
- [x] Local integration tests passed
- [x] Direct Python verification successful
- [x] All 16 API keys active (8 DeepSeek + 8 Perplexity)
- [x] Circuit breakers operational (3 registered)
- [x] Health monitoring working (30s interval)
- [ ] All tests passing (`pytest tests/backend -v`)
- [ ] No critical linting errors

### ✅ Infrastructure Requirements

#### PostgreSQL
- [ ] Database server accessible
- [ ] Database created: `bybit_strategy_tester`
- [ ] User credentials configured
- [ ] Migrations applied: `alembic upgrade head`
- [ ] Connection pool settings optimal

#### Redis
- [ ] Redis server accessible (port 6379)
- [ ] DB 0: Cache
- [ ] DB 1: Celery broker
- [ ] DB 2: Results
- [ ] Memory limit configured
- [ ] Persistence enabled

#### Environment Variables
- [ ] `.env` file configured on staging
- [ ] All API keys present and valid
- [ ] Database URL correct
- [ ] Redis URL correct
- [ ] LOG_LEVEL set appropriately
- [ ] ENVIRONMENT=staging

### ✅ Dependencies
- [ ] Python 3.10+ installed
- [ ] All requirements.txt installed
- [ ] pybreaker==1.0.2 present
- [ ] httpx, loguru, fastapi, etc. versions match

---

## Deployment Steps

### Step 1: Git Operations
```bash
# On local machine
git add .
git commit -m "feat: Phase 1 - Self-healing infrastructure complete

- UnifiedAgentInterface with 16 API keys (8 DeepSeek + 8 Perplexity)
- Circuit breakers: deepseek_api, perplexity_api, mcp_server
- Health monitoring with auto-recovery (30s interval)
- Autonomy score calculation (baseline: 3.0-8.5/10)
- Comprehensive error handling and logging

Verification:
- Direct Python tests: PASSED
- Circuit breakers: 3 registered, all CLOSED
- Health checks: All components healthy
- API keys: All 16 active

Ready for 7-day staging monitoring."

git push origin feature/deadlock-prevention-clean
```

### Step 2: Staging Server Deployment
```bash
# SSH to staging server
ssh user@staging-server

# Pull latest code
cd /path/to/bybit_strategy_tester_v2
git pull origin feature/deadlock-prevention-clean

# Activate virtual environment
source .venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Restart services
sudo systemctl restart bybit-backend
sudo systemctl restart bybit-celery
```

### Step 3: Verification
```bash
# Run verification scripts
python verify_phase1_direct.py

# Check health endpoint
curl http://localhost:8000/health

# Check logs
tail -f logs/app.log
```

---

## Post-Deployment Verification

### Immediate Checks (First 30 minutes)
- [ ] Backend starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] Circuit breakers register successfully
- [ ] Health monitoring starts (check logs)
- [ ] All 16 API keys load correctly
- [ ] No Python exceptions in logs
- [ ] Database connections stable
- [ ] Redis connections stable

### Short-term Checks (First 24 hours)
- [ ] No unexpected circuit breaker trips
- [ ] Health monitoring runs every 30s
- [ ] Auto-recovery triggers when needed
- [ ] Autonomy score calculated correctly
- [ ] API key rotation working
- [ ] No memory leaks
- [ ] No database deadlocks

### Week 1 Monitoring (7 days)
- [ ] Track auto-recovery success rate (target: >85%)
- [ ] Monitor autonomy score trend
- [ ] Count human interventions (target: <2/week)
- [ ] Check circuit breaker trip frequency
- [ ] Analyze error patterns
- [ ] Review performance metrics

---

## Success Criteria

### Technical Metrics
1. **Auto-Recovery Rate**: ≥85% of failures resolved automatically
2. **Autonomy Score**: Baseline established, trending upward
3. **Human Interventions**: <2 per week
4. **Circuit Breaker Effectiveness**: >90% of cascading failures prevented
5. **Health Check Success**: >99% pass rate
6. **API Availability**: >99.9% uptime

### Operational Metrics
1. **Deployment Time**: <15 minutes downtime
2. **Zero Data Loss**: All data intact after deployment
3. **Rollback Ready**: Can rollback in <5 minutes if needed
4. **Monitoring Coverage**: All Phase 1 features monitored

---

## Rollback Plan

If critical issues detected within first 24 hours:

```bash
# SSH to staging
ssh user@staging-server

# Rollback to previous commit
cd /path/to/bybit_strategy_tester_v2
git log --oneline -5  # Find previous commit hash
git checkout <previous-commit-hash>

# Downgrade migrations if needed
alembic downgrade -1

# Restart services
sudo systemctl restart bybit-backend
sudo systemctl restart bybit-celery

# Verify rollback
curl http://localhost:8000/health
```

**Rollback Triggers**:
- Backend fails to start
- Database connections fail
- >50% circuit breakers open
- Memory usage >80%
- Critical exceptions in logs

---

## Monitoring Setup

### Dashboards to Create

#### 1. Circuit Breaker Dashboard
- **Metrics**:
  - Circuit breaker states (CLOSED/OPEN/HALF_OPEN)
  - Failure counts by breaker
  - Recovery attempts
  - Time in open state
- **Alerts**:
  - Any breaker open >5 minutes
  - >3 breakers open simultaneously

#### 2. Health Monitoring Dashboard
- **Metrics**:
  - Health check success rate
  - Component availability (DeepSeek/Perplexity/MCP)
  - Recovery action success rate
  - Active API keys count
- **Alerts**:
  - Health check success rate <95%
  - Any component down >2 minutes

#### 3. Autonomy Score Dashboard
- **Metrics**:
  - Current autonomy score
  - 7-day trend
  - Human intervention count
  - Auto-recovery success rate
- **Alerts**:
  - Autonomy score drops >2 points
  - >2 human interventions in 24h

### Log Aggregation
- **Tool**: ELK Stack or Grafana Loki
- **Log Sources**:
  - `logs/app.log` - Main application logs
  - `logs/unified_agent_interface.log` - Agent operations
  - `logs/circuit_breaker.log` - Breaker events
  - `logs/health_monitor.log` - Health checks
- **Retention**: 30 days

---

## Known Issues / Technical Debt

### Autonomous Improvement Orchestrator
- **Status**: ⏳ Debugging required
- **Issue**: Process terminates after ~20-24 seconds
- **Root Cause**: Unknown - possibly asyncio task management or Perplexity API timeout
- **Impact**: Low - doesn't affect Phase 1 deployment
- **Action**: Create separate debugging task for Phase 2

### Metrics System
- **Status**: ⚠️ Disabled
- **Issue**: "Metrics system not available" warning
- **Impact**: Low - logging still works
- **Action**: Investigate Prometheus metrics integration

### Perplexity API Performance
- **Status**: ⚠️ Slow
- **Issue**: 2+ minute response times
- **Impact**: Medium - affects multi-agent workflows
- **Action**: Consider timeout adjustments or alternative providers

---

## Next Steps After Deployment

1. **Week 1**: Monitor metrics, gather baseline data
2. **Week 2**: Analyze patterns, identify improvements
3. **Week 3**: Plan Phase 2 enhancements
4. **Week 4**: Review success criteria, prepare production deployment

---

## Contact / Escalation

- **Primary**: Development Team
- **Backup**: DevOps Team
- **Emergency**: On-call Engineer

**Deployment Lead**: [Your Name]  
**Date**: November 18, 2025  
**Sign-off**: [ ] Development Lead  [ ] DevOps Lead  [ ] QA Lead
