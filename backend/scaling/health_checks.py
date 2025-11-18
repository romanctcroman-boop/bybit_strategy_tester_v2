"""
Health Checks and Failover - Ensure system reliability

Provides:
- Continuous health monitoring
- Automatic failover on worker failures
- Circuit breaker pattern
- Recovery mechanisms
"""

import redis
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
from dataclasses import dataclass
import threading
import time


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit breaker tripped
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: HealthStatus
    response_time_ms: float
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping requests to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            success_threshold: Successes before closing circuit
            timeout_seconds: Time before trying half-open
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_attempt_time: Optional[datetime] = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args, **kwargs: Function arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.timeout_seconds:
                    logger.info("Circuit breaker: Attempting half-open")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception("Circuit breaker is OPEN")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            self.last_attempt_time = datetime.utcnow()
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful execution"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker: Closing (recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker: Opening (recovery failed)")
            self.state = CircuitState.OPEN
        
        elif self.failure_count >= self.failure_threshold:
            logger.error(f"Circuit breaker: Opening (failures: {self.failure_count})")
            self.state = CircuitState.OPEN
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("Circuit breaker: Manual reset")


class HealthCheck:
    """
    Health check for a service/worker.
    
    Monitors service health and triggers failover if needed.
    """
    
    def __init__(
        self,
        service_id: str,
        check_func: Callable[[], bool],
        interval_seconds: int = 30,
        timeout_seconds: int = 10
    ):
        """
        Initialize health check.
        
        Args:
            service_id: Service/worker ID
            check_func: Function that returns True if healthy
            interval_seconds: Check interval
            timeout_seconds: Check timeout
        """
        self.service_id = service_id
        self.check_func = check_func
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        
        self.last_check: Optional[HealthCheckResult] = None
        self.consecutive_failures = 0
        self.circuit_breaker = CircuitBreaker()
    
    def check(self) -> HealthCheckResult:
        """
        Perform health check.
        
        Returns:
            HealthCheckResult
        """
        start_time = time.time()
        
        try:
            # Execute health check with timeout
            is_healthy = self.check_func()
            response_time_ms = (time.time() - start_time) * 1000
            
            if is_healthy:
                self.consecutive_failures = 0
                result = HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms
                )
            else:
                self.consecutive_failures += 1
                result = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time_ms,
                    error_message="Health check returned False"
                )
        
        except Exception as e:
            self.consecutive_failures += 1
            response_time_ms = (time.time() - start_time) * 1000
            
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error_message=str(e)
            )
        
        self.last_check = result
        return result


