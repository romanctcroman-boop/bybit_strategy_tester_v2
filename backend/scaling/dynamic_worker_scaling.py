"""
Dynamic Worker Scaling - Automatic worker pool management

Provides:
- Automatic worker scaling based on queue depth
- CPU and memory based scaling decisions
- Worker health monitoring
- Graceful shutdown handling
"""

import psutil
import redis
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import threading
import time
from loguru import logger
from dataclasses import dataclass


@dataclass
class WorkerMetrics:
    """Metrics for worker performance"""
    worker_id: str
    cpu_percent: float
    memory_percent: float
    tasks_processed: int
    tasks_failed: int
    last_heartbeat: datetime
    status: str  # active, idle, overloaded, dead


@dataclass
class ScalingConfig:
    """Configuration for worker scaling"""
    min_workers: int = 1
    max_workers: int = 10
    target_queue_depth: int = 100
    scale_up_threshold: float = 0.8  # 80% of max workers busy
    scale_down_threshold: float = 0.3  # 30% of max workers busy
    cpu_threshold: float = 80.0  # Scale up if CPU > 80%
    memory_threshold: float = 85.0  # Scale up if memory > 85%
    scale_up_cooldown: int = 60  # Seconds before next scale up
    scale_down_cooldown: int = 300  # Seconds before next scale down
    heartbeat_timeout: int = 30  # Seconds before considering worker dead


