# 🚀 Production Deployment Guide

## Prerequisites

- Docker 20.10+ and Docker Compose v2+
- 4GB+ RAM available
- 20GB+ disk space
- Domain name (optional, for HTTPS)

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/RomanCTC/bybit_strategy_tester_v2.git
cd bybit_strategy_tester_v2

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env  # or use your favorite editor
```

### 2. Required Environment Variables

**CRITICAL - Must be set:**

```bash
# API Keys (REQUIRED)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here

# Database Password (CHANGE DEFAULT!)
POSTGRES_PASSWORD=your_secure_password_here

# Security Keys (GENERATE SECURE KEYS!)
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)

# Grafana Admin Password
GRAFANA_PASSWORD=your_grafana_admin_password
```

### 3. Deploy

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Access Services

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/your_password)
- **Prometheus**: http://localhost:9090

---

## Architecture

```
┌─────────────────┐
│   Internet      │
└────────┬────────┘
         │
    ┌────▼─────┐
    │  Nginx   │  ← Frontend (React SPA)
    │  :3001   │
    └────┬─────┘
         │
    ┌────▼────────────────┐
    │  FastAPI Backend    │
    │     :8000           │
    └────┬────────────┬───┘
         │            │
    ┌────▼────┐  ┌───▼────┐
    │ PostgreSQL│ │ Redis  │
    │   :5432   │ │ :6379  │
    └───────────┘ └────────┘
         │
    ┌────▼─────────────────┐
    │  Monitoring Stack    │
    │  Prometheus + Grafana│
    └──────────────────────┘
```

---

## Services

### 1. PostgreSQL Database
- **Image**: postgres:15-alpine
- **Port**: 5432
- **Volume**: postgres-data (persistent)
- **Health check**: pg_isready

### 2. Redis Cache
- **Image**: redis:7-alpine
- **Port**: 6379
- **Volume**: redis-data (persistent with AOF)
- **Health check**: redis-cli ping

### 3. Backend API
- **Build**: ./Dockerfile
- **Port**: 8000
- **Health check**: /health endpoint
- **Resources**: 2 CPU, 2GB RAM limit

### 4. Frontend Web App
- **Build**: ./frontend/Dockerfile
- **Port**: 3001 → 80 (Nginx)
- **Health check**: HTTP GET /
- **Resources**: 0.5 CPU, 512MB RAM limit

### 5. Prometheus (Monitoring)
- **Image**: prom/prometheus:latest
- **Port**: 9090
- **Volume**: prometheus-data (30 days retention)
- **Scrapes**: Backend /metrics endpoint

### 6. Grafana (Dashboards)
- **Image**: grafana/grafana:latest
- **Port**: 3000
- **Volume**: grafana-data (persistent)
- **Default user**: admin/admin

### 7. AlertManager (Alerts)
- **Image**: prom/alertmanager:latest
- **Port**: 9093
- **Volume**: alertmanager-data

---

## Security Checklist

### ✅ Before Production

- [ ] Change default PostgreSQL password
- [ ] Generate secure SECRET_KEY and JWT_SECRET_KEY
- [ ] Set strong Grafana admin password
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Enable HTTPS (use reverse proxy like Traefik/Caddy)
- [ ] Set up firewall rules (only expose necessary ports)
- [ ] Configure rate limiting
- [ ] Enable authentication for all services
- [ ] Set up SSL certificates (Let's Encrypt)
- [ ] Configure backup strategy
- [ ] Set up log rotation
- [ ] Review and update security headers in nginx.conf

### 🔒 Recommended Security Practices

```bash
# 1. Use Docker secrets for sensitive data
echo "your_secret_password" | docker secret create postgres_password -

# 2. Run containers with non-root users (already configured)

# 3. Limit resource usage (already configured in docker-compose.prod.yml)

# 4. Use private networks (already configured)

# 5. Regular security updates
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

---

## Monitoring & Health Checks

### Health Check Endpoints

```bash
# Backend API
curl http://localhost:8000/health
# Expected: {"status": "healthy", "checks": {...}}

# Frontend
curl http://localhost:3001/health
# Expected: healthy

# PostgreSQL
docker exec bybit-postgres pg_isready -U postgres

# Redis
docker exec bybit-redis redis-cli ping
# Expected: PONG
```

### Prometheus Targets

Access http://localhost:9090/targets to see all monitored services.

### Grafana Dashboards

