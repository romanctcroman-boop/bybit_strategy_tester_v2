# Docker Compose Setup Guide

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available for containers

### Environment Setup

1. Copy example environment file:
```bash
cp .env.example .env
```

2. Configure required variables in `.env`:
```env
# Database
DB_PASSWORD=your_secure_password_here

# Redis
REDIS_PASSWORD=your_redis_password_here

# Grafana
GRAFANA_PASSWORD=admin_password_here

# API Keys (optional for backtesting)
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
```

### Starting Services

#### Development (all services):
```bash
docker-compose up -d
```

#### Production (optimized):
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### Testing only:
```bash
docker-compose -f docker-compose.test.yml up -d
```

#### PostgreSQL only:
```bash
docker-compose -f docker-compose.postgres.yml up -d
```

#### Redis Cluster:
```bash
docker-compose -f docker-compose.redis-cluster.yml up -d
```

### Checking Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mcp-server
docker-compose logs -f postgres
```

### Accessing Services

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Backend API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Grafana | http://localhost:3000 | admin / (from .env) |
| Prometheus | http://localhost:9090 | - |
| PostgreSQL | localhost:5432 | mcp_user / (from .env) |
| Redis | localhost:6379 | - / (from .env) |

### Running Migrations

```bash
# Run migrations inside backend container
docker-compose exec mcp-server alembic upgrade head

# Or from host (if alembic installed locally)
docker-compose up -d postgres
alembic upgrade head
```

### Running Tests in Docker

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run tests
docker-compose -f docker-compose.test.yml exec backend pytest tests/ -v

# Run with coverage
docker-compose -f docker-compose.test.yml exec backend pytest tests/ --cov=backend --cov-report=html
```

### Stopping Services

```bash
# Stop all services (preserves data)
docker-compose down

# Stop and remove volumes (deletes data)
docker-compose down -v

# Stop specific service
docker-compose stop mcp-server
```

### Scaling Services

```bash
# Scale backend service to 3 replicas
docker-compose up -d --scale mcp-server=3

# Note: Requires load balancer configuration
```

## Service Details

### mcp-server (Backend API)
- **Image**: Built from Dockerfile
- **Port**: 8000
- **Dependencies**: postgres, redis
- **Health Check**: `python deployment/health_check.py` every 30s
- **Resources**: 
  - Limit: 512MB RAM, 1 CPU
  - Reservation: 256MB RAM, 0.5 CPU

### postgres (Database)
- **Image**: postgres:15-alpine
- **Port**: 5432
- **Volume**: `postgres_data` (persistent)
- **Init Script**: `deployment/init-db.sql`
- **Resources**:
  - Limit: 256MB RAM, 0.5 CPU

### redis (Cache)
- **Image**: redis:7-alpine
- **Port**: 6379
- **Volume**: `redis_data` (persistent with AOF)
- **Resources**:
  - Limit: 128MB RAM, 0.25 CPU

### prometheus (Metrics)
- **Image**: prom/prometheus:latest
- **Port**: 9090
- **Volume**: `prometheus_data` (persistent)
- **Retention**: 200 hours
- **Config**: `monitoring/prometheus.yml`

### grafana (Dashboards)
- **Image**: grafana/grafana:latest
- **Port**: 3000
- **Volume**: `grafana_data` (persistent)
- **Dashboards**: Auto-provisioned from `monitoring/dashboards/`

## Volumes

Persistent data volumes:
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis AOF persistence
- `prometheus_data`: Prometheus time-series data
- `grafana_data`: Grafana dashboards and settings

### Backup Volumes

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U mcp_user mcp_db > backup_$(date +%Y%m%d).sql

# Backup Redis
docker-compose exec redis redis-cli --rdb /data/backup.rdb

# Copy volumes
docker run --rm -v postgres_data:/source -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /source
```

### Restore Volumes

```bash
# Restore PostgreSQL
docker-compose exec -T postgres psql -U mcp_user mcp_db < backup_20241114.sql

# Restore Redis
docker-compose stop redis
docker run --rm -v redis_data:/target -v $(pwd):/backup alpine tar xzf /backup/redis_backup.tar.gz -C /target
docker-compose start redis
```

## Networking

All services run on the `mcp-network` bridge network, allowing inter-service communication:

```bash
# Services can reach each other by name:
# - postgres:5432
# - redis:6379
# - mcp-server:8000
# - prometheus:9090
# - grafana:3000
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs mcp-server

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart mcp-server
```

### Database connection issues

```bash
# Check postgres is ready
docker-compose exec postgres pg_isready -U mcp_user

# Test connection
docker-compose exec mcp-server psql $DATABASE_URL
```

### Redis connection issues

```bash
# Check redis is running
docker-compose exec redis redis-cli ping

# If password protected
docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping
```

### Out of memory errors

```bash
# Check resource usage
docker stats

# Increase memory limits in docker-compose.yml
# Or adjust Docker Desktop settings
```

### Port conflicts

```bash
# Change ports in docker-compose.yml:
ports:
  - "8001:8000"  # Map to different host port
```

## Development Workflow

1. **Start dependencies only**:
```bash
docker-compose up -d postgres redis
```

2. **Run backend locally** (for development):
```bash
uvicorn backend.api.app:app --reload
```

3. **Run tests**:
```bash
pytest tests/ -v
```

4. **Stop dependencies**:
```bash
docker-compose down
```

## Production Considerations

### Security

1. **Use secrets management**:
```bash
# Instead of .env file, use Docker secrets
docker secret create db_password ./secrets/db_password.txt
```

2. **Enable TLS**:
- Use reverse proxy (nginx/traefik) for HTTPS
- Configure SSL certificates

3. **Limit exposure**:
- Don't expose PostgreSQL/Redis to public internet
- Use firewall rules

### Monitoring

1. **Enable Prometheus metrics**:
- Backend exposes `/metrics` endpoint
- Configured in `monitoring/prometheus.yml`

2. **Set up Grafana dashboards**:
- Import pre-configured dashboards from `monitoring/dashboards/`
- Create alerts for critical metrics

3. **Log aggregation**:
```bash
# Use log driver for centralized logging
docker-compose logs --follow | tee application.log
```

### High Availability

For production HA setup:

1. **Database replication**: Use PostgreSQL streaming replication
2. **Redis cluster**: Use `docker-compose.redis-cluster.yml`
3. **Load balancer**: Add nginx/traefik for backend replicas
4. **Health checks**: Monitor all services with external tool

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml`:
```yaml
postgres:
  command: postgres -c shared_buffers=256MB -c max_connections=200
```

### Redis

Edit `docker-compose.yml`:
```yaml
redis:
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### Backend

Scale horizontally:
```bash
docker-compose up -d --scale mcp-server=4
```

## Cleanup

### Remove all containers and volumes:
```bash
docker-compose down -v --remove-orphans
```

### Remove all images:
```bash
docker-compose down --rmi all
```

### Prune Docker system:
```bash
docker system prune -a --volumes
```

## Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
