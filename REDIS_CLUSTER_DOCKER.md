# 🐳 Redis Cluster via Docker - Quick Start

**Date**: November 5, 2025  
**Status**: ✅ READY TO USE  
**Purpose**: Production-ready Redis Cluster for TaskQueue HA

---

## 🚀 Quick Start (5 minutes)

###  Step 1: Start Redis Cluster

```bash
# Start all 6 nodes + create cluster
docker-compose -f docker-compose.redis-cluster.yml up -d

# Wait for cluster creation (30 seconds)
docker logs redis-cluster-init

# Expected output:
# >>> Performing hash slots allocation on 6 nodes...
# Master[0] -> Slots 0 - 5460
# Master[1] -> Slots 5461 - 10922
# Master[2] -> Slots 10923 - 16383
# [OK] All nodes agree about slots configuration.
# [OK] All 16384 slots covered.
```

---

### Step 2: Verify Cluster

```bash
# Check cluster status
docker exec redis-cluster-node-1 redis-cli -p 7000 cluster info

# Expected output:
# cluster_state:ok
# cluster_slots_assigned:16384
# cluster_known_nodes:6
# cluster_size:3

# List all nodes
docker exec redis-cluster-node-1 redis-cli -p 7000 cluster nodes

# Test connection
docker exec -it redis-cluster-node-1 redis-cli -c -p 7000
127.0.0.1:7000> SET test "Hello Cluster"
-> Redirected to slot [6918] located at 172.28.0.102:7001
OK
127.0.0.1:7001> GET test
"Hello Cluster"
```

---

### Step 3: Connect TaskQueue

Update `backend/services/task_queue.py`:

```python
# Development: Single Redis
# redis_url = "redis://localhost:6379/0"

# Production: Redis Cluster
cluster_nodes = [
    {"host": "localhost", "port": 7000},
    {"host": "localhost", "port": 7001},
    {"host": "localhost", "port": 7002},
]
```

---

## 🔧 Management Commands

### Start Cluster
```bash
docker-compose -f docker-compose.redis-cluster.yml up -d
```

### Stop Cluster
```bash
docker-compose -f docker-compose.redis-cluster.yml down
```

### Stop + Clean Data
```bash
docker-compose -f docker-compose.redis-cluster.yml down -v
```

### View Logs
```bash
# All nodes
docker-compose -f docker-compose.redis-cluster.yml logs

# Specific node
docker logs redis-cluster-node-1

# Follow logs
docker logs -f redis-cluster-node-1
```

### Restart Node
```bash
# Restart single node (tests failover)
docker restart redis-cluster-node-1

# Watch cluster promote replica
docker exec redis-cluster-node-2 redis-cli -p 7001 cluster nodes
```

---

## 🧪 Test Failover

### Simulate Master Crash

```bash
# 1. Check current masters
docker exec redis-cluster-node-1 redis-cli -p 7000 cluster nodes | grep master

# Example output:
# abc123... 172.28.0.101:7000 myself,master - 0 ... connected 0-5460
# def456... 172.28.0.102:7001 master - 0 ... connected 5461-10922
# ghi789... 172.28.0.103:7002 master - 0 ... connected 10923-16383

# 2. Stop first master
docker stop redis-cluster-node-1

# 3. Wait 5-10 seconds for failover
sleep 10

# 4. Check cluster - replica should be promoted
docker exec redis-cluster-node-2 redis-cli -p 7001 cluster nodes

# Expected: Replica (node-4) now shows as master for slots 0-5460

# 5. Restart original master (becomes replica)
docker start redis-cluster-node-1

# 6. Verify it joined as replica
docker exec redis-cluster-node-1 redis-cli -p 7000 cluster nodes
```

---

## 📊 Monitoring

### Cluster Health Check

```bash
# Quick health check
docker exec redis-cluster-node-1 redis-cli -p 7000 cluster info | grep cluster_state

# Should show: cluster_state:ok

# Detailed status
docker exec redis-cluster-node-1 redis-cli -p 7000 \
  --eval "redis.call('cluster', 'info')"
```

### Node Metrics

```bash
# Memory usage
for port in 7000 7001 7002 7003 7004 7005; do
  echo "Node $port:"
  docker exec redis-cluster-node-$((port-6999)) redis-cli -p $port info memory | grep used_memory_human
done

# Replication status
for port in 7000 7001 7002 7003 7004 7005; do
  echo "Node $port:"
  docker exec redis-cluster-node-$((port-6999)) redis-cli -p $port info replication | grep role
done
```

---

## 🐛 Troubleshooting