1. Login to http://localhost:3000
2. Navigate to Dashboards
3. Import pre-configured dashboards from `monitoring/grafana/dashboards/`

**Available Dashboards:**
- Backend API Performance
- Database Metrics
- Redis Cache Stats
- Backtest Execution Metrics
- System Resources

---

## Backup & Restore

### Automated Backups

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="./backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# PostgreSQL backup
docker exec bybit-postgres pg_dump -U postgres bybit_tester > $BACKUP_DIR/postgres.sql

# Redis backup
docker exec bybit-redis redis-cli SAVE
docker cp bybit-redis:/data/dump.rdb $BACKUP_DIR/redis.rdb

echo "Backup completed: $BACKUP_DIR"
EOF

chmod +x backup.sh

# Run backup
./backup.sh

# Schedule daily backups (cron)
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/backup.sh") | crontab -
```

### Restore from Backup

```bash
# PostgreSQL restore
cat backups/20250109/postgres.sql | docker exec -i bybit-postgres psql -U postgres bybit_tester

# Redis restore
docker cp backups/20250109/redis.rdb bybit-redis:/data/dump.rdb
docker-compose -f docker-compose.prod.yml restart redis
```

---

## Scaling

### Horizontal Scaling (Multiple API Instances)

```yaml
# docker-compose.prod.yml
services:
  api:
    # ... existing config
    deploy:
      replicas: 3  # Run 3 instances

  # Add load balancer
  nginx-lb:
    image: nginx:alpine
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    ports:
      - "8080:80"
    depends_on:
      - api
```

### Vertical Scaling (Increase Resources)

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4'        # Increase to 4 CPUs
          memory: 4G       # Increase to 4GB RAM
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Check container status
docker-compose -f docker-compose.prod.yml ps

# Restart specific service
docker-compose -f docker-compose.prod.yml restart api
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker exec bybit-postgres pg_isready

# Check connection from API container
docker exec bybit-api psql -h postgres -U postgres -d bybit_tester -c "SELECT 1"

# Verify DATABASE_URL environment variable
docker exec bybit-api env | grep DATABASE_URL
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# Reduce PostgreSQL shared_buffers
# Edit docker-compose.prod.yml:
services:
  postgres:
    command: postgres -c shared_buffers=256MB -c max_connections=100
```

### Performance Issues

```bash
# Check backend metrics
curl http://localhost:8000/metrics

# View slow queries in PostgreSQL
docker exec bybit-postgres psql -U postgres -d bybit_tester -c "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;"

# Check Redis memory usage
docker exec bybit-redis redis-cli INFO memory
```

---

## Maintenance

### Update Application

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations (if needed)
docker exec bybit-api alembic upgrade head
```

### Database Migrations

```bash
# Run migrations
docker exec bybit-api alembic upgrade head

# Rollback migration
docker exec bybit-api alembic downgrade -1

# Check current version
docker exec bybit-api alembic current
```

### Clean Up

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove stopped containers
docker container prune

# Clean up logs (older than 7 days)
find ./logs -name "*.log" -mtime +7 -delete
```

---

## Production Checklist

### Infrastructure
- [ ] Set up HTTPS/SSL certificates
- [ ] Configure domain name and DNS
- [ ] Set up firewall rules
- [ ] Configure log aggregation (ELK/Loki)
- [ ] Set up automated backups
- [ ] Configure monitoring alerts
- [ ] Set up CDN for static assets (optional)

### Application
- [ ] All environment variables configured
- [ ] Database migrations applied
- [ ] API keys configured and tested
- [ ] Rate limiting configured
- [ ] CORS origins configured
- [ ] Error tracking setup (Sentry)
- [ ] Performance monitoring setup

### Security
- [ ] Change all default passwords
- [ ] Enable authentication
- [ ] Configure HTTPS only
- [ ] Set up security headers
- [ ] Enable request validation
- [ ] Configure session management
- [ ] Set up IP whitelisting (if needed)

### Monitoring
- [ ] Prometheus scraping configured
- [ ] Grafana dashboards imported
- [ ] Alert rules configured
- [ ] Log aggregation working
- [ ] Health checks passing
- [ ] Metrics endpoints accessible

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/RomanCTC/bybit_strategy_tester_v2/issues
- Documentation: See project README.md
- Logs: `docker-compose -f docker-compose.prod.yml logs -f`

---

**Last Updated:** 2025-11-09  
**Version:** 2.0  
**Author:** GitHub Copilot + DeepSeek Agent
