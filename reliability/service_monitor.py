"""
Service Health Monitoring System

Implements continuous health monitoring with:
- Perplexity Agent: 30-second check intervals, P95 latency tracking
- DeepSeek Agent: Multi-state health (HEALTHY/DEGRADED/UNHEALTHY/DEAD)
- Prometheus: Metrics export ready

Features:
- Health Check Scheduling: Async periodic checks every 30s
- Multi-State Status: HEALTHY → DEGRADED → UNHEALTHY → DEAD
- Latency Tracking: P50, P95, P99 percentiles
- Failure Detection: Consecutive failure threshold
- Recovery Detection: Automatic state improvement
- Alerting: Configurable alert callbacks
- Metrics Export: Prometheus-compatible metrics

Usage:
    from reliability.service_monitor import ServiceMonitor, ServiceConfig
    
    # Define health check
    async def check_api_health():
        response = await httpx.get("https://api.example.com/health")
        return response.status_code == 200
    
    # Configure monitoring
    config = ServiceConfig(
        name="api_service",
        check_interval=30.0,
        timeout=5.0
    )
    
    monitor = ServiceMonitor(config, check_api_health)
    
    # Start monitoring
    await monitor.start()
    
    # Get current health
    health = monitor.get_health()
    print(f"Status: {health.status}, Latency P95: {health.latency_p95:.2f}ms")
"""

import asyncio
import logging
import time
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, List, Dict, Any, Awaitable
from collections import deque

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"         # All checks passing, low latency
    DEGRADED = "degraded"       # Some failures or high latency
    UNHEALTHY = "unhealthy"     # Many failures, very high latency
    DEAD = "dead"               # Service completely unavailable


@dataclass
class ServiceConfig:
    """Service monitoring configuration
    
    Attributes:
        name: Service name
        check_interval: Seconds between health checks (default: 30)
        timeout: Max seconds for health check (default: 5)
        failure_threshold: Consecutive failures before UNHEALTHY (default: 3)
        dead_threshold: Consecutive failures before DEAD (default: 10)
        latency_threshold_degraded: P95 latency (ms) for DEGRADED (default: 1000)
        latency_threshold_unhealthy: P95 latency (ms) for UNHEALTHY (default: 3000)
        sample_size: Number of recent checks to track (default: 100)
    """
    name: str
    check_interval: float = 30.0
    timeout: float = 5.0
    failure_threshold: int = 3
    dead_threshold: int = 10
    latency_threshold_degraded: float = 1000.0  # ms
    latency_threshold_unhealthy: float = 3000.0  # ms
    sample_size: int = 100


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    timestamp: float
    success: bool
    latency_ms: float
    error: Optional[str] = None


@dataclass
class ServiceHealth:
    """Current health state of a service
    
    Attributes:
        status: Current health status
        last_check: Timestamp of last check
        consecutive_failures: Number of consecutive failures
        total_checks: Total checks performed
        total_successes: Total successful checks
        total_failures: Total failed checks
        latency_p50: P50 latency in milliseconds
        latency_p95: P95 latency in milliseconds
        latency_p99: P99 latency in milliseconds
        uptime_percentage: Percentage of successful checks
    """
    status: HealthStatus
    last_check: float
    consecutive_failures: int = 0
    total_checks: int = 0
    total_successes: int = 0
    total_failures: int = 0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    uptime_percentage: float = 100.0


