# Redis Cluster Implementation Guide

**Date**: November 5, 2025  
**Status**: 🔴 IN PROGRESS  
**Priority**: CRITICAL (Production Blocker)

---

## 📊 Why Redis Cluster?

### Current Problem: Single Point of Failure (SPOF)

```
Current Architecture:
┌─────────────────┐
│  Single Redis   │  ← CRASH = TOTAL SYSTEM FAILURE ❌
│   Instance      │
└─────────────────┘
        ↓
┌─────────────────┐
│   TaskQueue     │
└─────────────────┘
```

### Redis Cluster Solution: High Availability + Scalability

```
Redis Cluster Architecture:
┌──────────────────────────────────────────────────┐
│                Redis Cluster                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │Master 1 │  │Master 2 │  │Master 3 │          │
│  │Port 7000│  │Port 7001│  │Port 7002│          │
│  └────┬────┘  └────┬────┘  └────┬────┘          │
│       │            │            │                 │
│       ↓            ↓            ↓                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │Replica 1│  │Replica 2│  │Replica 3│          │
│  │Port 7003│  │Port 7004│  │Port 7005│          │
│  └─────────┘  └─────────┘  └─────────┘          │
└──────────────────────────────────────────────────┘
        ↓
┌─────────────────┐
│   TaskQueue     │  ← Automatic failover ✅
└─────────────────┘
```

**Benefits**:
- ✅ **High Availability**: Master failure → Replica promoted automatically
- ✅ **Horizontal Scaling**: Distribute load across multiple nodes
- ✅ **Data Sharding**: 16,384 slots distributed across masters
- ✅ **Read Scalability**: Replicas can serve read requests
- ✅ **No Downtime**: Rolling upgrades possible

---

## 🚀 Quick Start

### Prerequisites

1. **Redis Installed**:
   ```powershell
   # Download from: https://github.com/microsoftarchive/redis/releases
   # Or use Chocolatey:
   choco install redis-64
   ```

2. **Ports Available**: 7000-7005 (TCP)

3. **Disk Space**: ~500MB for cluster data

---

### Setup Script

**Run Cluster Setup**:
```powershell
# Navigate to scripts directory
cd D:\bybit_strategy_tester_v2\scripts

# Setup 6-node cluster (3 masters, 3 replicas)
.\setup_redis_cluster.ps1

# Options:
.\setup_redis_cluster.ps1 -Clean      # Clean and restart
.\setup_redis_cluster.ps1 -Stop       # Stop all nodes
.\setup_redis_cluster.ps1 -RedisPath "C:\Path\To\Redis"  # Custom path
```

**Expected Output**:
```
================================================================================
Redis Cluster Setup Script
================================================================================

✅ Redis found at: C:\Program Files\Redis

📁 Creating data directories...
  ✅ Created: D:\redis_cluster_data\node_7000
  ✅ Created: D:\redis_cluster_data\node_7001
  ...

⚙️ Creating configuration files...
  ✅ Created config: redis_7000.conf
  ✅ Created config: redis_7001.conf
  ...

🚀 Starting Redis nodes...
  ✅ Started node on port 7000 (PID: 12345)
  ✅ Started node on port 7001 (PID: 12346)
  ...

🔗 Creating Redis Cluster...
>>> Performing hash slots allocation on 6 nodes...
Master[0] -> Slots 0 - 5460
Master[1] -> Slots 5461 - 10922
Master[2] -> Slots 10923 - 16383
...
✅ Cluster created successfully!

================================================================================
✅ Redis Cluster Setup Complete!
================================================================================

Connection Endpoints:
  Node 1: 127.0.0.1:7000 (MASTER)
  Node 2: 127.0.0.1:7001 (MASTER)
  Node 3: 127.0.0.1:7002 (MASTER)
  Node 4: 127.0.0.1:7003 (REPLICA)
  Node 5: 127.0.0.1:7004 (REPLICA)
  Node 6: 127.0.0.1:7005 (REPLICA)
```

---

## ⚙️ Configuration Details

### Node Configuration (redis.conf)

Each node has optimized configuration:

```conf
# Network
port 7000                    # Unique per node
bind 127.0.0.1
protected-mode yes

# Persistence (AOF + RDB)
appendonly yes               # Write-Ahead Log for durability
appendfsync everysec         # Balance between performance and safety
save 900 1                   # RDB snapshot every 15 min
save 300 10                  # RDB snapshot every 5 min
save 60 10000                # RDB snapshot every 1 min

# Cluster
cluster-enabled yes
cluster-node-timeout 5000    # 5 second timeout for node failures
cluster-require-full-coverage yes  # Strict mode

# Memory
maxmemory 256mb              # Per-node limit
maxmemory-policy allkeys-lru # Evict least recently used
```