class HealthMonitor:
    """
    Central health monitoring service.
    
    Monitors all services and triggers failover actions.
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize health monitor.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        self.health_checks: Dict[str, HealthCheck] = {}
        self.failover_handlers: Dict[str, Callable] = {}
        
        self._running = False
        self._monitoring_thread: Optional[threading.Thread] = None
    
    def register_health_check(
        self,
        service_id: str,
        check_func: Callable[[], bool],
        failover_handler: Optional[Callable] = None,
        interval_seconds: int = 30
    ):
        """
        Register health check for service.
        
        Args:
            service_id: Service/worker ID
            check_func: Health check function
            failover_handler: Function to call on failover
            interval_seconds: Check interval
        """
        self.health_checks[service_id] = HealthCheck(
            service_id=service_id,
            check_func=check_func,
            interval_seconds=interval_seconds
        )
        
        if failover_handler:
            self.failover_handlers[service_id] = failover_handler
        
        logger.info(f"Registered health check for {service_id}")
    
    def unregister_health_check(self, service_id: str):
        """Unregister health check"""
        if service_id in self.health_checks:
            del self.health_checks[service_id]
        if service_id in self.failover_handlers:
            del self.failover_handlers[service_id]
        
        logger.info(f"Unregistered health check for {service_id}")
    
    def check_service(self, service_id: str) -> Optional[HealthCheckResult]:
        """
        Check health of specific service.
        
        Args:
            service_id: Service ID to check
        
        Returns:
            HealthCheckResult or None if not registered
        """
        health_check = self.health_checks.get(service_id)
        if not health_check:
            return None
        
        result = health_check.check()
        
        # Store result in Redis
        self._store_health_result(service_id, result)
        
        # Trigger failover if unhealthy
        if result.status == HealthStatus.UNHEALTHY:
            if health_check.consecutive_failures >= 3:
                logger.error(f"Service {service_id} is unhealthy (failures: {health_check.consecutive_failures})")
                self._trigger_failover(service_id)
        
        return result
    
    def _store_health_result(self, service_id: str, result: HealthCheckResult):
        """Store health check result in Redis"""
        import json
        
        key = f"health:{service_id}"
        data = {
            'service_id': service_id,
            'status': result.status.value,
            'response_time_ms': result.response_time_ms,
            'error_message': result.error_message,
            'timestamp': result.timestamp.isoformat()
        }
        
        self.redis.setex(key, 300, json.dumps(data))  # TTL: 5 minutes
    
    def _trigger_failover(self, service_id: str):
        """
        Trigger failover for failed service.
        
        Args:
            service_id: Failed service ID
        """
        logger.warning(f"Triggering failover for {service_id}")
        
        # Call failover handler if registered
        handler = self.failover_handlers.get(service_id)
        if handler:
            try:
                handler(service_id)
                logger.info(f"Failover handler executed for {service_id}")
            except Exception as e:
                logger.error(f"Failover handler failed for {service_id}: {e}")
        
        # Emit failover event
        self.redis.xadd('health:failover:events', {
            'service_id': service_id,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_all_health_status(self) -> Dict[str, HealthCheckResult]:
        """Get health status of all services"""
        results = {}
        
        for service_id, health_check in self.health_checks.items():
            if health_check.last_check:
                results[service_id] = health_check.last_check
            else:
                # No check yet
                results[service_id] = HealthCheckResult(
                    status=HealthStatus.UNKNOWN,
                    response_time_ms=0
                )
        
        return results
    
    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy service IDs"""
        unhealthy = []
        
        for service_id, health_check in self.health_checks.items():
            if health_check.last_check and health_check.last_check.status == HealthStatus.UNHEALTHY:
                unhealthy.append(service_id)
        
        return unhealthy
    
    def run_monitoring_loop(self, check_interval_seconds: int = 30):
        """
        Start continuous health monitoring.
        
        Args:
            check_interval_seconds: Interval between checks
        """
        self._running = True
        
        def monitoring_loop():
            while self._running:
                try:
                    for service_id in list(self.health_checks.keys()):
                        self.check_service(service_id)
                
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                
                time.sleep(check_interval_seconds)
        
        self._monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        logger.info(f"Started health monitoring loop (interval: {check_interval_seconds}s)")
    
    def stop_monitoring_loop(self):
        """Stop health monitoring loop"""
        self._running = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Stopped health monitoring loop")


class AutoRecovery:
    """
    Automatic recovery mechanisms.
    
    Attempts to recover failed services automatically.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        health_monitor: HealthMonitor
    ):
        """
        Initialize auto-recovery.
        
        Args:
            redis_client: Redis client instance
            health_monitor: Health monitor instance
        """
        self.redis = redis_client
        self.health_monitor = health_monitor
        self.recovery_attempts: Dict[str, int] = {}
        self.max_recovery_attempts = 3
    
    def attempt_recovery(self, service_id: str) -> bool:
        """
        Attempt to recover failed service.
        
        Args:
            service_id: Service ID to recover
        
        Returns:
            True if recovery successful
        """
        attempts = self.recovery_attempts.get(service_id, 0)
        
        if attempts >= self.max_recovery_attempts:
            logger.error(f"Max recovery attempts reached for {service_id}")
            return False
        
        self.recovery_attempts[service_id] = attempts + 1
        
        logger.info(f"Attempting recovery for {service_id} (attempt {attempts + 1}/{self.max_recovery_attempts})")
        
        # Recovery logic (restart worker, clear state, etc.)
        try:
            # In production, this would actually restart the service
            # For now, we just simulate recovery
            time.sleep(2)
            
            # Check if recovery was successful
            result = self.health_monitor.check_service(service_id)
            
            if result and result.status == HealthStatus.HEALTHY:
                logger.info(f"Successfully recovered {service_id}")
                self.recovery_attempts[service_id] = 0
                return True
            else:
                logger.warning(f"Recovery failed for {service_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error during recovery of {service_id}: {e}")
            return False
