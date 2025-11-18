# 🔄 ROLLBACK STRATEGY - Production Recovery Guide

**Дата:** 2025-11-09  
**Версия:** 1.0  
**Статус:** Production Ready

---

## 📋 СОДЕРЖАНИЕ

1. [Overview](#overview)
2. [Database Rollback](#database-rollback)
3. [Docker Container Rollback](#docker-container-rollback)
4. [Application Code Rollback](#application-code-rollback)
5. [Configuration Rollback](#configuration-rollback)
6. [Emergency Procedures](#emergency-procedures)
7. [Rollback Testing](#rollback-testing)
8. [Post-Rollback Checklist](#post-rollback-checklist)

---

## 🎯 OVERVIEW

### **Rollback Principles**

1. **Always test rollback procedures in staging first**
2. **Maintain database backups before any migration**
3. **Use Git tags for version control**
4. **Document rollback decision and timing**
5. **Communicate with stakeholders during rollback**

### **When to Rollback**

✅ **Critical bugs affecting core functionality**  
✅ **Data corruption or loss**  
✅ **Security vulnerabilities discovered post-deployment**  
✅ **Performance degradation > 50%**  
✅ **Failed health checks for > 5 minutes**

❌ **Don't rollback for:**  
- Minor UI bugs (fix forward instead)
- Non-critical feature issues
- Cosmetic problems

---

## 💾 DATABASE ROLLBACK

### **Priority 1: BacktestEngine (No DB changes)**
**Status:** ✅ No database migration, safe to rollback

**Rollback Steps:**
```bash
# No database rollback needed
# Just revert application code (see Application Code Rollback section)
```

---

### **Priority 2: Strategy System (DB Migration Added)**
**Migration:** Added `interval` column to `backtests` table

#### **Rollback Procedure:**

**Step 1: Backup current database**
```bash
# Create backup before rollback
docker exec bybit-postgres pg_dump -U postgres bybit_tester > backup_before_rollback_$(date +%Y%m%d_%H%M%S).sql
```

**Step 2: Revert Alembic migration**
```bash
# Connect to API container
docker exec -it bybit-api bash

# Check current migration
alembic current

# Rollback one migration (Priority 2: interval column)
alembic downgrade -1

# Verify migration status
alembic current
```

**Step 3: Manual SQL rollback (if Alembic fails)**
```sql
-- Connect to database
docker exec -it bybit-postgres psql -U postgres -d bybit_tester

-- Drop interval column
ALTER TABLE backtests DROP COLUMN IF EXISTS interval;

-- Verify column is removed
\d backtests

-- Exit
\q
```

**Step 4: Restart backend**
```bash
docker-compose -f docker-compose.prod.yml restart api
```

**Step 5: Verify rollback**
```bash
# Check API health
curl http://localhost:8000/health

# Verify database schema
docker exec -it bybit-postgres psql -U postgres -d bybit_tester -c "\d backtests"
```

#### **Data Preservation:**

⚠️ **Warning:** Rolling back `interval` column will lose multi-timeframe configuration data.

**Preserve data before rollback:**
```sql
-- Export interval data before rollback
COPY (SELECT id, interval FROM backtests WHERE interval IS NOT NULL) 
TO '/tmp/interval_backup.csv' CSV HEADER;
```

**Restore data after re-deployment:**
```sql
-- Restore interval data
COPY backtests (id, interval) 
FROM '/tmp/interval_backup.csv' CSV HEADER;
```

---

### **Priority 3: Rate Limiting (No DB changes)**
**Status:** ✅ No database migration, safe to rollback

**Rollback Steps:**
```bash
# No database rollback needed
# Configuration changes only - revert .env file
```

---

### **Priority 4: Frontend Dashboard (No DB changes)**
**Status:** ✅ No backend database changes

**Rollback Steps:**
```bash
# Frontend only - redeploy previous Docker image
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend
```

---

### **Priority 5: Docker Deployment (Infrastructure)**
**Status:** ✅ Configuration-only changes

**Rollback Steps:**
```bash
# Revert docker-compose.prod.yml changes via Git
git checkout HEAD~1 docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🐳 DOCKER CONTAINER ROLLBACK

### **Full Stack Rollback**

**Step 1: Identify current version**
```bash
# Check current image tags
docker images | grep bybit

# Check running containers
docker ps | grep bybit
```

**Step 2: Stop current containers**
```bash
# Graceful shutdown (waits for connections to close)
docker-compose -f docker-compose.prod.yml down

# Force shutdown (if graceful fails after 30s)
docker-compose -f docker-compose.prod.yml down --timeout 5
```

**Step 3: Checkout previous version**
```bash
# Find previous Git tag
git tag -l | sort -V | tail -n 5

# Checkout previous version (e.g., v1.4.0)
git checkout v1.4.0

# Or checkout specific commit
git checkout <commit-hash>
```

**Step 4: Rebuild and deploy**
```bash
# Rebuild Docker images
docker-compose -f docker-compose.prod.yml build

# Deploy previous version
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
docker-compose -f docker-compose.prod.yml ps
```

**Step 5: Verify health**
```bash
# Check API health
curl http://localhost:8000/health

# Check frontend
curl http://localhost:3001/

# Check logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

---

### **Individual Service Rollback**

#### **Backend API Only:**
```bash
# Rebuild backend from previous version
docker-compose -f docker-compose.prod.yml build api

# Restart only API service
docker-compose -f docker-compose.prod.yml up -d --no-deps api

# Verify
curl http://localhost:8000/health
```

#### **Frontend Only:**
```bash
# Rebuild frontend from previous version
docker-compose -f docker-compose.prod.yml build frontend

# Restart only frontend service
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend

# Verify
curl http://localhost:3001/
```

#### **Database Rollback (Extreme Caution):**
```bash
# ⚠️ WARNING: This will restore database to previous backup
# All data changes since backup will be LOST

# Stop all services that use database
docker-compose -f docker-compose.prod.yml stop api

# Restore database from backup
docker exec -i bybit-postgres psql -U postgres -d bybit_tester < backup_20251109_120000.sql

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📦 APPLICATION CODE ROLLBACK

### **Git-based Rollback**

**Step 1: Identify version to rollback to**
```bash
# View recent commits
git log --oneline -n 10

# View tags
git tag -l | sort -V

# View specific commit details
git show <commit-hash>
```

**Step 2: Create rollback branch**
```bash
# Create new branch for rollback
git checkout -b rollback/to-v1.4.0 main

# Revert to specific commit (creates new revert commit)
git revert <commit-hash>

# Or reset to specific version (rewrites history - use carefully)
git reset --hard v1.4.0
```

**Step 3: Deploy rollback**
```bash
# Push rollback branch
git push origin rollback/to-v1.4.0

# Deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

**Step 4: Verify deployment**
```bash
# Check Git version
git log -1

# Check application health
curl http://localhost:8000/health

# Check version endpoint (if exists)
curl http://localhost:8000/version
```

---

### **File-specific Rollback**

**Rollback specific file:**
```bash
# Revert single file to previous version
git checkout HEAD~1 -- backend/core/backtest_engine.py

# Commit change
git commit -m "Rollback: Revert backtest_engine.py to stable version"

# Rebuild and deploy
docker-compose -f docker-compose.prod.yml build api
docker-compose -f docker-compose.prod.yml up -d --no-deps api
```

---

## ⚙️ CONFIGURATION ROLLBACK

### **Environment Variables (.env)**

**Rollback Steps:**
```bash
# Restore .env from backup
cp .env.backup.20251109 .env

# Restart services to apply new config
docker-compose -f docker-compose.prod.yml restart

# Verify configuration
docker-compose -f docker-compose.prod.yml exec api env | grep DEEPSEEK_API_KEY
```

### **Nginx Configuration**

**Rollback Steps:**
```bash
# Revert nginx.conf
git checkout HEAD~1 -- frontend/nginx.conf

# Rebuild frontend
docker-compose -f docker-compose.prod.yml build frontend

# Restart frontend
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend

# Test configuration
docker-compose -f docker-compose.prod.yml exec frontend nginx -t
```

### **Docker Compose Configuration**

**Rollback Steps:**
```bash
# Revert docker-compose.prod.yml
git checkout HEAD~1 -- docker-compose.prod.yml

# Apply new configuration
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Verify services
docker-compose -f docker-compose.prod.yml ps
```

---

## 🚨 EMERGENCY PROCEDURES

### **Emergency Full Rollback (< 5 minutes)**

**Scenario:** Critical production issue, need immediate rollback

```bash
#!/bin/bash
# emergency_rollback.sh

set -e  # Exit on error

echo "🚨 EMERGENCY ROLLBACK INITIATED"
echo "Time: $(date)"

# 1. Stop all services
echo "⏹️  Stopping all services..."
docker-compose -f docker-compose.prod.yml down --timeout 10

# 2. Checkout previous stable version
echo "⏪ Checking out previous version..."
git fetch --tags
PREVIOUS_TAG=$(git tag -l | sort -V | tail -n 2 | head -n 1)
git checkout $PREVIOUS_TAG

# 3. Restore database backup
echo "💾 Restoring database..."
docker-compose -f docker-compose.prod.yml up -d postgres
sleep 5
docker exec -i bybit-postgres psql -U postgres -d bybit_tester < /backups/latest.sql

# 4. Deploy previous version
echo "🚀 Deploying previous version..."
docker-compose -f docker-compose.prod.yml up -d

# 5. Wait for services to be healthy
echo "⏳ Waiting for services..."
sleep 30

# 6. Verify health
echo "✅ Verifying health..."
curl -f http://localhost:8000/health || echo "❌ API health check FAILED"
curl -f http://localhost:3001/ || echo "❌ Frontend health check FAILED"

echo "✅ EMERGENCY ROLLBACK COMPLETE"
echo "Time: $(date)"
```

**Usage:**
```bash
chmod +x emergency_rollback.sh
./emergency_rollback.sh
```

---

### **Emergency Database Restoration**

**Scenario:** Database corruption or data loss

```bash
#!/bin/bash
# restore_database.sh

set -e

echo "💾 DATABASE RESTORATION STARTED"

# 1. Stop API to prevent writes
docker-compose -f docker-compose.prod.yml stop api

# 2. Create current database dump (for safety)
docker exec bybit-postgres pg_dump -U postgres bybit_tester > /backups/before_restore_$(date +%Y%m%d_%H%M%S).sql

# 3. Drop and recreate database
docker exec -it bybit-postgres psql -U postgres -c "DROP DATABASE IF EXISTS bybit_tester;"
docker exec -it bybit-postgres psql -U postgres -c "CREATE DATABASE bybit_tester;"

# 4. Restore from backup
BACKUP_FILE=${1:-/backups/latest.sql}
docker exec -i bybit-postgres psql -U postgres -d bybit_tester < $BACKUP_FILE

# 5. Restart API
docker-compose -f docker-compose.prod.yml up -d api

# 6. Verify
sleep 10
curl -f http://localhost:8000/health

echo "✅ DATABASE RESTORATION COMPLETE"
```

**Usage:**
```bash
chmod +x restore_database.sh
./restore_database.sh /backups/backup_20251109_120000.sql
```

---

## 🧪 ROLLBACK TESTING

### **Pre-Production Rollback Test**

**Test rollback procedure in staging:**

```bash
# 1. Deploy latest version to staging
git checkout main
docker-compose -f docker-compose.prod.yml up -d

# 2. Create test data
curl -X POST http://localhost:8000/api/backtests -d '{...}'

# 3. Perform rollback
git checkout v1.4.0
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify data integrity
curl http://localhost:8000/api/backtests

# 5. Verify application functionality
# Run smoke tests...

# 6. Document rollback time
# Measure: Stop services → Deploy previous version → Services healthy
```

**Expected Rollback Times:**
- **Application Code Only:** 2-3 minutes
- **With Database Rollback:** 5-10 minutes
- **Full Stack Rollback:** 10-15 minutes

---

## ✅ POST-ROLLBACK CHECKLIST

### **Immediate Actions (0-15 minutes)**

- [ ] **Verify all services are healthy**
  ```bash
  docker-compose -f docker-compose.prod.yml ps
  curl http://localhost:8000/health
  curl http://localhost:3001/
  ```

- [ ] **Check application logs for errors**
  ```bash
  docker-compose -f docker-compose.prod.yml logs --tail=100
  ```

- [ ] **Verify database integrity**
  ```bash
  docker exec -it bybit-postgres psql -U postgres -d bybit_tester -c "SELECT COUNT(*) FROM backtests;"
  ```

- [ ] **Test critical user flows**
  - Login/authentication
  - Create backtest
  - View results
  - Dashboard loads

- [ ] **Monitor metrics**
  - Check Grafana dashboards
  - CPU/Memory usage normal
  - Response times < 500ms
  - No error spikes in logs

---

### **Short-term Actions (15-60 minutes)**

- [ ] **Notify stakeholders**
  - Send rollback notification
  - Explain reason for rollback
  - Provide ETA for fix

- [ ] **Document rollback**
  - Create incident report
  - Document root cause
  - Log rollback decision

- [ ] **Analyze root cause**
  - Review failed deployment logs
  - Identify what went wrong
  - Plan fix strategy

- [ ] **Create fix branch**
  ```bash
  git checkout -b hotfix/issue-description main
  ```

---

### **Long-term Actions (1-24 hours)**

- [ ] **Fix root cause**
  - Implement fix
  - Add tests to prevent regression
  - Code review

- [ ] **Test fix thoroughly**
  - Unit tests
  - Integration tests
  - Staging deployment

- [ ] **Plan re-deployment**
  - Schedule deployment window
  - Communicate with team
  - Prepare rollback plan for new deployment

- [ ] **Update documentation**
  - Update CHANGELOG
  - Document lessons learned
  - Improve rollback procedures if needed

---

## 📊 ROLLBACK DECISION MATRIX

| Issue Severity | Response Time | Action | Approval Required |
|----------------|---------------|--------|-------------------|
| **Critical** (System down) | < 5 min | Emergency rollback | On-call engineer |
| **High** (Major feature broken) | < 30 min | Standard rollback | Team lead |
| **Medium** (Minor issues) | < 2 hours | Fix forward | Developer |
| **Low** (Cosmetic bugs) | Next sprint | Fix forward | Product owner |

---

## 📞 CONTACTS & ESCALATION

**Emergency Rollback Authority:**
- On-call Engineer: [Contact info]
- DevOps Lead: [Contact info]
- CTO: [Contact info]

**Escalation Path:**
1. Developer → Team Lead (< 15 min)
2. Team Lead → DevOps Lead (< 30 min)
3. DevOps Lead → CTO (< 1 hour)

**Communication Channels:**
- Slack: #production-incidents
- Email: [email protected]
- PagerDuty: [PagerDuty integration]

---

## 📝 ROLLBACK LOG TEMPLATE

```markdown
# Rollback Incident Report

**Date:** YYYY-MM-DD HH:MM UTC
**Incident ID:** INC-XXXXX
**Severity:** Critical/High/Medium/Low

## Summary
Brief description of the issue that triggered rollback

## Timeline
- HH:MM - Issue detected
- HH:MM - Decision to rollback
- HH:MM - Rollback initiated
- HH:MM - Rollback completed
- HH:MM - Services verified healthy

## Root Cause
Detailed explanation of what caused the issue

## Rollback Procedure Used
- [ ] Application code rollback
- [ ] Database migration rollback
- [ ] Configuration rollback
- [ ] Full stack rollback

## Data Impact
- Records affected: XXX
- Data loss: Yes/No
- Data backup restored: Yes/No

## Lessons Learned
1. What went wrong
2. What we'll do differently next time

## Action Items
- [ ] Fix root cause (Owner: XXX, Due: YYYY-MM-DD)
- [ ] Add tests to prevent regression (Owner: XXX)
- [ ] Update deployment process (Owner: XXX)
```

---

**Signed:** GitHub Copilot  
**Date:** 2025-11-09  
**Version:** 1.0  
**Status:** ✅ Production Ready
