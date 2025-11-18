"""
Load Balancer - Intelligent task distribution across workers

Provides:
- Round-robin load balancing
- Least-connections routing
- Weighted load balancing
- Health-aware routing
"""

import redis
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
from loguru import logger
import random


class LoadBalancingStrategy(Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_LOADED = "least_loaded"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RANDOM = "random"


class WorkerState:
    """State of a worker for load balancing"""
    
    def __init__(
        self,
        worker_id: str,
        weight: int = 1,
        max_concurrent_tasks: int = 10
    ):
        """
        Initialize worker state.
        
        Args:
            worker_id: Unique worker ID
            weight: Worker weight (higher = more tasks)
            max_concurrent_tasks: Max concurrent tasks per worker
        """
        self.worker_id = worker_id
        self.weight = weight
        self.max_concurrent_tasks = max_concurrent_tasks
        self.current_connections = 0
        self.total_tasks_assigned = 0
        self.last_assigned_at: Optional[datetime] = None
        self.is_healthy = True
    
    def can_accept_task(self) -> bool:
        """Check if worker can accept new task"""
        return (
            self.is_healthy and
            self.current_connections < self.max_concurrent_tasks
        )
    
    def assign_task(self):
        """Assign new task to worker"""
        self.current_connections += 1
        self.total_tasks_assigned += 1
        self.last_assigned_at = datetime.utcnow()
    
    def complete_task(self):
        """Mark task as completed"""
        if self.current_connections > 0:
            self.current_connections -= 1
    
    def get_load_factor(self) -> float:
        """Get current load factor (0.0 = idle, 1.0 = full)"""
        return self.current_connections / self.max_concurrent_tasks


class LoadBalancer:
    """
    Intelligent load balancer for distributing tasks across workers.
    
    Supports multiple load balancing strategies and health-aware routing.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED
    ):
        """
        Initialize load balancer.
        
        Args:
            redis_client: Redis client instance
            strategy: Load balancing strategy
        """
        self.redis = redis_client
        self.strategy = strategy
        self.workers: Dict[str, WorkerState] = {}
        self.round_robin_index = 0
    
    def register_worker(
        self,
        worker_id: str,
        weight: int = 1,
        max_concurrent_tasks: int = 10
    ):
        """
        Register worker with load balancer.
        
        Args:
            worker_id: Unique worker ID
            weight: Worker weight for weighted strategies
            max_concurrent_tasks: Max concurrent tasks
        """
        self.workers[worker_id] = WorkerState(
            worker_id=worker_id,
            weight=weight,
            max_concurrent_tasks=max_concurrent_tasks
        )
        logger.info(f"Registered worker {worker_id} with load balancer")
    
    def unregister_worker(self, worker_id: str):
        """Unregister worker from load balancer"""
        if worker_id in self.workers:
            del self.workers[worker_id]
            logger.info(f"Unregistered worker {worker_id} from load balancer")
    
    def mark_worker_unhealthy(self, worker_id: str):
        """Mark worker as unhealthy (will not receive tasks)"""
        if worker_id in self.workers:
            self.workers[worker_id].is_healthy = False
            logger.warning(f"Marked worker {worker_id} as unhealthy")
    
    def mark_worker_healthy(self, worker_id: str):
        """Mark worker as healthy"""
        if worker_id in self.workers:
            self.workers[worker_id].is_healthy = True
            logger.info(f"Marked worker {worker_id} as healthy")
    
    def get_next_worker(self) -> Optional[str]:
        """
        Get next worker for task assignment.
        
        Returns:
            Worker ID or None if no available workers
        """
        # Filter healthy workers that can accept tasks
        available_workers = [
            w for w in self.workers.values()
            if w.can_accept_task()
        ]
        
        if not available_workers:
            logger.warning("No available workers")
            return None
        
        # Select worker based on strategy
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            worker = self._round_robin_select(available_workers)
        
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            worker = self._least_connections_select(available_workers)
        
        elif self.strategy == LoadBalancingStrategy.LEAST_LOADED:
            worker = self._least_loaded_select(available_workers)
        
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            worker = self._weighted_round_robin_select(available_workers)
        
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            worker = random.choice(available_workers)
        
        else:
            # Default to least loaded
            worker = self._least_loaded_select(available_workers)
        
        return worker.worker_id if worker else None
    
    def _round_robin_select(self, workers: List[WorkerState]) -> Optional[WorkerState]:
        """Round-robin selection"""
        if not workers:
            return None
        
        worker = workers[self.round_robin_index % len(workers)]
        self.round_robin_index += 1
        
        return worker
    
    def _least_connections_select(self, workers: List[WorkerState]) -> Optional[WorkerState]:
        """Select worker with least active connections"""
        return min(workers, key=lambda w: w.current_connections)
    
    def _least_loaded_select(self, workers: List[WorkerState]) -> Optional[WorkerState]:
        """Select worker with lowest load factor"""
        return min(workers, key=lambda w: w.get_load_factor())
    
    def _weighted_round_robin_select(self, workers: List[WorkerState]) -> Optional[WorkerState]:
        """Weighted round-robin selection"""
        # Build weighted list
        weighted_workers = []
        for worker in workers:
            weighted_workers.extend([worker] * worker.weight)
        
        if not weighted_workers:
            return None
        
        worker = weighted_workers[self.round_robin_index % len(weighted_workers)]
        self.round_robin_index += 1
        
        return worker
    
    def assign_task(self, task_id: str) -> Optional[str]:
        """
        Assign task to worker.
        
        Args:
            task_id: Task ID to assign
        
        Returns:
            Worker ID that received the task, or None
        """
        worker_id = self.get_next_worker()
        
        if not worker_id:
            logger.error(f"No available worker for task {task_id}")
            return None
        
        # Update worker state
        self.workers[worker_id].assign_task()
        
        # Store assignment in Redis
        self.redis.hset(
            f"task:assignments",
            task_id,
            worker_id
        )
        
        logger.debug(f"Assigned task {task_id} to worker {worker_id}")
        
        return worker_id
    
    def complete_task(self, task_id: str):
        """
        Mark task as completed.
        
        Args:
            task_id: Task ID that completed
        """
        # Get worker assignment
        worker_id = self.redis.hget(f"task:assignments", task_id)
        
        if worker_id:
            worker_id = worker_id.decode() if isinstance(worker_id, bytes) else worker_id
            
            if worker_id in self.workers:
                self.workers[worker_id].complete_task()
                logger.debug(f"Task {task_id} completed on worker {worker_id}")
            
            # Remove assignment
            self.redis.hdel(f"task:assignments", task_id)
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get statistics for all workers"""
        stats = {}
        
        for worker_id, worker in self.workers.items():
            stats[worker_id] = {
                'current_connections': worker.current_connections,
                'total_tasks_assigned': worker.total_tasks_assigned,
                'load_factor': worker.get_load_factor(),
                'is_healthy': worker.is_healthy,
                'last_assigned_at': worker.last_assigned_at.isoformat() if worker.last_assigned_at else None
            }
        
        return stats
    
    def get_load_distribution(self) -> Dict[str, float]:
        """Get load distribution across workers"""
        total_connections = sum(w.current_connections for w in self.workers.values())
        
        if total_connections == 0:
            return {w.worker_id: 0.0 for w in self.workers.values()}
        
        return {
            w.worker_id: w.current_connections / total_connections
            for w in self.workers.values()
        }
    
    def rebalance_tasks(self) -> int:
        """
        Rebalance tasks across workers.
        
        Moves tasks from overloaded to underloaded workers.
        
        Returns:
            Number of tasks rebalanced
        """
        # Find overloaded and underloaded workers
        overloaded = [
            w for w in self.workers.values()
            if w.get_load_factor() > 0.8 and w.current_connections > 0
        ]
        
        underloaded = [
            w for w in self.workers.values()
            if w.get_load_factor() < 0.5 and w.can_accept_task()
        ]
        
        if not overloaded or not underloaded:
            return 0
        
        rebalanced = 0
        
        # Move tasks from overloaded to underloaded
        for overloaded_worker in overloaded:
            for underloaded_worker in underloaded:
                if not underloaded_worker.can_accept_task():
                    continue
                
                # Move one task
                overloaded_worker.complete_task()
                underloaded_worker.assign_task()
                rebalanced += 1
                
                logger.info(
                    f"Rebalanced task from {overloaded_worker.worker_id} "
                    f"to {underloaded_worker.worker_id}"
                )
                
                if overloaded_worker.get_load_factor() <= 0.8:
                    break
        
        return rebalanced


class AdaptiveLoadBalancer(LoadBalancer):
    """
    Adaptive load balancer that switches strategies based on load.
    
    Uses different strategies for different load conditions:
    - Low load: Round-robin for even distribution
    - Medium load: Least loaded for efficiency
    - High load: Least connections for responsiveness
    """
    
    def __init__(self, redis_client: redis.Redis):
        """Initialize adaptive load balancer"""
        super().__init__(redis_client, LoadBalancingStrategy.LEAST_LOADED)
        self.low_load_threshold = 0.3
        self.high_load_threshold = 0.7
    
    def get_next_worker(self) -> Optional[str]:
        """Get next worker with adaptive strategy"""
        # Calculate average load
        if not self.workers:
            return None
        
        avg_load = sum(w.get_load_factor() for w in self.workers.values()) / len(self.workers)
        
        # Adapt strategy based on load
        if avg_load < self.low_load_threshold:
            self.strategy = LoadBalancingStrategy.ROUND_ROBIN
            logger.debug("Using ROUND_ROBIN (low load)")
        
        elif avg_load > self.high_load_threshold:
            self.strategy = LoadBalancingStrategy.LEAST_CONNECTIONS
            logger.debug("Using LEAST_CONNECTIONS (high load)")
        
        else:
            self.strategy = LoadBalancingStrategy.LEAST_LOADED
            logger.debug("Using LEAST_LOADED (medium load)")
        
        return super().get_next_worker()