class ServiceMonitor:
    """Service health monitoring with continuous checks
    
    Monitors service health with:
    - Periodic health checks (default: every 30 seconds)
    - Latency percentile tracking (P50, P95, P99)
    - Status state machine (HEALTHY → DEGRADED → UNHEALTHY → DEAD)
    - Automatic recovery detection
    - Alert callbacks for status changes
    
    Example:
        async def check_api():
            response = await httpx.get("https://api.example.com/health")
            return response.status_code == 200
        
        config = ServiceConfig(name="api")
        monitor = ServiceMonitor(config, check_api)
        
        await monitor.start()
        
        # Later...
        health = monitor.get_health()
        if health.status == HealthStatus.UNHEALTHY:
            print("API is unhealthy!")
    """
    
    def __init__(
        self,
        config: ServiceConfig,
        health_check: Callable[[], Awaitable[bool]],
        on_status_change: Optional[Callable[[HealthStatus, HealthStatus], None]] = None
    ):
        """Initialize service monitor
        
        Args:
            config: Monitoring configuration
            health_check: Async function that returns True if healthy
            on_status_change: Optional callback for status changes (old_status, new_status)
        """
        self.config = config
        self.health_check = health_check
        self.on_status_change = on_status_change
        
        self.status = HealthStatus.HEALTHY
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_checks = 0
        self.total_successes = 0
        self.total_failures = 0
        self.last_check_time: Optional[float] = None
        
        # Recent check history for metrics
        self.recent_checks: deque[HealthCheckResult] = deque(maxlen=config.sample_size)
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        logger.info(
            f"Service monitor initialized: '{config.name}', "
            f"check_interval={config.check_interval}s"
        )
    
    async def start(self):
        """Start continuous health monitoring"""
        if self._monitor_task and not self._monitor_task.done():
            logger.warning(f"Monitor for '{self.config.name}' already running")
            return
        
        self._stop_event.clear()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started monitoring service '{self.config.name}'")
    
    async def stop(self):
        """Stop health monitoring"""
        if not self._monitor_task:
            return
        
        self._stop_event.set()
        
        if self._monitor_task and not self._monitor_task.done():
            await self._monitor_task
        
        logger.info(f"Stopped monitoring service '{self.config.name}'")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while not self._stop_event.is_set():
            try:
                await self._perform_health_check()
            except Exception as e:
                logger.error(
                    f"Error in monitor loop for '{self.config.name}': {e}",
                    exc_info=True
                )
            
            # Wait for next check interval
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.check_interval
                )
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue monitoring
    
    async def _perform_health_check(self):
        """Perform single health check"""
        self.total_checks += 1
        start_time = time.time()
        
        try:
            # Run health check with timeout
            is_healthy = await asyncio.wait_for(
                self.health_check(),
                timeout=self.config.timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if is_healthy:
                await self._handle_success(latency_ms)
            else:
                await self._handle_failure(latency_ms, "Health check returned False")
        
        except asyncio.TimeoutError:
            latency_ms = self.config.timeout * 1000
            await self._handle_failure(latency_ms, f"Timeout after {self.config.timeout}s")
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            await self._handle_failure(latency_ms, str(e))
        
        self.last_check_time = time.time()
    
    async def _handle_success(self, latency_ms: float):
        """Handle successful health check"""
        self.total_successes += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Record result
        self.recent_checks.append(HealthCheckResult(
            timestamp=time.time(),
            success=True,
            latency_ms=latency_ms
        ))
        
        # Update status based on latency and consecutive successes
        await self._update_status()
        
        logger.debug(
            f"Health check succeeded for '{self.config.name}': "
            f"latency={latency_ms:.1f}ms, status={self.status.value}"
        )
    
    async def _handle_failure(self, latency_ms: float, error: str):
        """Handle failed health check"""
        self.total_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        # Record result
        self.recent_checks.append(HealthCheckResult(
            timestamp=time.time(),
            success=False,
            latency_ms=latency_ms,
            error=error
        ))
        
        # Update status based on consecutive failures
        await self._update_status()
        
        logger.warning(
            f"Health check failed for '{self.config.name}': "
            f"{error}, consecutive_failures={self.consecutive_failures}, "
            f"status={self.status.value}"
        )
    
    async def _update_status(self):
        """Update health status based on recent checks"""
        old_status = self.status
        
        # Check for DEAD status (too many consecutive failures)
        if self.consecutive_failures >= self.config.dead_threshold:
            self.status = HealthStatus.DEAD
        
        # Check for UNHEALTHY status
        elif self.consecutive_failures >= self.config.failure_threshold:
            self.status = HealthStatus.UNHEALTHY
        
        # Check for DEGRADED status (high latency)
        elif self.consecutive_failures > 0:
            self.status = HealthStatus.DEGRADED
        
        else:
            # Check latency thresholds
            p95_latency = self._calculate_percentile(0.95)
            
            if p95_latency >= self.config.latency_threshold_unhealthy:
                self.status = HealthStatus.UNHEALTHY
            elif p95_latency >= self.config.latency_threshold_degraded:
                self.status = HealthStatus.DEGRADED
            else:
                # Require multiple consecutive successes to recover to HEALTHY
                if self.consecutive_successes >= 2 or self.total_checks == 1:
                    self.status = HealthStatus.HEALTHY
                else:
                    self.status = HealthStatus.DEGRADED
        
        # Trigger callback if status changed
        if old_status != self.status:
            logger.info(
                f"Service '{self.config.name}' status changed: "
                f"{old_status.value} → {self.status.value}"
            )
            
            if self.on_status_change:
                try:
                    self.on_status_change(old_status, self.status)
                except Exception as e:
                    logger.error(f"Error in status change callback: {e}")
    
    def _calculate_percentile(self, percentile: float) -> float:
        """Calculate latency percentile from recent checks
        
        Args:
            percentile: Percentile to calculate (0.0 to 1.0)
        
        Returns:
            Latency in milliseconds
        """
        if not self.recent_checks:
            return 0.0
        
        latencies = [check.latency_ms for check in self.recent_checks]
        
        try:
            return statistics.quantiles(latencies, n=100)[int(percentile * 100) - 1]
        except (statistics.StatisticsError, IndexError):
            # Fallback for small sample sizes
            sorted_latencies = sorted(latencies)
            index = int(len(sorted_latencies) * percentile)
            return sorted_latencies[min(index, len(sorted_latencies) - 1)]
    
    def get_health(self) -> ServiceHealth:
        """Get current service health
        
        Returns:
            Current health state with metrics
        """
        uptime = (self.total_successes / self.total_checks * 100) if self.total_checks > 0 else 100.0
        
        return ServiceHealth(
            status=self.status,
            last_check=self.last_check_time or 0.0,
            consecutive_failures=self.consecutive_failures,
            total_checks=self.total_checks,
            total_successes=self.total_successes,
            total_failures=self.total_failures,
            latency_p50=self._calculate_percentile(0.50),
            latency_p95=self._calculate_percentile(0.95),
            latency_p99=self._calculate_percentile(0.99),
            uptime_percentage=uptime
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get Prometheus-compatible metrics
        
        Returns:
            Dictionary with metrics suitable for Prometheus export
        """
        health = self.get_health()
        
        return {
            "service_name": self.config.name,
            "health_status": health.status.value,
            "health_status_code": self._status_to_code(health.status),
            "total_checks": health.total_checks,
            "total_successes": health.total_successes,
            "total_failures": health.total_failures,
            "consecutive_failures": health.consecutive_failures,
            "uptime_percentage": health.uptime_percentage,
            "latency_p50_ms": health.latency_p50,
            "latency_p95_ms": health.latency_p95,
            "latency_p99_ms": health.latency_p99,
            "last_check_timestamp": health.last_check,
            "check_interval_seconds": self.config.check_interval,
        }
    
    def _status_to_code(self, status: HealthStatus) -> int:
        """Convert status to numeric code for Prometheus
        
        Args:
            status: Health status
        
        Returns:
            Numeric code (0=DEAD, 1=UNHEALTHY, 2=DEGRADED, 3=HEALTHY)
        """
        return {
            HealthStatus.DEAD: 0,
            HealthStatus.UNHEALTHY: 1,
            HealthStatus.DEGRADED: 2,
            HealthStatus.HEALTHY: 3,
        }[status]
    
    def reset(self):
        """Reset monitoring state"""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.status = HealthStatus.HEALTHY
        logger.info(f"Service monitor reset: '{self.config.name}'")
    
    def __repr__(self) -> str:
        return (
            f"ServiceMonitor(name='{self.config.name}', "
            f"status={self.status.value}, "
            f"checks={self.total_checks})"
        )
