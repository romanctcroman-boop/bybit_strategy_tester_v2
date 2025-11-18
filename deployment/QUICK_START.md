# 🚀 Quick Deployment Guide - 5 Minutes to Production

## Prerequisites Check

```powershell
# Check Docker
docker --version
# Expected: Docker version 20.10+

# Check Docker Compose
docker-compose --version
# Expected: Docker Compose version 2.0+

# Check Python
python --version
# Expected: Python 3.11+
```

## One-Command Deployment

```powershell
# Navigate to project directory
cd d:\bybit_strategy_tester_v2

# Run deployment (4 workers, all Phase 1 features)
D:\.venv\Scripts\python.exe deployment/production_deploy.py --workers 4
```

## What Gets Deployed

### Services
- ✅ **Backend API** (FastAPI with JWT auth) → `localhost:8000`
- ✅ **Celery Workers** (4 workers, auto-scaling 2-4) → Background
- ✅ **PostgreSQL** (Database) → `localhost:5432`
- ✅ **Redis** (Cache & Queue) → `localhost:6379`
- ✅ **Prometheus** (Metrics) → `localhost:9090`
- ✅ **Grafana** (Dashboards) → `localhost:3000`

### Phase 1 Features
- ✅ **Sandbox Isolation**: Docker containers for code execution
- ✅ **JWT Authentication**: RS256 tokens, 30min expiry
- ✅ **RBAC Authorization**: Admin/User/Guest roles
- ✅ **Rate Limiting**: 100 req/min per user
- ✅ **Secure Logging**: 8 sensitive patterns filtered
- ✅ **Horizontal Scaling**: 2-4 workers (dynamic)

## Deployment Steps (Automated)

The script performs these steps automatically:

1. ✅ **Check Prerequisites** (Docker, Redis, PostgreSQL)
2. ✅ **Create .env.production** (with secure secrets)
3. ✅ **Create docker-compose.production.yml**
4. ✅ **Create Dockerfiles** (Backend, Celery)
5. ✅ **Build Docker Images** (~5 min)
6. ✅ **Start Services** (Docker Compose up)
7. ✅ **Run Database Migrations** (Alembic)
8. ✅ **Verify Deployment** (Health checks)

**Total Time**: ~10 minutes (mostly Docker build)

## Post-Deployment

### 1. Verify Services

```powershell
# Check all services are running
docker-compose -f docker-compose.production.yml ps

# Expected output:
# NAME                STATUS              PORTS
# backend             Up 30 seconds       0.0.0.0:8000->8000/tcp
# celery-worker       Up 30 seconds
# postgres            Up 30 seconds       0.0.0.0:5432->5432/tcp
# redis               Up 30 seconds       0.0.0.0:6379->6379/tcp
# prometheus          Up 30 seconds       0.0.0.0:9090->9090/tcp
# grafana             Up 30 seconds       0.0.0.0:3000->3000/tcp
```

### 2. Test API

```powershell
# Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", "timestamp": "..."}

# API docs
Start-Process http://localhost:8000/docs
```

### 3. Update API Keys

Edit `.env.production`:

```bash
# Replace these with your actual keys
BYBIT_API_KEY=your_real_key_here
BYBIT_API_SECRET=your_real_secret_here
DEEPSEEK_API_KEY=your_real_key_here
PERPLEXITY_API_KEY=your_real_key_here
```

Then restart:

```powershell
docker-compose -f docker-compose.production.yml restart backend
```

## Access Dashboards

- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Prometheus Metrics**: http://localhost:9090
- **Grafana Dashboards**: http://localhost:3000
  - Username: `admin`
  - Password: Check `.env.production`

## Common Commands

### View Logs

```powershell
# All services
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f backend
docker-compose -f docker-compose.production.yml logs -f celery-worker
```

### Restart Services

```powershell
# Restart all
docker-compose -f docker-compose.production.yml restart

# Restart specific
docker-compose -f docker-compose.production.yml restart backend
```

### Stop Services

```powershell
# Stop all
docker-compose -f docker-compose.production.yml stop

# Stop specific
docker-compose -f docker-compose.production.yml stop backend
```

### Scale Workers

```powershell
# Scale to 8 workers
docker-compose -f docker-compose.production.yml scale celery-worker=8

# Scale to 2 workers
docker-compose -f docker-compose.production.yml scale celery-worker=2
```

## Monitoring

### Metrics Endpoints

```powershell
# Backend metrics
curl http://localhost:8000/metrics

# Key metrics to watch:
# - jwt_tokens_issued_total
# - rate_limit_exceeded_total
# - sandbox_executions_total
# - celery_workers_active
# - celery_queue_depth
```

### View Grafana Dashboard

1. Open http://localhost:3000
2. Login (admin/admin)
3. Navigate to "Phase 1 Security & Scaling Dashboard"
4. See real-time metrics

## Troubleshooting

### Service Won't Start

```powershell
# Check logs
docker-compose -f docker-compose.production.yml logs backend

# Check if port is already in use
netstat -ano | findstr :8000

# Kill process using port
taskkill /PID <PID> /F
```

### Database Connection Error

```powershell
# Check PostgreSQL status
docker-compose -f docker-compose.production.yml ps postgres

# Check PostgreSQL logs
docker-compose -f docker-compose.production.yml logs postgres

# Restart PostgreSQL
docker-compose -f docker-compose.production.yml restart postgres
```

### Redis Connection Error

```powershell
# Check Redis status
docker-compose -f docker-compose.production.yml ps redis

# Test Redis connection
docker exec -it bybit_strategy_redis redis-cli ping
```

## Security Checklist

Before going to production:

- [ ] Update all API keys in `.env.production`
- [ ] Set strong passwords (DB, Redis, Grafana)
- [ ] Secure `MASTER_ENCRYPTION_KEY`
- [ ] Review `JWT_SECRET_KEY`
- [ ] Configure firewall rules
- [ ] Enable HTTPS/TLS
- [ ] Set up backup schedule
- [ ] Configure monitoring alerts

## Next Steps

After deployment:

1. **Monitor Metrics**: Check Prometheus/Grafana
2. **Test Endpoints**: Use API docs at `/docs`
3. **Scale Workers**: Adjust based on load
4. **Review Logs**: Check for errors/warnings
5. **Plan Phase 2**: Advanced features (optional)

## Rollback

If something goes wrong:

```powershell
# Stop all services
docker-compose -f docker-compose.production.yml down

# Remove volumes (optional, data loss!)
docker-compose -f docker-compose.production.yml down -v

# Check previous deployment
git log --oneline
git checkout <previous-commit>
```

## Support

- **Documentation**: `deployment/README.md`
- **Phase 1 Summary**: `PHASE_1_COMPLETE_FINAL_SUMMARY.md`
- **Issues**: GitHub Issues

---

**🎉 Ready to Deploy! 🎉**

Run the deployment command above and you'll have a production-ready system in ~10 minutes!