class WorkerHealthMonitor:
    """
    Monitor health of worker pool.
    
    Tracks:
    - Worker heartbeats
    - Resource usage (CPU, memory)
    - Task completion rates
    - Error rates
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize health monitor.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        self.workers_key = "workers:registry"
        self.metrics_key_prefix = "workers:metrics"
    
    def register_worker(
        self,
        worker_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register new worker.
        
        Args:
            worker_id: Unique worker ID
            metadata: Worker metadata (hostname, pid, etc.)
        """
        import json
        
        worker_data = {
            'worker_id': worker_id,
            'registered_at': datetime.utcnow().isoformat(),
            'status': 'active',
            **(metadata or {})
        }
        
        self.redis.hset(
            self.workers_key,
            worker_id,
            json.dumps(worker_data)
        )
        
        logger.info(f"Registered worker: {worker_id}")
    
    def update_heartbeat(
        self,
        worker_id: str,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Update worker heartbeat.
        
        Args:
            worker_id: Worker ID
            metrics: Current metrics (CPU, memory, tasks, etc.)
        """
        import json
        
        heartbeat_data = {
            'worker_id': worker_id,
            'timestamp': datetime.utcnow().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            **(metrics or {})
        }
        
        metrics_key = f"{self.metrics_key_prefix}:{worker_id}"
        self.redis.setex(
            metrics_key,
            60,  # TTL: 60 seconds
            json.dumps(heartbeat_data)
        )
    
    def get_worker_metrics(self, worker_id: str) -> Optional[WorkerMetrics]:
        """Get metrics for specific worker"""
        import json
        
        metrics_key = f"{self.metrics_key_prefix}:{worker_id}"
        data = self.redis.get(metrics_key)
        
        if not data:
            return None
        
        metrics_dict = json.loads(data)
        
        return WorkerMetrics(
            worker_id=worker_id,
            cpu_percent=metrics_dict.get('cpu_percent', 0),
            memory_percent=metrics_dict.get('memory_percent', 0),
            tasks_processed=metrics_dict.get('tasks_processed', 0),
            tasks_failed=metrics_dict.get('tasks_failed', 0),
            last_heartbeat=datetime.fromisoformat(metrics_dict.get('timestamp')),
            status=metrics_dict.get('status', 'unknown')
        )
    
    def get_all_workers(self) -> List[WorkerMetrics]:
        """Get metrics for all registered workers"""
        import json
        
        workers_data = self.redis.hgetall(self.workers_key)
        all_metrics = []
        
        for worker_id_bytes, _ in workers_data.items():
            worker_id = worker_id_bytes.decode() if isinstance(worker_id_bytes, bytes) else worker_id_bytes
            metrics = self.get_worker_metrics(worker_id)
            
            if metrics:
                all_metrics.append(metrics)
        
        return all_metrics
    
    def remove_dead_workers(self, timeout_seconds: int = 30) -> List[str]:
        """
        Remove workers with no recent heartbeat.
        
        Args:
            timeout_seconds: Timeout before considering worker dead
        
        Returns:
            List of removed worker IDs
        """
        now = datetime.utcnow()
        dead_workers = []
        
        for metrics in self.get_all_workers():
            time_since_heartbeat = (now - metrics.last_heartbeat).total_seconds()
            
            if time_since_heartbeat > timeout_seconds:
                self.redis.hdel(self.workers_key, metrics.worker_id)
                dead_workers.append(metrics.worker_id)
                logger.warning(f"Removed dead worker: {metrics.worker_id}")
        
        return dead_workers


class DynamicWorkerScaler:
    """
    Automatic worker scaling based on load.
    
    Scales workers up/down based on:
    - Queue depth
    - CPU usage
    - Memory usage
    - Worker utilization
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        config: ScalingConfig,
        health_monitor: WorkerHealthMonitor
    ):
        """
        Initialize worker scaler.
        
        Args:
            redis_client: Redis client instance
            config: Scaling configuration
            health_monitor: Worker health monitor
        """
        self.redis = redis_client
        self.config = config
        self.health_monitor = health_monitor
        
        self.last_scale_up = datetime.min
        self.last_scale_down = datetime.min
        
        self._running = False
        self._scaling_thread: Optional[threading.Thread] = None
    
    def should_scale_up(
        self,
        queue_depth: int,
        active_workers: int
    ) -> bool:
        """
        Determine if we should scale up.
        
        Args:
            queue_depth: Current queue depth
            active_workers: Number of active workers
        
        Returns:
            True if should scale up
        """
        # Check cooldown
        time_since_last_scale = (datetime.utcnow() - self.last_scale_up).total_seconds()
        if time_since_last_scale < self.config.scale_up_cooldown:
            return False
        
        # Check max workers
        if active_workers >= self.config.max_workers:
            return False
        
        # Check queue depth
        if queue_depth > self.config.target_queue_depth:
            logger.info(f"Queue depth ({queue_depth}) exceeds target ({self.config.target_queue_depth})")
            return True
        
        # Check worker utilization
        workers = self.health_monitor.get_all_workers()
        if workers:
            busy_workers = sum(1 for w in workers if w.cpu_percent > 50)
            utilization = busy_workers / len(workers)
            
            if utilization > self.config.scale_up_threshold:
                logger.info(f"Worker utilization ({utilization:.2%}) exceeds threshold")
                return True
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > self.config.cpu_threshold:
            logger.info(f"CPU usage ({cpu_percent}%) exceeds threshold")
            return True
        
        if memory_percent > self.config.memory_threshold:
            logger.info(f"Memory usage ({memory_percent}%) exceeds threshold")
            return True
        
        return False
    
    def should_scale_down(
        self,
        queue_depth: int,
        active_workers: int
    ) -> bool:
        """
        Determine if we should scale down.
        
        Args:
            queue_depth: Current queue depth
            active_workers: Number of active workers
        
        Returns:
            True if should scale down
        """
        # Check cooldown
        time_since_last_scale = (datetime.utcnow() - self.last_scale_down).total_seconds()
        if time_since_last_scale < self.config.scale_down_cooldown:
            return False
        
        # Check min workers
        if active_workers <= self.config.min_workers:
            return False
        
        # Check queue depth (only scale down if queue is small)
        if queue_depth > self.config.target_queue_depth * 0.5:
            return False
        
        # Check worker utilization
        workers = self.health_monitor.get_all_workers()
        if workers:
            busy_workers = sum(1 for w in workers if w.cpu_percent > 50)
            utilization = busy_workers / len(workers)
            
            if utilization < self.config.scale_down_threshold:
                logger.info(f"Worker utilization ({utilization:.2%}) below threshold")
                return True
        
        return False
    
    def scale_up(self, num_workers: int = 1) -> int:
        """
        Scale up worker pool.
        
        Args:
            num_workers: Number of workers to add
        
        Returns:
            Number of workers actually added
        """
        current_workers = len(self.health_monitor.get_all_workers())
        max_new_workers = self.config.max_workers - current_workers
        
        actual_new_workers = min(num_workers, max_new_workers)
        
        if actual_new_workers <= 0:
            logger.warning("Cannot scale up: at max worker limit")
            return 0
        
        # In production, this would spawn new worker processes/containers
        # For now, we just log and update timestamp
        logger.info(f"🚀 Scaling up: adding {actual_new_workers} workers")
        self.last_scale_up = datetime.utcnow()
        
        # Emit scaling event
        self._emit_scaling_event('scale_up', actual_new_workers)
        
        return actual_new_workers
    
    def scale_down(self, num_workers: int = 1) -> int:
        """
        Scale down worker pool.
        
        Args:
            num_workers: Number of workers to remove
        
        Returns:
            Number of workers actually removed
        """
        current_workers = len(self.health_monitor.get_all_workers())
        max_removable = current_workers - self.config.min_workers
        
        actual_removed = min(num_workers, max_removable)
        
        if actual_removed <= 0:
            logger.warning("Cannot scale down: at min worker limit")
            return 0
        
        # In production, this would gracefully shutdown worker processes
        logger.info(f"📉 Scaling down: removing {actual_removed} workers")
        self.last_scale_down = datetime.utcnow()
        
        # Emit scaling event
        self._emit_scaling_event('scale_down', actual_removed)
        
        return actual_removed
    
    def _emit_scaling_event(self, event_type: str, num_workers: int):
        """Emit scaling event to Redis for monitoring"""
        import json
        
        event = {
            'event_type': event_type,
            'num_workers': num_workers,
            'timestamp': datetime.utcnow().isoformat(),
            'total_workers': len(self.health_monitor.get_all_workers())
        }
        
        self.redis.xadd('scaling:events', event)
    
    def run_scaling_loop(self, interval_seconds: int = 30):
        """
        Run continuous scaling loop.
        
        Args:
            interval_seconds: Check interval in seconds
        """
        self._running = True
        
        def scaling_loop():
            while self._running:
                try:
                    # Remove dead workers
                    self.health_monitor.remove_dead_workers(
                        timeout_seconds=self.config.heartbeat_timeout
                    )
                    
                    # Get current state
                    queue_depth = self.redis.llen('celery')  # Celery default queue
                    active_workers = len(self.health_monitor.get_all_workers())
                    
                    logger.debug(f"Queue: {queue_depth}, Workers: {active_workers}")
                    
                    # Make scaling decision
                    if self.should_scale_up(queue_depth, active_workers):
                        self.scale_up()
                    elif self.should_scale_down(queue_depth, active_workers):
                        self.scale_down()
                    
                except Exception as e:
                    logger.error(f"Error in scaling loop: {e}")
                
                time.sleep(interval_seconds)
        
        self._scaling_thread = threading.Thread(target=scaling_loop, daemon=True)
        self._scaling_thread.start()
        
        logger.info(f"Started scaling loop (interval: {interval_seconds}s)")
    
    def stop_scaling_loop(self):
        """Stop scaling loop"""
        self._running = False
        if self._scaling_thread:
            self._scaling_thread.join(timeout=5)
        logger.info("Stopped scaling loop")
    
    def get_scaling_metrics(self) -> Dict[str, Any]:
        """Get current scaling metrics"""
        workers = self.health_monitor.get_all_workers()
        
        return {
            'total_workers': len(workers),
            'min_workers': self.config.min_workers,
            'max_workers': self.config.max_workers,
            'active_workers': sum(1 for w in workers if w.status == 'active'),
            'overloaded_workers': sum(1 for w in workers if w.cpu_percent > 80),
            'average_cpu': sum(w.cpu_percent for w in workers) / len(workers) if workers else 0,
            'average_memory': sum(w.memory_percent for w in workers) / len(workers) if workers else 0,
            'last_scale_up': self.last_scale_up.isoformat(),
            'last_scale_down': self.last_scale_down.isoformat()
        }
