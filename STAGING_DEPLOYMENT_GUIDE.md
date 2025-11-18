# Staging Deployment Guide - Quick Wins #1-4

**Branch**: `feature/deadlock-prevention-clean`  
**Target Environment**: Staging  
**Deployment Date**: November 18, 2025  
**Expected Duration**: 1 week monitoring

---

## ✅ Pre-Deployment Checklist

### Code Quality
- [x] All 4 Quick Wins implemented and tested
- [x] 5/5 validation tests passed
- [x] No compilation errors
- [x] Git committed: `f1bc7dbc`
- [x] Branch: `feature/deadlock-prevention-clean`

### Configuration
- [x] `TOOL_CALL_BUDGET=10` added to `.env`
- [x] `.env.example` updated with documentation
- [x] Backward compatible (no breaking changes)

### Documentation
- [x] `QUICK_WINS_COMPLETE.md` - Implementation details
- [x] `DEPLOYMENT_CHECKLIST.md` - 4-week rollout plan
- [x] `SESSION_COMPLETE_QUICK_WINS.md` - Session summary
- [x] `STAGING_DEPLOYMENT_GUIDE.md` - This file

---

## 🚀 Deployment Steps

### Step 1: Verify Configuration

```powershell
# Check TOOL_CALL_BUDGET in .env
Get-Content .env | Select-String "TOOL_CALL_BUDGET"
# Expected: TOOL_CALL_BUDGET=10

# Verify Python can read it
py -c "from backend.agents.base_config import TOOL_CALL_BUDGET; print(f'TOOL_CALL_BUDGET = {TOOL_CALL_BUDGET}')"
# Expected: TOOL_CALL_BUDGET = 10
```

**✅ Completed**: Configuration verified

---

### Step 2: Run Pre-Deployment Tests

```powershell
# Quick Wins validation test
py test_quick_wins_validation.py
# Expected: 5/5 tests passed

# Syntax validation
py -m py_compile backend/agents/base_config.py
py -m py_compile backend/agents/unified_agent_interface.py
py -m py_compile backend/agents/agent_to_agent_communicator.py
# Expected: No errors

# Optional: Full backend test suite
pytest tests/backend -v --maxfail=3
```

**Status**: ⏳ Pending

---

### Step 3: Backup Current State

```powershell
# Create backup of current .env
Copy-Item .env .env.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')

# Tag current state
git tag -a staging-pre-quick-wins -m "State before Quick Wins deployment"

# Backup logs directory
Copy-Item logs logs.backup.$(Get-Date -Format 'yyyyMMdd') -Recurse -ErrorAction SilentlyContinue
```

**Status**: ⏳ Pending

---

### Step 4: Deploy to Staging

```powershell
# Stop all services
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "uvicorn" -Force -ErrorAction SilentlyContinue

# Clear old logs (optional)
Remove-Item logs/*.log -ErrorAction SilentlyContinue

# Start backend with new configuration
.\start.ps1
# Or manually:
# python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --reload
```

**Status**: ⏳ Pending

---

### Step 5: Verify Deployment

```powershell
# Check backend health
curl http://127.0.0.1:8000/api/health

# Check agent configuration
curl http://127.0.0.1:8000/api/v1/agent/health | ConvertFrom-Json

# Verify tool call budget
py -c "from backend.agents.base_config import TOOL_CALL_BUDGET; print(TOOL_CALL_BUDGET)"
# Expected: 10
```

**Expected Output**:
```json
{
  "status": "healthy",
  "mcp_server": "available",
  "deepseek_keys": 8,
  "perplexity_keys": 8,
  "tool_call_budget": 10
}
```

**Status**: ⏳ Pending

---

## 📊 Week 1: Monitoring Plan

### Daily Monitoring (Days 1-7)

#### Morning Check (09:00)

```powershell
# 1. Check for budget exceeded events
Get-Content logs/agent_background_service.log | Select-String "Budget exceeded" | Measure-Object
# Expected: < 1% of total requests

# 2. Check service health
curl http://127.0.0.1:8000/api/health

# 3. Review error logs
Get-Content logs/*.log | Select-String "ERROR" | Select-Object -Last 20
```

#### Afternoon Check (14:00)

```powershell
# 1. Check key selection distribution
Get-Content logs/*.log | Select-String "Key selected:" | Group-Object | Select-Object Count, Name
# Expected: Each key ~12.5% usage (1/8)

# 2. Monitor performance
Get-Content logs/*.log | Select-String "Tool call.*completed" | Measure-Object
# Track total tool calls per day

# 3. Check for rate limit errors
Get-Content logs/*.log | Select-String "429" | Measure-Object
# Expected: No increase compared to baseline
```

#### Evening Review (18:00)

