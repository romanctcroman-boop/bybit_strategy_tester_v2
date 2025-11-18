"""
Horizontal Scaling Module

Provides distributed task processing, dynamic worker scaling,
load balancing, and high availability features.

Components:
- RedisConsumerGroup: Distributed task processing with Redis Streams
- DynamicWorkerScaler: Automatic worker pool management
- LoadBalancer: Intelligent task distribution
- HealthMonitor: Service health monitoring and failover
"""

from .redis_consumer_groups import (
    RedisConsumerGroup,
    TaskPriorityQueue
)
from .dynamic_worker_scaling import (
    WorkerHealthMonitor,
    DynamicWorkerScaler,
    WorkerMetrics,
    ScalingConfig
)
from .load_balancer import (
    LoadBalancer,
    AdaptiveLoadBalancer,
    LoadBalancingStrategy,
    WorkerState
)
from .health_checks import (
    HealthMonitor,
    HealthCheck,
    CircuitBreaker,
    AutoRecovery,
    HealthStatus,
    CircuitState,
    HealthCheckResult
)

__all__ = [
    # Redis Consumer Groups
    'RedisConsumerGroup',
    'TaskPriorityQueue',
    
    # Dynamic Scaling
    'WorkerHealthMonitor',
    'DynamicWorkerScaler',
    'WorkerMetrics',
    'ScalingConfig',
    
    # Load Balancing
    'LoadBalancer',
    'AdaptiveLoadBalancer',
    'LoadBalancingStrategy',
    'WorkerState',
    
    # Health & Failover
    'HealthMonitor',
    'HealthCheck',
    'CircuitBreaker',
    'AutoRecovery',
    'HealthStatus',
    'CircuitState',
    'HealthCheckResult'
]
