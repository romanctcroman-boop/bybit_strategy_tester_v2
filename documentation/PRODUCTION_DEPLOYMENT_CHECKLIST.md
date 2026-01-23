# Production Deployment Checklist

## Bybit Strategy Tester v2 - Phase 7 Deployment

**Version:** 2.0.0  
**Last Updated:** December 2025  
**Author:** RomanCTC

---

## 📋 Pre-Deployment Checklist

### 1. Infrastructure Requirements

- [ ] **Kubernetes Cluster**
  - [ ] Minimum 3 nodes (for HA)
  - [ ] At least 4 CPU cores per node
  - [ ] At least 8GB RAM per node
  - [ ] Network policies enabled
  - [ ] Storage class configured

- [ ] **External Services**
  - [ ] PostgreSQL 15+ (managed or self-hosted)
  - [ ] Redis 7+ (managed or self-hosted)
  - [ ] DNS configured for your domain
  - [ ] SSL certificates (Let's Encrypt or custom)

- [ ] **Monitoring Stack**
  - [ ] Prometheus operator installed
  - [ ] Grafana deployed
  - [ ] AlertManager configured
  - [ ] PagerDuty/Slack integration set up

### 2. Security Checklist

- [ ] **Secrets Management**
  - [ ] All passwords changed from defaults
  - [ ] Secrets stored in Vault/AWS Secrets Manager/K8s Secrets
  - [ ] API keys encrypted at rest
  - [ ] JWT secrets rotated

- [ ] **Network Security**
  - [ ] TLS enabled for all endpoints
  - [ ] Network policies applied
  - [ ] Firewall rules configured
  - [ ] Rate limiting enabled

- [ ] **Application Security**
  - [ ] CORS configured properly
  - [ ] Security headers enabled
  - [ ] Input validation in place
  - [ ] SQL injection protection verified

### 3. Configuration Review

- [ ] **Environment Variables**

  ```bash
  # Required
  DATABASE_URL=postgresql://user:pass@host:5432/db
  REDIS_URL=redis://:password@host:6379/0
  SECRET_KEY=<generated-secret>
  JWT_SECRET_KEY=<generated-secret>
  
  # API Keys
  BYBIT_API_KEY=<your-key>
  BYBIT_API_SECRET=<your-secret>
  DEEPSEEK_API_KEY=<your-key>
  PERPLEXITY_API_KEY=<your-key>
  
  # Circuit Breaker
  CIRCUIT_BREAKER_THRESHOLD=5
  CIRCUIT_BREAKER_RECOVERY=30
  ```

- [ ] **Resource Limits Verified**
  - Backend: 2 CPU, 2GB Memory
  - Celery Worker: 1 CPU, 1GB Memory
  - Celery Beat: 0.5 CPU, 512MB Memory

---

## 🚀 Deployment Steps

### Option A: Docker Compose (Single Server)

```bash
# 1. Clone repository
git clone https://github.com/your-org/bybit-strategy-tester.git
cd bybit-strategy-tester

# 2. Configure environment
cp .env.example .env
# Edit .env with your values

# 3. Generate secrets
openssl rand -hex 32  # For SECRET_KEY
openssl rand -hex 32  # For JWT_SECRET_KEY

# 4. Deploy
docker-compose -f deployment/docker-compose-prod.yml up -d

# 5. Run migrations
docker-compose -f deployment/docker-compose-prod.yml exec backend python main.py migrate

# 6. Verify health
curl http://localhost:8000/health
```

### Option B: Kubernetes with Helm

```bash
# 1. Add Helm dependencies
cd helm/bybit-strategy-tester
helm dependency update

# 2. Create namespace
kubectl create namespace bybit-prod

# 3. Create secrets (from external secret manager or manually)
kubectl create secret generic bybit-secrets \
  --from-literal=DB_USER=bybit_user \
  --from-literal=DB_PASS=<password> \
  --from-literal=SECRET_KEY=<secret> \
  --from-literal=JWT_SECRET_KEY=<jwt-secret> \
  --from-literal=REDIS_PASSWORD=<redis-pass> \
  --from-literal=BYBIT_API_KEY=<api-key> \
  --from-literal=BYBIT_API_SECRET=<api-secret> \
  --from-literal=PERPLEXITY_API_KEY=<perplexity-key> \
  --from-literal=DEEPSEEK_API_KEY=<deepseek-key> \
  -n bybit-prod

# 4. Install chart
helm install bybit-strategy-tester ./helm/bybit-strategy-tester \
  --namespace bybit-prod \
  --set secrets.create=false \
  --set ingress.hosts[0].host=api.yourdomain.com \
  --values helm/bybit-strategy-tester/values-prod.yaml

# 5. Verify deployment
kubectl get pods -n bybit-prod
kubectl get svc -n bybit-prod
kubectl get ingress -n bybit-prod

# 6. Check logs
kubectl logs -f deployment/bybit-strategy-tester-backend -n bybit-prod
```

### Option C: Kustomize

```bash
# 1. Customize for your environment
cd k8s
cp kustomization.yaml kustomization-prod.yaml
# Edit kustomization-prod.yaml

# 2. Preview
kubectl kustomize .

# 3. Apply
kubectl apply -k .

# 4. Verify
kubectl get all -n bybit-strategy-tester
```

---

## ✅ Post-Deployment Verification

### 1. Health Checks

```bash
# API Health
curl -s https://api.yourdomain.com/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "components": {
#     "database": "healthy",
#     "redis": "healthy",
#     "ai_agents": "healthy"
#   }
# }
```

### 2. Monitoring Verification

- [ ] Prometheus scraping metrics from `/metrics`
- [ ] Grafana dashboards loading data:
  - System Health Dashboard
  - API Performance Dashboard
  - Circuit Breaker Dashboard
  - AI Latency Dashboard
- [ ] AlertManager receiving alerts

### 3. Functional Tests

```bash
# Test API endpoints
curl -X GET https://api.yourdomain.com/api/v1/strategies
curl -X GET https://api.yourdomain.com/api/v1/backtest/status

# Test WebSocket
wscat -c wss://api.yourdomain.com/ws/updates

# Test AI endpoints (requires auth)
curl -X POST https://api.yourdomain.com/api/v1/ai/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a simple SMA crossover strategy"}'
```

### 4. Circuit Breaker Verification

```bash
# Check circuit breaker status
curl https://api.yourdomain.com/api/v1/monitoring/circuit-breakers

# Expected: All breakers in CLOSED state
```

---

## 📊 Monitoring & Alerting

### Key Metrics to Watch

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| API Error Rate | > 1% | > 5% | Check logs, restart pods |
| Response Latency (p95) | > 500ms | > 2s | Scale up, optimize queries |
| Circuit Breaker Open | N/A | Any open | Investigate service |
| Memory Usage | > 70% | > 90% | Scale up memory |
| CPU Usage | > 70% | > 90% | Scale up replicas |
| Fallback Rate | > 10% | > 30% | Fix underlying service |

### Alert Response Runbook

1. **CircuitBreakerOpen**
   - Check service logs: `kubectl logs -l app=<service>`
   - Check external service status
   - Try manual reset if appropriate
   - Escalate if persists > 10 minutes

2. **HighAPIErrorRate**
   - Check recent deployments
   - Review error logs
   - Check database connections
   - Roll back if necessary

3. **DegradedModeActive**
   - System is using fallbacks
   - Monitor for recovery
   - Check underlying services
   - Plan maintenance window if needed

---

## 🔄 Rollback Procedure

### Quick Rollback (Helm)

```bash
# List releases
helm history bybit-strategy-tester -n bybit-prod

# Rollback to previous
helm rollback bybit-strategy-tester -n bybit-prod

# Rollback to specific revision
helm rollback bybit-strategy-tester 3 -n bybit-prod
```

### Quick Rollback (Docker Compose)

```bash
# Pull previous version
docker pull ghcr.io/your-org/bybit-strategy-tester:v1.9.0

# Update docker-compose.yml with previous tag
# Restart
docker-compose -f deployment/docker-compose-prod.yml up -d
```

---

## 📝 Maintenance Tasks

### Daily

- [ ] Check Grafana dashboards
- [ ] Review AlertManager notifications
- [ ] Verify backup completion

### Weekly

- [ ] Review error logs
- [ ] Check resource utilization trends
- [ ] Update dependencies if needed
- [ ] Test disaster recovery

### Monthly

- [ ] Rotate secrets
- [ ] Review and update alerts
- [ ] Performance testing
- [ ] Security scan

---

## 📚 Related Documentation

- [Architecture Overview](../documentation/ARCHITECTURE.md)
- [API Documentation](https://api.yourdomain.com/docs)
- [Circuit Breaker Runbook](../docs/CIRCUIT_BREAKER_RUNBOOK.md)
- [Troubleshooting Guide](../docs/TROUBLESHOOTING.md)
- [Scaling Guide](../docs/SCALING.md)

---

## 📞 Support Contacts

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-call Engineer | `ops@example.com` | Immediate |
| Tech Lead | `tech-lead@example.com` | 15 minutes |
| Management | `manager@example.com` | 30 minutes |

---

**Last verified:** December 2025