```powershell
# Generate daily report
py -c "
import json
from pathlib import Path
from datetime import datetime

log_file = Path('logs/agent_background_service.log')
if log_file.exists():
    content = log_file.read_text()
    budget_exceeded = content.count('Budget exceeded')
    total_requests = content.count('Agent request')
    rate = (budget_exceeded / total_requests * 100) if total_requests > 0 else 0
    
    print(f'''
    Daily Report - {datetime.now().strftime('%Y-%m-%d')}
    =====================================
    Total Requests: {total_requests}
    Budget Exceeded: {budget_exceeded}
    Rate: {rate:.2f}%
    Status: {'✅ OK' if rate < 1 else '⚠️ REVIEW NEEDED'}
    ''')
"
```

### Metrics to Track

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| Budget exceeded rate | < 1% | Increase TOOL_CALL_BUDGET to 12 |
| 429 errors | Baseline ± 10% | Check async lock implementation |
| p95 latency | < +10ms | Profile async lock contention |
| Key imbalance | Max 20%, Min 5% | Investigate key selection logic |

---

## 🔍 Detailed Monitoring Commands

### Budget Exceeded Analysis

```powershell
# Count budget exceeded events
(Get-Content logs/*.log | Select-String "Budget exceeded").Count

# Get context around budget exceeded events
Get-Content logs/*.log | Select-String "Budget exceeded" -Context 5

# Identify which agents/tasks exceed budget most
Get-Content logs/*.log | Select-String "Budget exceeded" | 
    ForEach-Object { $_ -match "agent_type=(\w+)" | Out-Null; $Matches[1] } | 
    Group-Object | Sort-Object Count -Descending
```

### Key Selection Fairness

```powershell
# Distribution of key usage
Get-Content logs/*.log | Select-String "Key selected: (\w+-\d+)" | 
    ForEach-Object { $_ -match "Key selected: (\w+-\d+)" | Out-Null; $Matches[1] } | 
    Group-Object | Sort-Object Count -Descending | 
    Format-Table Name, Count, @{Label="Percent";Expression={($_.Count / (Get-Content logs/*.log | Select-String "Key selected:").Count * 100).ToString("0.00") + "%"}}

# Expected output:
# Name          Count  Percent
# ----          -----  -------
# deepseek-0    125    12.50%
# deepseek-1    125    12.50%
# ...
```

### Performance Monitoring

```powershell
# Average tool calls per request
$total_tools = (Get-Content logs/*.log | Select-String "Tool call #").Count
$total_requests = (Get-Content logs/*.log | Select-String "Agent request completed").Count
$avg = $total_tools / $total_requests
Write-Host "Average tool calls per request: $($avg.ToString('0.00'))"
# Target: < 10 (well under budget of 10)

# Tool call duration histogram
Get-Content logs/*.log | Select-String "Tool call.*completed.*\((\d+\.\d+)s\)" | 
    ForEach-Object { $_ -match "\((\d+\.\d+)s\)" | Out-Null; [double]$Matches[1] } | 
    Measure-Object -Average -Maximum -Minimum
```

### Error Rate Monitoring

```powershell
# 429 Rate Limit Errors
(Get-Content logs/*.log | Select-String "429|rate limit" -CaseSensitive:$false).Count

# Connection Errors
(Get-Content logs/*.log | Select-String "Connection error|timeout").Count

# MCP Server Errors
(Get-Content logs/*.log | Select-String "MCP.*error" -CaseSensitive:$false).Count
```

---

## 📋 Daily Status Report Template

```markdown
## Staging Daily Report - [DATE]

### Summary
- **Uptime**: XX hours
- **Total Requests**: XXX
- **Budget Exceeded**: X (X.XX%)
- **Rate Limit Errors**: X
- **System Status**: ✅ Healthy / ⚠️ Review Needed / ❌ Issues

### Key Metrics
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Budget exceeded rate | X.XX% | < 1% | ✅ / ⚠️ / ❌ |
| Avg tool calls/request | X.XX | < 10 | ✅ / ⚠️ / ❌ |
| 429 errors | XX | Baseline | ✅ / ⚠️ / ❌ |
| Key selection balance | OK / Imbalanced | Even | ✅ / ⚠️ / ❌ |

### Key Selection Distribution
```
deepseek-0:  12.5% (✅)
deepseek-1:  12.5% (✅)
...
```

### Issues Encountered
- [ ] None
- [ ] Budget too restrictive (describe)
- [ ] Performance degradation (describe)
- [ ] Other: [describe]

### Recommendations
- [ ] Continue monitoring
- [ ] Adjust TOOL_CALL_BUDGET to: XX
- [ ] Investigate issue: [describe]
- [ ] Ready for production deployment

### Next Actions
- [ ] [Action item 1]
- [ ] [Action item 2]
```

---

## ⚠️ Incident Response

### Budget Exceeded > 1% of Requests