### Cluster Not Creating

**Problem**: `redis-cluster-init` exits without creating cluster

**Solution**:
```bash
# Manually create cluster
docker exec -it redis-cluster-node-1 sh

# Inside container
redis-cli --cluster create \
  172.28.0.101:7000 172.28.0.102:7001 172.28.0.103:7002 \
  172.28.0.104:7003 172.28.0.105:7004 172.28.0.106:7005 \
  --cluster-replicas 1 --cluster-yes
```

---

### Connection Refused

**Problem**: Can't connect from host to cluster

**Check**:
```bash
# Verify containers are running
docker ps | grep redis-cluster

# Check port bindings
docker port redis-cluster-node-1

# Test from host
redis-cli -c -p 7000 ping
# Should return: PONG
```

---

### CLUSTERDOWN Error

**Problem**: `(error) CLUSTERDOWN The cluster is down`

**Solution**:
```bash
# Check how many masters are up
docker exec redis-cluster-node-2 redis-cli -p 7001 cluster nodes | grep master

# Need at least 2 masters up (quorum)
# Restart stopped nodes
docker start redis-cluster-node-1
docker start redis-cluster-node-2
docker start redis-cluster-node-3
```

---

## 📈 Performance Tuning

### Connection Pooling

```python
# In TaskQueue.__init__()
from redis.cluster import RedisCluster

self.redis = RedisCluster(
    startup_nodes=cluster_nodes,
    decode_responses=False,
    skip_full_coverage_check=False,
    max_connections_per_node=50,  # Connection pool size
    readonly_mode=False,           # Don't read from replicas
    retry_on_timeout=True,
    retry_on_error=[ConnectionError, TimeoutError]
)
```

### Memory Optimization

```yaml
# In docker-compose.redis-cluster.yml
# Add to each node command:
--maxmemory 256mb
--maxmemory-policy allkeys-lru
```

---

## ✅ Integration with TaskQueue

### Update Code

```python
# backend/services/task_queue.py

from redis.cluster import RedisCluster
from redis import Redis
import os

class TaskQueue:
    def __init__(self, redis_url: str = None, cluster_nodes: list = None):
        """
        Initialize TaskQueue with Redis or Redis Cluster
        
        Args:
            redis_url: Single Redis URL (development)
            cluster_nodes: Cluster nodes list (production)
        """
        if cluster_nodes:
            # Production: Redis Cluster
            self.redis = RedisCluster(
                startup_nodes=cluster_nodes,
                decode_responses=False,
                skip_full_coverage_check=False,
                max_connections_per_node=50
            )
            self.is_cluster = True
        elif redis_url:
            # Development: Single Redis
            self.redis = Redis.from_url(redis_url)
            self.is_cluster = False
        else:
            # Default: Check environment
            if os.getenv("REDIS_CLUSTER_ENABLED") == "true":
                nodes = [
                    {"host": "localhost", "port": 7000},
                    {"host": "localhost", "port": 7001},
                    {"host": "localhost", "port": 7002},
                ]
                self.redis = RedisCluster(startup_nodes=nodes)
                self.is_cluster = True
            else:
                self.redis = Redis.from_url("redis://localhost:6379/0")
                self.is_cluster = False
```

### Environment Variables

```bash
# .env file

# Development (single Redis)
REDIS_CLUSTER_ENABLED=false
REDIS_URL=redis://localhost:6379/0

# Production (Redis Cluster)
REDIS_CLUSTER_ENABLED=true
REDIS_CLUSTER_NODES=localhost:7000,localhost:7001,localhost:7002
```

---

## 🧪 Run Tests with Cluster

```bash
# Set environment
export REDIS_CLUSTER_ENABLED=true

# Run TaskQueue tests
pytest tests/integration/test_task_queue.py -v

# Run DeepSeek tests
pytest tests/integration/test_deepseek_agent.py -v

# All tests
pytest tests/integration/ -v
```

---

## 📦 Next Steps

- [ ] Update TaskQueue to support Redis Cluster
- [ ] Add cluster health checks to monitoring
- [ ] Update CI/CD to use cluster in tests
- [ ] Document failover procedures
- [ ] Add Grafana dashboard for cluster metrics

---

## 📚 References

- Docker Compose File: `docker-compose.redis-cluster.yml`
- Redis Cluster Guide: `REDIS_CLUSTER_GUIDE.md`
- DeepSeek Recommendations: `DEEPSEEK_PRODUCTION_RECOMMENDATIONS.md`

---

*Created: November 5, 2025*  
*Status: Production-ready Redis Cluster via Docker* ✅