### Why These Settings?

**AOF (Append-Only File)**:
- Logs every write operation
- Ensures durability (data survives crashes)
- `appendfsync everysec` = write to disk every second (performance + safety)

**RDB Snapshots**:
- Point-in-time backup
- Faster restarts than AOF alone
- Multiple save points for flexibility

**Cluster Timeout**:
- 5 seconds = balance between false positives and fast failover
- Too low = unnecessary failovers
- Too high = longer downtime

---

## 🔌 TaskQueue Integration

### Update Connection Configuration

**Before (Single Redis)**:
```python
# backend/services/task_queue.py
class TaskQueue:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = Redis.from_url(redis_url)
```

**After (Redis Cluster)**:
```python
# backend/services/task_queue.py
from redis.cluster import RedisCluster

class TaskQueue:
    def __init__(
        self, 
        cluster_nodes: List[Dict[str, Any]] = None,
        redis_url: str = None  # Fallback for dev
    ):
        if cluster_nodes:
            # Production: Redis Cluster
            self.redis = RedisCluster(
                startup_nodes=cluster_nodes,
                decode_responses=False,
                skip_full_coverage_check=False,
                max_connections_per_node=50
            )
        else:
            # Development: Single instance
            self.redis = Redis.from_url(redis_url or "redis://localhost:6379/0")
```

**Configuration File** (config/redis.yaml):
```yaml
# Production
redis:
  mode: cluster
  nodes:
    - host: 127.0.0.1
      port: 7000
    - host: 127.0.0.1
      port: 7001
    - host: 127.0.0.1
      port: 7002

# Development
# redis:
#   mode: single
#   url: redis://localhost:6379/0
```

---

## 🧪 Testing Cluster

### 1. Basic Connectivity

```bash
# Connect to cluster
redis-cli -c -p 7000

# Test commands
127.0.0.1:7000> SET mykey "Hello Cluster"
-> Redirected to slot [14687] located at 127.0.0.1:7002
OK

127.0.0.1:7002> GET mykey
"Hello Cluster"
```

**Note**: `-c` flag enables cluster mode (follows redirects)

---

### 2. Verify Cluster Status

```bash
# Cluster info
redis-cli -p 7000 cluster info

# Expected output:
# cluster_state:ok
# cluster_slots_assigned:16384
# cluster_slots_ok:16384
# cluster_known_nodes:6
# cluster_size:3

# List all nodes
redis-cli -p 7000 cluster nodes

# Expected output (example):
# 07c37dfeb235213a872192d90877d0cd55635b91 127.0.0.1:7000@17000 myself,master
# - 0 1465474472010 1 connected 0-5460
# 67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 127.0.0.1:7002@17002 master
# - 0 1465474471001 3 connected 10923-16383
# 292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 127.0.0.1:7001@17001 master
# - 0 1465474470995 2 connected 5461-10922
# ...
```

---

### 3. Test Failover

**Simulate Master Crash**:
```powershell
# Stop master node
Stop-Process -Id (Get-Process redis-server | Where-Object { $_.CommandLine -like "*7000*" }).Id

# Wait 5-10 seconds for failover
Start-Sleep -Seconds 10

# Check cluster status
redis-cli -p 7001 cluster nodes
```

**Expected**: Replica 7003 promoted to master ✅

---

### 4. Integration Tests with Cluster

```python
# tests/integration/test_redis_cluster.py
import pytest
from backend.services.task_queue import TaskQueue

@pytest.mark.asyncio
async def test_cluster_connectivity():
    """Test TaskQueue works with Redis Cluster"""
    
    cluster_nodes = [
        {"host": "127.0.0.1", "port": 7000},
        {"host": "127.0.0.1", "port": 7001},
        {"host": "127.0.0.1", "port": 7002},
    ]
    
    queue = TaskQueue(cluster_nodes=cluster_nodes)
    await queue.connect()
    
    # Enqueue task
    task_id = await queue.enqueue_task(
        task_type="TEST_TASK",
        data={"test": "cluster"},
        priority="HIGH"
    )
    
    assert task_id is not None
    
    # Dequeue task
    tasks = await queue.dequeue_task(count=1, block_ms=1000)
    assert len(tasks) == 1
    
    await queue.disconnect()

@pytest.mark.asyncio
async def test_cluster_failover():
    """Test TaskQueue handles node failure gracefully"""
    # ... test implementation
```