**Symptoms**: Budget exceeded events > 1% of total requests

**Actions**:
1. Review logs for patterns: Which agents/tasks exceed budget?
2. Check if legitimate complex tasks or runaway loops
3. If legitimate: Increase `TOOL_CALL_BUDGET` to 12 or 15
4. If runaway loops: Investigate tool calling logic

```powershell
# Increase budget temporarily
$env:TOOL_CALL_BUDGET="12"
# Restart service
Restart-Service backend-api
```

### Key Selection Imbalance

**Symptoms**: One key > 20% usage or < 5% usage

**Actions**:
1. Check async lock is working correctly
2. Review key health status (error_count, requests_count)
3. Check for stuck keys (always selected or never selected)

```powershell
# Check key health
curl http://127.0.0.1:8000/api/v1/agent/keys/health | ConvertFrom-Json

# Reset key counters (if needed)
curl -X POST http://127.0.0.1:8000/api/v1/agent/keys/reset
```

### Increased 429 Errors

**Symptoms**: 429 rate limit errors > 10% increase

**Actions**:
1. Verify async lock is preventing concurrent key selection
2. Check if rate limit per key is exceeded
3. Review key rotation logic

```powershell
# Check async lock contention
Get-Content logs/*.log | Select-String "Lock acquired|Lock released" | Measure-Object

# If high contention, consider increasing key pool size
```

### Performance Degradation

**Symptoms**: p95 latency > +10ms compared to baseline

**Actions**:
1. Profile async lock acquisition time
2. Check for database connection pool exhaustion
3. Review tool call execution time

```powershell
# Measure lock contention
Get-Content logs/*.log | Select-String "async with.*_key_selection_lock" -Context 2

# Check database connections
curl http://127.0.0.1:8000/api/health/database | ConvertFrom-Json
```

---

## 🔄 Rollback Procedure

**If critical issues arise**, follow rollback plan:

### Quick Rollback (< 5 minutes)

```powershell
# 1. Stop services
Stop-Process -Name "python" -Force

# 2. Restore .env backup
Copy-Item .env.backup.* .env -Force

# 3. Checkout previous tag
git checkout staging-pre-quick-wins

# 4. Restart services
.\start.ps1

# 5. Verify rollback
curl http://127.0.0.1:8000/api/health
```

### Targeted Rollback (disable specific Quick Win)

**Quick Win #1 only** (disable budget):
```powershell
# Set very high budget (effectively disables limit)
$env:TOOL_CALL_BUDGET="999"
# Add to .env
Add-Content .env "TOOL_CALL_BUDGET=999"
# Restart
.\start.ps1
```

**Quick Win #2 only** (disable async lock):
```python
# Comment out lock in unified_agent_interface.py (line 293)
# async def get_active_key(...):
#     async with self._key_selection_lock:  # <-- Comment this line
# Restart service
```

---

## ✅ Week 1 Success Criteria

At end of Week 1, check all criteria:

- [ ] **Budget exceeded < 1%**: Achieved / Not achieved
- [ ] **No increase in 429 errors**: Achieved / Not achieved  
- [ ] **Even key distribution**: Achieved / Not achieved (all keys 5-20%)
- [ ] **Performance acceptable**: Achieved / Not achieved (p95 < +10ms)
- [ ] **No critical incidents**: Achieved / Not achieved
- [ ] **Logs reviewed daily**: Completed
- [ ] **Daily reports generated**: Completed

**If all criteria met**: ✅ **READY FOR PRODUCTION DEPLOYMENT (Week 2)**

**If 1-2 criteria not met**: ⚠️ **EXTEND STAGING BY 3 DAYS**

**If 3+ criteria not met**: ❌ **ROLLBACK & INVESTIGATE**

---

## 📞 Support & Escalation

**For deployment issues**:
1. Check `DEPLOYMENT_CHECKLIST.md` rollback section
2. Review `QUICK_WINS_COMPLETE.md` implementation details
3. Run `test_quick_wins_validation.py` to verify code integrity

**Escalation path**:
1. Check logs: `logs/agent_background_service.log`
2. Review metrics: Run monitoring commands above
3. Consult documentation: `QUICK_WINS_COMPLETE.md`

---

## 📅 Timeline

**Week 1** (Nov 18-24):
- **Day 1-2**: Initial deployment, close monitoring (3x daily checks)
- **Day 3-5**: Standard monitoring (2x daily checks)
- **Day 6-7**: Final validation, staging report preparation

**Week 2** (Nov 25 - Dec 1):
- Production deployment decision
- See `DEPLOYMENT_CHECKLIST.md` Step 4

---

**Status**: ✅ **READY TO BEGIN STAGING DEPLOYMENT**  
**Next Action**: Run Step 2 (Pre-Deployment Tests)  
**Deployment Window**: November 18, 2025 - November 24, 2025
