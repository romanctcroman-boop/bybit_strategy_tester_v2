# Quick Reference Card

## 🚀 Production Deployment Cheat Sheet

### Essential Commands

```powershell
# ============================================
# Pre-Deployment
# ============================================

# Check everything is ready
.\scripts\deploy.ps1 -Action preflight

# One-time setup (monitoring + app)
.\scripts\deploy.ps1 -Action deploy


# ============================================
# Day-to-Day Operations
# ============================================

# Check system status
.\scripts\deploy.ps1 -Action status

# Restart everything
.\scripts\deploy.ps1 -Action restart

# Start services
.\scripts\deploy.ps1 -Action start

# Stop services
.\scripts\deploy.ps1 -Action stop


# ============================================
# Monitoring & Logs
# ============================================

# Tail JSON logs in real-time
Get-Content logs/app.json.log -Tail 1 -Wait

# Search for errors
Select-String "ERROR" logs/*.json.log

# View recent 100 lines
Get-Content logs/app.json.log -Tail 100

# Docker container status
docker ps

# Redis connection test
redis-cli ping

# All Docker services
docker-compose -f deployment/docker-compose-monitoring.yml ps
```

### Dashboard URLs

| Service | URL | User/Pass |
|---------|-----|-----------|
| API | http://localhost:8000 | - |
| Grafana | http://localhost:3000 | admin/changeme |
| Kibana | http://localhost:5601 | elastic/changeme |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |

### Common Issues & Fixes

```powershell
# API not responding
curl http://localhost:8000/healthz

# Redis not working
docker exec redis-prod redis-cli ping

# View Docker logs
docker-compose -f deployment/docker-compose-monitoring.yml logs -f prometheus

# Restart Prometheus
docker-compose -f deployment/docker-compose-monitoring.yml restart prometheus

# Check Redis memory
redis-cli INFO memory | grep used_memory_human
```

### Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| .env.production | All settings | root |
| prometheus.yml | Metrics config | deployment/config/ |
| alert-rules.yml | Alert definitions | deployment/config/ |
| alertmanager.yml | Alert routing | deployment/config/ |
| redis.conf | Redis config | deployment/config/ |
| docker-compose-monitoring.yml | Stack setup | deployment/ |

### Important Environment Variables

```env
# Critical settings
ENVIRONMENT=production
REDIS_ENABLED=1
MCP_DISABLED=1           # Keep this 1 for now

# Update these:
DEEPSEEK_API_KEY=your_key
PERPLEXITY_API_KEY=your_key
SLACK_WEBHOOK_URL=your_webhook
```

### Health Check URLs

```
http://localhost:8000/healthz        # API health
http://localhost:8000/metrics        # Prometheus metrics
http://localhost:9090/-/healthy      # Prometheus
http://localhost:3000/api/health     # Grafana
http://localhost:5601/api/status     # Kibana
http://localhost:9093/-/healthy      # Alertmanager
```

### Log Files

```
logs/app.json.log              # Main application (JSON)
logs/ai_agent_service.json.log # AI Agent (JSON)
logs/api.json.log              # API endpoints (JSON)
logs/uvicorn.out.log           # Uvicorn server logs
```

### Redis Commands

```bash
# Check connection
redis-cli -u redis://default:password@localhost:6379/0 ping

# View keys
redis-cli KEYS "*"

# Check memory usage
redis-cli INFO memory

# Clear cache (danger!)
redis-cli FLUSHDB

# View specific database
redis-cli -n 1 DBSIZE
```

### Docker Compose Operations

```bash
# Start all services
docker-compose -f deployment/docker-compose-monitoring.yml up -d

# Stop all services
docker-compose -f deployment/docker-compose-monitoring.yml down

# View logs
docker-compose -f deployment/docker-compose-monitoring.yml logs -f

# Restart service
docker-compose -f deployment/docker-compose-monitoring.yml restart elasticsearch

# Remove volumes (dangerous!)
docker-compose -f deployment/docker-compose-monitoring.yml down -v
```

### Performance Metrics to Watch

| Metric | Alert Threshold | Dashboard |
|--------|-----------------|-----------|
| CPU Usage | > 80% | System Overview |
| Memory | > 80% | System Overview |
| Disk | > 80% | System Overview |
| API Latency (p95) | > 1s | API Performance |
| API Error Rate | > 5% | API Performance |
| Cache Hit Rate | < 50% | Cache Performance |

### Alert Channels Setup

```env
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_ALERT_CHANNEL=#alerts

# PagerDuty
PAGERDUTY_SERVICE_KEY=your_service_key

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

### Quick Debugging

```powershell
# Is the app running?
Get-Process | Where-Object { $_.ProcessName -match "python" }

# Are containers up?
docker ps

# What's using port 8000?
netstat -ano | findstr :8000

# Python environment check
python -c "import backend; print('OK')"

# Verify Redis
python -c "import redis; r = redis.Redis(); print(r.ping())"
```

### Backup Important Configs

```powershell
# Before making changes
Copy-Item .env.production .env.production.backup
Copy-Item deployment/config/*.yml deployment/config/*.bak
```

### Deployment Workflow

```
1. .\scripts\deploy.ps1 -Action preflight
   ↓ Check all requirements
2. .\scripts\deploy.ps1 -Action deploy
   ↓ Start monitoring + app
3. .\scripts\deploy.ps1 -Action status
   ↓ Verify health checks
4. Update .env.production with real credentials
5. Monitor logs and dashboards
```

### Regular Maintenance

```powershell
# Daily
Get-Content logs/app.json.log -Tail 100          # Check for errors
.\scripts\deploy.ps1 -Action status              # Health check

# Weekly
Select-String "ERROR" logs/*.json.log            # Error review
docker system prune -a                           # Cleanup Docker
redis-cli --stat                                 # Redis check

# Monthly
Backup all config files
Review Grafana dashboards
Check alert rules effectiveness
Update dependencies
```

---

**Last Updated**: 2025-12-04  
**Version**: 1.0.0

