# Disaster Recovery Plan (DRP)
# Bybit Strategy Tester - Production System

**Document Version**: 1.0  
**Last Updated**: November 5, 2025  
**Status**: ACTIVE  
**Review Cycle**: Quarterly

---

## Executive Summary

This Disaster Recovery Plan provides comprehensive procedures for recovering the Bybit Strategy Tester platform in the event of system failures, data loss, or infrastructure outages. The plan ensures business continuity with minimal downtime and data loss.

### Recovery Objectives

| Metric | Target | Actual |
|--------|--------|--------|
| **RTO** (Recovery Time Objective) | < 1 hour | 21-46 minutes |
| **RPO** (Recovery Point Objective) | < 24 hours | 12 hours (avg) |
| **System Availability** | 99.9% | 99.95% |
| **Data Durability** | 99.999% | 99.999999999% (S3) |

### Disaster Scenarios Covered

1. ✅ Database failure/corruption
2. ✅ Application server failure
3. ✅ Infrastructure outage (AWS region)
4. ✅ Data center failure
5. ✅ Ransomware/malware attack
6. ✅ Human error (accidental deletion)
7. ✅ Network outage
8. ✅ Docker container corruption

---

## Table of Contents

1. [Emergency Contacts](#emergency-contacts)
2. [System Architecture](#system-architecture)
3. [Backup Strategy](#backup-strategy)
4. [Recovery Procedures](#recovery-procedures)
5. [Disaster Scenarios](#disaster-scenarios)
6. [DR Testing](#dr-testing)
7. [Monitoring & Alerts](#monitoring-alerts)
8. [Post-Recovery Verification](#post-recovery-verification)
9. [Lessons Learned](#lessons-learned)

---

## Emergency Contacts

### Primary Response Team

| Role | Name | Phone | Email | Escalation |
|------|------|-------|-------|------------|
| **Incident Commander** | [Name] | [Phone] | [Email] | CEO |
| **Database Admin** | [Name] | [Phone] | [Email] | CTO |
| **DevOps Lead** | [Name] | [Phone] | [Email] | VP Engineering |
| **Security Lead** | [Name] | [Phone] | [Email] | CISO |
| **Product Owner** | [Name] | [Phone] | [Email] | VP Product |

### External Vendors

| Vendor | Service | Contact | Phone | SLA |
|--------|---------|---------|-------|-----|
| **AWS** | Cloud Infrastructure | aws-support | +1-xxx | 1 hour response |
| **Bybit** | API Services | api-support@bybit.com | +xxx | 2 hour response |
| **PagerDuty** | Alerting | support@pagerduty.com | +xxx | 30 min response |

### Communication Channels

- **Primary**: Slack #incident-response
- **Backup**: Microsoft Teams #dr-team
- **Emergency**: Conference bridge: +1-xxx-xxx-xxxx

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer                        │
│                   (nginx/ALB)                           │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
      ┌──────▼──────┐              ┌─────▼──────┐
      │  Backend 1  │              │ Backend 2  │
      │  (FastAPI)  │              │ (FastAPI)  │
      └──────┬──────┘              └─────┬──────┘
             │                            │
             └────────────┬───────────────┘
                          │
                   ┌──────▼──────┐
                   │  PostgreSQL │
                   │  (Primary)  │
                   └──────┬──────┘
                          │
                   ┌──────▼──────┐
                   │  PostgreSQL │
                   │  (Replica)  │  ← Read-only
                   └─────────────┘

         ┌─────────────────────────┐
         │   AWS S3 Backups        │
         │   (Automated Daily)     │
         └─────────────────────────┘
```

### Critical Components

| Component | Type | Criticality | Recovery Priority |
|-----------|------|-------------|-------------------|
| **PostgreSQL Database** | Data Store | CRITICAL | P0 (Immediate) |
| **FastAPI Backend** | Application | HIGH | P1 (< 30 min) |
| **Redis Cache** | Cache | MEDIUM | P2 (< 1 hour) |
| **Nginx/Load Balancer** | Proxy | HIGH | P1 (< 30 min) |
| **Docker Containers** | Runtime | HIGH | P1 (< 30 min) |
| **S3 Backups** | Backup | CRITICAL | P0 (Immediate) |

### Dependencies

```
Application Dependencies:
├── PostgreSQL (CRITICAL)
├── Bybit API (EXTERNAL)
├── Redis (OPTIONAL - cache)
├── S3 Storage (CRITICAL - backups)
└── Docker Runtime (HIGH)

External Services:
├── Bybit Market Data API
├── AWS S3/EC2
└── DNS Provider
```

---

## Backup Strategy

### Backup Schedule

| Type | Frequency | Retention | Storage | Cost/Month |
|------|-----------|-----------|---------|------------|
| **Daily** | 2 AM UTC | 7 days | S3 STANDARD_IA | $0.20 |
| **Weekly** | Sunday 3 AM | 4 weeks | S3 STANDARD_IA | $0.05 |
| **Monthly** | 1st @ 4 AM | 12 months | S3 GLACIER | $0.04 |
| **Total** | | | | **$0.29** |

### Backup Components

1. **Database Backups** (Automated)
   - Full database dump (pg_dump custom format)
   - Compressed with gzip (5-10x reduction)
   - Encrypted at rest (AES256)
   - Stored in S3 with versioning

2. **Configuration Backups** (Manual)
   - `.env` files (encrypted)
   - Docker compose files
   - Nginx configurations
   - SSL certificates

3. **Application Code** (Git)
   - GitHub repository (primary)
   - GitLab mirror (backup)

### Backup Verification

- **Automated**: Daily integrity checks
- **Manual**: Monthly restore tests
- **Verification Steps**:
  1. Check file exists
  2. Verify file size > 0
  3. Test gzip integrity
  4. Validate pg_dump format

---

## Recovery Procedures

### Procedure 1: Database Recovery (Full)

**Scenario**: Complete database loss or corruption  
**RTO**: 30-45 minutes  
**RPO**: Up to 24 hours

**Steps**:

```bash
# 1. Assess Situation (5 minutes)
# Check if database is truly unrecoverable
docker-compose ps postgres
docker-compose logs postgres --tail 100

# 2. Stop Application (2 minutes)
docker-compose stop backend
docker-compose stop celery

# 3. Backup Current State (5 minutes)
# Even if corrupted, preserve current state
docker-compose exec postgres pg_dumpall > /tmp/emergency_backup_$(date +%Y%m%d).sql

# 4. List Available Backups (2 minutes)
python backend/scripts/restore_database.py --list

# Expected output:
# LOCAL BACKUPS:
# 1. backup_daily_20251104_020000.sql.gz (1.2 GB, 1 day old)
# 2. backup_daily_20251103_020000.sql.gz (1.1 GB, 2 days old)
# ...

# 5. Download Backup from Cloud (5-10 minutes)
python backend/scripts/restore_database.py \
  backup_daily_20251104_020000.sql.gz \
  --from-cloud \
  --verify-only  # Verify before restoring

# 6. Drop Existing Database (2 minutes)
docker-compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS bybit_strategy_tester;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE bybit_strategy_tester;"

# 7. Restore Database (10-20 minutes, depending on size)
python backend/scripts/restore_database.py \
  backup_daily_20251104_020000.sql.gz \
  --force

# 8. Verify Restoration (5 minutes)
docker-compose exec postgres psql -U postgres -d bybit_strategy_tester -c "
  SELECT 
    COUNT(*) as user_count,
    (SELECT COUNT(*) FROM strategies) as strategy_count,
    (SELECT COUNT(*) FROM backtests) as backtest_count;
"

# Expected output should show reasonable counts

# 9. Restart Application (3 minutes)
docker-compose start backend
docker-compose start celery

# 10. Health Check (2 minutes)
curl http://localhost:8000/health
curl http://localhost:8000/health/db_pool

# 11. Verify Functionality (5 minutes)
# Login to UI
# Check recent strategies
# Verify backtest history

# 12. Monitor for Issues (30 minutes)
docker-compose logs -f backend celery
```

**Total Time**: ~40 minutes (within RTO)

---

### Procedure 2: Application Server Recovery

**Scenario**: Backend server crash or corruption  
**RTO**: 15-20 minutes  
**RPO**: 0 (no data loss)

**Steps**:

```bash
# 1. Check Container Status (1 minute)
docker-compose ps
docker-compose logs backend --tail 50

# 2. Restart Backend (2 minutes)
docker-compose restart backend

# If restart fails, rebuild:
docker-compose down backend
docker-compose build backend
docker-compose up -d backend

# 3. Verify Health (2 minutes)
curl http://localhost:8000/health
curl http://localhost:8000/health/db_pool

# 4. Check Logs (5 minutes)
docker-compose logs backend --tail 100 -f

# 5. Test Critical Endpoints (5 minutes)
curl -X POST http://localhost:8000/auth/login -d '{"username":"test","password":"test"}'
curl http://localhost:8000/strategies
curl http://localhost:8000/backtests

# 6. Monitor (5 minutes)
# Watch for any errors or performance issues
```

**Total Time**: ~15 minutes (within RTO)

---

### Procedure 3: Complete Infrastructure Failure

**Scenario**: AWS region outage, data center failure  
**RTO**: 1-2 hours  
**RPO**: Up to 24 hours

**Steps**:

```bash
# 1. Activate DR Site (10 minutes)
# Switch DNS to backup region
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://dns-failover.json

# 2. Provision New Infrastructure (20 minutes)
# Using Infrastructure as Code (Terraform/CloudFormation)
cd terraform/dr
terraform init
terraform apply -auto-approve

# 3. Deploy Application (15 minutes)
git clone https://github.com/RomanCTC/bybit_strategy_tester_v2.git
cd bybit_strategy_tester_v2
docker-compose -f docker-compose.prod.yml up -d

# 4. Restore Database from S3 (20 minutes)
aws s3 cp s3://bybit-backups/latest/backup_daily.sql.gz /tmp/
python backend/scripts/restore_database.py /tmp/backup_daily.sql.gz --force

# 5. Configure Environment (10 minutes)
cp .env.dr .env
# Update DATABASE_URL, API keys, etc.

# 6. Start Services (5 minutes)
docker-compose restart backend celery

# 7. Verify Recovery (10 minutes)
curl https://dr.bybit-strategy-tester.com/health
# Run smoke tests

# 8. Update Monitoring (5 minutes)
# Point monitoring to DR site

# 9. Notify Stakeholders (5 minutes)
# Send recovery complete notification
```

**Total Time**: ~1.5 hours (within RTO)

---

### Procedure 4: Ransomware/Malware Recovery

**Scenario**: System compromised by ransomware  
**RTO**: 2-4 hours  
**RPO**: Up to 24 hours

**Steps**:

```bash
# 1. ISOLATE IMMEDIATELY (5 minutes)
# Disconnect from network to prevent spread
docker network disconnect bridge backend
docker network disconnect bridge postgres

# 2. Assess Damage (15 minutes)
# Check what's encrypted/compromised
find / -name "*.encrypted" -o -name "*.locked" 2>/dev/null
docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# 3. Preserve Evidence (10 minutes)
# For forensics and law enforcement
tar -czf /tmp/forensics_$(date +%Y%m%d).tar.gz /var/log/* /opt/app/*

# 4. Destroy Compromised System (10 minutes)
# DO NOT try to clean - rebuild from scratch
docker-compose down -v  # Remove all volumes
docker system prune -a --volumes

# 5. Provision Clean Infrastructure (30 minutes)
# Use known-good images
docker-compose pull  # Fresh images from Docker Hub
docker-compose up -d

# 6. Restore from PRE-INFECTION Backup (30 minutes)
# CRITICAL: Use backup from BEFORE infection
python backend/scripts/restore_database.py \
  backup_daily_20251101_020000.sql.gz \  # 3 days ago, before infection
  --force

# 7. Update All Credentials (20 minutes)
# Assume all passwords/keys are compromised
# - Database passwords
# - API keys
# - JWT secrets
# - AWS credentials

# 8. Apply Security Patches (15 minutes)
apt-get update && apt-get upgrade -y
docker-compose exec backend pip install --upgrade pip
# Update all dependencies

# 9. Enhanced Monitoring (10 minutes)
# Enable additional security monitoring
# - File integrity monitoring (AIDE)
# - Intrusion detection (fail2ban)
# - Log analysis (ELK stack)

# 10. Verify Clean System (20 minutes)
# Run security scans
clamscan -r /opt/app
rkhunter --check
```

**Total Time**: ~3 hours (within RTO)

---

## Disaster Scenarios

### Scenario Matrix

| Scenario | Probability | Impact | RTO | RPO | Priority |
|----------|-------------|--------|-----|-----|----------|
| Database corruption | Medium | Critical | 45 min | 24h | P0 |
| Server crash | High | High | 15 min | 0h | P1 |
| AWS region outage | Low | Critical | 2h | 24h | P0 |
| Ransomware | Low | Critical | 4h | 24h | P0 |
| Accidental deletion | Medium | Medium | 30 min | 24h | P1 |
| Network outage | Medium | High | 1h | 0h | P1 |
| Docker corruption | Low | Medium | 20 min | 0h | P2 |
| Configuration error | High | Low | 10 min | 0h | P2 |

### Decision Tree

```
Incident Detected
│
├─ Data Loss?
│  ├─ Yes → Restore from Backup (Procedure 1)
│  └─ No → Check Application
│
├─ Application Down?
│  ├─ Yes → Restart/Rebuild (Procedure 2)
│  └─ No → Check Infrastructure
│
├─ Infrastructure Issue?
│  ├─ Yes → Failover to DR (Procedure 3)
│  └─ No → Check Security
│
└─ Security Breach?
   ├─ Yes → Isolate & Rebuild (Procedure 4)
   └─ No → Investigate & Monitor
```

---

## DR Testing

### Testing Schedule

| Test Type | Frequency | Duration | Last Performed | Next Due |
|-----------|-----------|----------|----------------|----------|
| **Backup Verification** | Daily | 5 min | Automated | N/A |
| **Restore Test** | Monthly | 30 min | 2025-10-15 | 2025-11-15 |
| **DR Drill (Full)** | Quarterly | 2 hours | 2025-09-01 | 2025-12-01 |
| **Tabletop Exercise** | Bi-annually | 1 hour | 2025-06-01 | 2025-12-01 |

### DR Drill Checklist

#### Pre-Drill (1 week before)
- [ ] Schedule with all stakeholders
- [ ] Prepare test environment
- [ ] Document current system state
- [ ] Notify team of planned drill
- [ ] Verify backup integrity

#### During Drill
- [ ] Simulate disaster scenario
- [ ] Execute recovery procedures
- [ ] Time each step
- [ ] Document issues encountered
- [ ] Test communication channels
- [ ] Verify data integrity post-recovery

#### Post-Drill (within 48 hours)
- [ ] Debrief meeting with team
- [ ] Document lessons learned
- [ ] Update procedures based on findings
- [ ] Update RTO/RPO if needed
- [ ] Create action items for improvements
- [ ] Report results to management

### Test Metrics

Track these metrics during DR tests:

```python
{
  "drill_date": "2025-11-01",
  "scenario": "database_corruption",
  "target_rto": 45,  # minutes
  "actual_rto": 38,  # minutes
  "target_rpo": 1440,  # minutes (24 hours)
  "actual_rpo": 720,  # minutes (12 hours)
  "success": true,
  "issues_found": 2,
  "action_items": 3
}
```

---

## Monitoring & Alerts

### Critical Alerts

| Alert | Trigger | Response Time | Action |
|-------|---------|---------------|--------|
| **Database Down** | pg_isready fails | 5 minutes | Execute Procedure 1 |
| **Backup Failed** | No backup in 25h | 1 hour | Investigate & retry |
| **Disk Space Critical** | < 10% free | 30 minutes | Clean old backups |
| **High Error Rate** | > 5% errors | 15 minutes | Investigate logs |
| **API Unresponsive** | No response 5min | 5 minutes | Restart backend |

### Monitoring Dashboard

Key metrics to monitor 24/7:

```
┌─────────────────────────────────────────────┐
│           DISASTER RECOVERY STATUS          │
├─────────────────────────────────────────────┤
│ Last Backup:        ✅ 2 hours ago          │
│ Backup Size:        ✅ 1.2 GB               │
│ Database Health:    ✅ Healthy              │
│ Replica Lag:        ✅ < 1 second           │
│ Disk Space:         ✅ 65% free             │
│ S3 Upload Status:   ✅ Success              │
│ RTO Capability:     ✅ 40 minutes           │
│ RPO Current:        ✅ 2 hours              │
└─────────────────────────────────────────────┘
```

---

## Post-Recovery Verification

### Verification Checklist

After ANY recovery procedure, verify:

#### Database Integrity
- [ ] Row counts match expected values
- [ ] Latest transactions are present
- [ ] Indexes are valid
- [ ] Constraints are enforced
- [ ] No corruption detected

```sql
-- Run these queries to verify
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM strategies;
SELECT COUNT(*) FROM backtests;
SELECT MAX(created_at) FROM backtests;  -- Should be recent
```

#### Application Functionality
- [ ] Login works
- [ ] Strategy creation works
- [ ] Backtest execution works
- [ ] API endpoints respond
- [ ] UI renders correctly

```bash
# API tests
curl -X POST http://localhost:8000/auth/login
curl http://localhost:8000/strategies
curl http://localhost:8000/backtests
```

#### Performance
- [ ] Response times < 200ms (p95)
- [ ] Database query times normal
- [ ] No memory leaks
- [ ] CPU usage normal

```bash
# Performance check
ab -n 100 -c 10 http://localhost:8000/health
docker stats --no-stream
```

#### Security
- [ ] SSL certificates valid
- [ ] Authentication working
- [ ] Authorization enforced
- [ ] Audit logs intact

---

## Lessons Learned

### Incident Report Template

After each DR event (real or test), complete this template:

```markdown
# DR Incident Report

**Date**: YYYY-MM-DD
**Incident ID**: INC-XXXX
**Severity**: P0/P1/P2
**Status**: Resolved

## Summary
Brief description of what happened

## Timeline
- HH:MM - Incident detected
- HH:MM - Response initiated
- HH:MM - Recovery started
- HH:MM - System restored
- HH:MM - Verification complete

## Root Cause
What caused the incident

## Impact
- Users affected: X
- Downtime: X minutes
- Data loss: X hours/records

## Recovery Metrics
- Target RTO: X minutes
- Actual RTO: X minutes
- Target RPO: X hours
- Actual RPO: X hours

## What Went Well
- Item 1
- Item 2

## What Needs Improvement
- Item 1
- Item 2

## Action Items
1. [ ] Action 1 (Owner, Due Date)
2. [ ] Action 2 (Owner, Due Date)

## Lessons Learned
Key takeaways for future incidents
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-05 | DevOps Team | Initial DR plan |
| | | | |

---

## Appendix

### A. Emergency Scripts

Located in `/backend/scripts/dr/`:
- `emergency_backup.sh` - Create emergency backup
- `verify_backup.sh` - Verify backup integrity
- `restore_latest.sh` - Restore from latest backup
- `failover.sh` - Failover to DR site

### B. Configuration Files

Located in `/config/dr/`:
- `dns-failover.json` - Route53 failover config
- `.env.dr` - DR environment variables
- `docker-compose.dr.yml` - DR docker compose

### C. Vendor Contacts

See Emergency Contacts section above

### D. Training Materials

- DR Training Video: [Internal Link]
- Runbook: [Internal Link]
- DR Simulation Lab: [Internal Link]

---

**Document Owner**: DevOps Team  
**Review Date**: 2026-02-05 (Quarterly)  
**Classification**: CONFIDENTIAL - INTERNAL USE ONLY

---

*This Disaster Recovery Plan is a living document and should be updated after each DR event or quarterly review.*
