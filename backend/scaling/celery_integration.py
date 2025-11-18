"""
Celery Integration with Horizontal Scaling

Integrates Celery with Redis Consumer Groups, dynamic scaling,
load balancing, and health monitoring.
"""

import os
import redis
from celery import Celery, signals
from typing import Optional
from loguru import logger

from backend.scaling import (
    RedisConsumerGroup,
    WorkerHealthMonitor,
    DynamicWorkerScaler,
    LoadBalancer,
    HealthMonitor,
    ScalingConfig,
    LoadBalancingStrategy
)


class ScalableCeleryApp:
    """
    Enhanced Celery app with horizontal scaling capabilities.
    
    Features:
    - Automatic worker scaling based on queue depth
    - Load balancing across workers
    - Health monitoring and failover
    - Redis consumer groups for reliable processing
    """
    
    def __init__(
        self,
        app_name: str = "bybit_strategy_tester_v2",
        redis_url: Optional[str] = None,
        scaling_config: Optional[ScalingConfig] = None,
        enable_scaling: bool = True
    ):
        """
        Initialize scalable Celery app.
        
        Args:
            app_name: Application name
            redis_url: Redis connection URL
            scaling_config: Scaling configuration
            enable_scaling: Enable dynamic scaling
        """
        self.app_name = app_name
        
        # Redis connection
        self.redis_url = redis_url or os.environ.get(
            "CELERY_BROKER_URL",
            "redis://localhost:6379/0"
        )
        
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        
        # Celery app
        self.celery_app = Celery(
            app_name,
            broker=self.redis_url,
            backend=self.redis_url
        )
        
        # Configure Celery
        self._configure_celery()
        
        # Scaling components
        self.scaling_enabled = enable_scaling
        if self.scaling_enabled:
            self.scaling_config = scaling_config or ScalingConfig()
            self._setup_scaling_components()
            self._register_celery_signals()
    
    def _configure_celery(self):
        """Configure Celery settings"""
        self.celery_app.conf.update(
            # Task settings
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            
            # Worker settings
            worker_prefetch_multiplier=1,  # Only prefetch 1 task per worker
            task_acks_late=True,  # Acknowledge after completion
            task_reject_on_worker_lost=True,  # Reject if worker dies
            
            # Reliability
            broker_connection_retry=True,
            broker_connection_retry_on_startup=True,
            broker_connection_max_retries=10,
            
            # Performance
            worker_disable_rate_limits=False,
            task_compression='gzip',
            result_compression='gzip',
            
            # Monitoring
            worker_send_task_events=True,
            task_send_sent_event=True,
        )
    
    def _setup_scaling_components(self):
        """Setup scaling infrastructure"""
        # Health monitor
        self.health_monitor = WorkerHealthMonitor(self.redis_client)
        
        # Dynamic scaler
        self.scaler = DynamicWorkerScaler(
            redis_client=self.redis_client,
            config=self.scaling_config,
            health_monitor=self.health_monitor
        )
        
        # Load balancer
        self.load_balancer = LoadBalancer(
            redis_client=self.redis_client,
            strategy=LoadBalancingStrategy.LEAST_LOADED
        )
        
        # Health monitoring
        self.health_service = HealthMonitor(self.redis_client)
        
        # Redis consumer group
        self.consumer_group = RedisConsumerGroup(
            redis_client=self.redis_client,
            stream_name=f"{self.app_name}:tasks",
            group_name=f"{self.app_name}:workers"
        )
        
        logger.info("Initialized scaling components")
    
    def _register_celery_signals(self):
        """Register Celery signal handlers for scaling"""
        
        @signals.worker_ready.connect
        def on_worker_ready(sender, **kwargs):
            """Worker startup handler"""
            worker_id = sender.hostname
            logger.info(f"Worker ready: {worker_id}")
            
            # Register worker
            self.health_monitor.register_worker(
                worker_id=worker_id,
                metadata={
                    'hostname': sender.hostname,
                    'pid': os.getpid()
                }
            )
            
            # Register with load balancer
            self.load_balancer.register_worker(
                worker_id=worker_id,
                weight=1,
                max_concurrent_tasks=self.scaling_config.max_workers
            )
        
        @signals.worker_shutdown.connect
        def on_worker_shutdown(sender, **kwargs):
            """Worker shutdown handler"""
            worker_id = sender.hostname
            logger.info(f"Worker shutting down: {worker_id}")
            
            # Unregister from load balancer
            self.load_balancer.unregister_worker(worker_id)
        
        @signals.task_prerun.connect
        def on_task_prerun(sender, task_id, task, **kwargs):
            """Task start handler"""
            # Update worker heartbeat
            worker_id = task.request.hostname if hasattr(task.request, 'hostname') else 'unknown'
            self.health_monitor.update_heartbeat(
                worker_id=worker_id,
                metrics={'tasks_running': 1}
            )
        
        @signals.task_success.connect
        def on_task_success(sender, **kwargs):
            """Task success handler"""
            task_id = kwargs.get('result', {}).get('task_id')
            if task_id:
                self.load_balancer.complete_task(task_id)
        
        @signals.task_failure.connect
        def on_task_failure(sender, task_id, exception, **kwargs):
            """Task failure handler"""
            logger.error(f"Task {task_id} failed: {exception}")
            self.load_balancer.complete_task(task_id)
    
    def start_scaling(self, interval_seconds: int = 30):
        """
        Start dynamic scaling loop.
        
        Args:
            interval_seconds: Scaling check interval
        """
        if not self.scaling_enabled:
            logger.warning("Scaling is disabled")
            return
        
        # Start scaling loop
        self.scaler.run_scaling_loop(interval_seconds=interval_seconds)
        
        # Start health monitoring
        self.health_service.run_monitoring_loop(check_interval_seconds=interval_seconds)
        
        logger.info("Started scaling and health monitoring")
    
    def stop_scaling(self):
        """Stop scaling loops"""
        if not self.scaling_enabled:
            return
        
        self.scaler.stop_scaling_loop()
        self.health_service.stop_monitoring_loop()
        
        logger.info("Stopped scaling and health monitoring")
    
    def get_metrics(self) -> dict:
        """Get current scaling metrics"""
        if not self.scaling_enabled:
            return {'scaling_enabled': False}
        
        return {
            'scaling_enabled': True,
            'scaling_metrics': self.scaler.get_scaling_metrics(),
            'load_balancer_stats': self.load_balancer.get_worker_stats(),
            'health_status': {
                service_id: {
                    'status': result.status.value,
                    'response_time_ms': result.response_time_ms
                }
                for service_id, result in self.health_service.get_all_health_status().items()
            }
        }


# Create global instance (backward compatible with existing celery_app)
_scalable_app: Optional[ScalableCeleryApp] = None


def get_scalable_celery_app(
    enable_scaling: bool = True,
    scaling_config: Optional[ScalingConfig] = None
) -> ScalableCeleryApp:
    """
    Get or create scalable Celery app singleton.
    
    Args:
        enable_scaling: Enable dynamic scaling
        scaling_config: Scaling configuration
    
    Returns:
        ScalableCeleryApp instance
    """
    global _scalable_app
    
    if _scalable_app is None:
        _scalable_app = ScalableCeleryApp(
            enable_scaling=enable_scaling,
            scaling_config=scaling_config
        )
    
    return _scalable_app


# For backward compatibility
def get_celery_app() -> Celery:
    """Get Celery app (backward compatible)"""
    return get_scalable_celery_app().celery_app