---

## 📊 Monitoring & Alerts

### Key Metrics to Monitor

**Cluster Health**:
```bash
# Monitor continuously
watch -n 5 'redis-cli -p 7000 cluster info'

# Key metrics:
# - cluster_state: Should be "ok"
# - cluster_slots_assigned: Should be 16384
# - cluster_known_nodes: Should be 6
```

**Node Health**:
```bash
# Check each node
for port in 7000 7001 7002 7003 7004 7005; do
    echo "Node $port:"
    redis-cli -p $port info replication | grep role
    redis-cli -p $port info memory | grep used_memory_human
done
```

**Grafana Dashboards**:
- Cluster state (ok/fail)
- Node count (masters/replicas)
- Memory usage per node
- Replication lag
- Failed nodes count

**Alert Rules**:
```yaml
# Prometheus alerts
- alert: RedisClusterDown
  expr: redis_cluster_state != 1
  for: 1m
  annotations:
    summary: "Redis Cluster is DOWN"

- alert: RedisNodeDown
  expr: redis_up == 0
  for: 30s
  annotations:
    summary: "Redis node {{ $labels.instance }} is DOWN"

- alert: RedisReplicationLag
  expr: redis_replication_lag_seconds > 10
  for: 2m
  annotations:
    summary: "Replica lag > 10 seconds"
```

---

## 🚨 Common Issues & Solutions

### Issue 1: "Cluster is DOWN"

**Symptoms**:
```
(error) CLUSTERDOWN The cluster is down
```

**Causes**:
- Too many masters failed
- Not enough replicas available
- Network partition

**Solution**:
```bash
# Check cluster state
redis-cli -p 7000 cluster info

# Manually fix cluster (use with caution)
redis-cli -p 7000 cluster fix
```

---

### Issue 2: "No connection could be made"

**Symptoms**:
```
Could not connect to Redis at 127.0.0.1:7000: Connection refused
```

**Solutions**:
```powershell
# Check if node is running
Get-Process redis-server

# Check if port is listening
netstat -an | Select-String "7000"

# Restart node
.\setup_redis_cluster.ps1 -Stop
.\setup_redis_cluster.ps1
```

---

### Issue 3: "MOVED" Redirects

**Symptoms**:
```
(error) MOVED 3999 127.0.0.1:7001
```

**Explanation**: Normal behavior! Cluster redirects to correct node.

**Solution**: Use `-c` flag with redis-cli, or ensure redis-py cluster client is used.

---

## 📚 Next Steps

### 1. Production Deployment Checklist

- [ ] Setup cluster on dedicated servers (not localhost)
- [ ] Configure firewall rules (ports 7000-7005, 17000-17005)
- [ ] Enable Redis AUTH for security
- [ ] Setup Prometheus exporters
- [ ] Configure Grafana dashboards
- [ ] Setup alert rules in Alert Manager
- [ ] Document runbooks for common issues
- [ ] Test failover scenarios
- [ ] Backup and restore procedures

---

### 2. TaskQueue Code Updates

- [ ] Update TaskQueue to use RedisCluster client
- [ ] Add cluster health checks
- [ ] Update connection pooling for cluster
- [ ] Add retry logic for MOVED/ASK redirects
- [ ] Update metrics to track per-node stats
- [ ] Integration tests with cluster

---

### 3. Performance Tuning

- [ ] Benchmark throughput (target: 10,000+ tasks/sec)
- [ ] Optimize slot distribution
- [ ] Tune maxmemory-policy per workload
- [ ] Enable read-from-replica for read-heavy streams
- [ ] Configure client-side connection pooling

---

## 📖 References

- Redis Cluster Tutorial: https://redis.io/docs/management/scaling/
- Redis Cluster Spec: https://redis.io/docs/reference/cluster-spec/
- redis-py Cluster: https://redis-py.readthedocs.io/en/stable/clustering.html
- DeepSeek Recommendations: ../DEEPSEEK_PRODUCTION_RECOMMENDATIONS.md

---

*Setup script: scripts/setup_redis_cluster.ps1*  
*Generated: November 5, 2025*  
*Status: Ready for implementation*
