"""
Resource Limiter - Runtime monitoring and enforcement of resource constraints
"""

import asyncio
import psutil
import time
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger('sandbox.resources')


@dataclass
class ResourceLimits:
    """Resource limit configuration"""
    max_cpu_percent: float = 100.0  # Maximum CPU usage percentage
    max_memory_mb: int = 512        # Maximum memory in MB
    max_execution_time: int = 30    # Maximum execution time in seconds
    max_io_operations: int = 1000   # Maximum file I/O operations


@dataclass
class ResourceUsage:
    """Current resource usage snapshot"""
    cpu_percent: float
    memory_mb: float
    execution_time: float
    io_operations: int
    timestamp: float


class ResourceLimiter:
    """
    Runtime resource monitoring and enforcement for sandboxed code execution.
    
    Monitors:
    - CPU usage
    - Memory consumption
    - Execution time
    - I/O operations
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        """
        Initialize resource limiter.
        
        Args:
            limits: Resource limit configuration
        """
        self.limits = limits or ResourceLimits()
        self.start_time: Optional[float] = None
        self.usage_history: list = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._violation_detected = False
    
    async def start_monitoring(self, container_id: str, interval: float = 0.5) -> None:
        """
        Start monitoring container resources.
        
        Args:
            container_id: Docker container ID to monitor
            interval: Monitoring interval in seconds
        """
        self.start_time = time.time()
        self._monitoring_task = asyncio.create_task(
            self._monitor_loop(container_id, interval)
        )
    
    async def stop_monitoring(self) -> None:
        """Stop resource monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self, container_id: str, interval: float) -> None:
        """Internal monitoring loop"""
        import docker
        client = docker.from_env()
        
        try:
            container = client.containers.get(container_id)
            
            while True:
                try:
                    # Get container stats
                    stats = container.stats(stream=False)
                    
                    # Calculate CPU usage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                                stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                   stats['precpu_stats']['system_cpu_usage']
                    cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
                    
                    # Calculate memory usage
                    memory_usage = stats['memory_stats'].get('usage', 0)
                    memory_mb = memory_usage / (1024 * 1024)
                    
                    # Calculate execution time
                    execution_time = time.time() - self.start_time
                    
                    # Record usage
                    usage = ResourceUsage(
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                        execution_time=execution_time,
                        io_operations=0,  # TODO: Implement I/O tracking
                        timestamp=time.time()
                    )
                    self.usage_history.append(usage)
                    
                    # Check for violations
                    if self._check_violations(usage):
                        self._violation_detected = True
                        logger.warning(f"Resource violation detected: {usage}")
                        break
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error monitoring container {container_id}: {e}")
                    break
                    
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
    
    def _check_violations(self, usage: ResourceUsage) -> bool:
        """
        Check if current usage violates limits.
        
        Args:
            usage: Current resource usage
            
        Returns:
            True if violation detected
        """
        violations = []
        
        if usage.cpu_percent > self.limits.max_cpu_percent:
            violations.append(f"CPU usage {usage.cpu_percent:.1f}% exceeds limit {self.limits.max_cpu_percent}%")
        
        if usage.memory_mb > self.limits.max_memory_mb:
            violations.append(f"Memory usage {usage.memory_mb:.1f}MB exceeds limit {self.limits.max_memory_mb}MB")
        
        if usage.execution_time > self.limits.max_execution_time:
            violations.append(f"Execution time {usage.execution_time:.1f}s exceeds limit {self.limits.max_execution_time}s")
        
        if usage.io_operations > self.limits.max_io_operations:
            violations.append(f"I/O operations {usage.io_operations} exceeds limit {self.limits.max_io_operations}")
        
        if violations:
            for violation in violations:
                logger.warning(f"VIOLATION: {violation}")
            return True
        
        return False
    
    def has_violations(self) -> bool:
        """Check if any violations were detected"""
        return self._violation_detected
    
    def get_peak_usage(self) -> Optional[ResourceUsage]:
        """
        Get peak resource usage during monitoring.
        
        Returns:
            ResourceUsage with peak values, or None if no history
        """
        if not self.usage_history:
            return None
        
        peak_cpu = max(self.usage_history, key=lambda x: x.cpu_percent)
        peak_memory = max(self.usage_history, key=lambda x: x.memory_mb)
        peak_time = self.usage_history[-1]
        
        return ResourceUsage(
            cpu_percent=peak_cpu.cpu_percent,
            memory_mb=peak_memory.memory_mb,
            execution_time=peak_time.execution_time,
            io_operations=max(u.io_operations for u in self.usage_history),
            timestamp=time.time()
        )
    
    def get_average_usage(self) -> Optional[ResourceUsage]:
        """
        Get average resource usage during monitoring.
        
        Returns:
            ResourceUsage with average values, or None if no history
        """
        if not self.usage_history:
            return None
        
        n = len(self.usage_history)
        
        return ResourceUsage(
            cpu_percent=sum(u.cpu_percent for u in self.usage_history) / n,
            memory_mb=sum(u.memory_mb for u in self.usage_history) / n,
            execution_time=self.usage_history[-1].execution_time,
            io_operations=sum(u.io_operations for u in self.usage_history),
            timestamp=time.time()
        )
    
    def get_usage_report(self) -> Dict:
        """
        Generate comprehensive usage report.
        
        Returns:
            Dict with usage statistics
        """
        if not self.usage_history:
            return {
                'status': 'no_data',
                'message': 'No usage data collected'
            }
        
        peak = self.get_peak_usage()
        average = self.get_average_usage()
        
        return {
            'status': 'violation' if self._violation_detected else 'ok',
            'limits': {
                'cpu_percent': self.limits.max_cpu_percent,
                'memory_mb': self.limits.max_memory_mb,
                'execution_time': self.limits.max_execution_time,
                'io_operations': self.limits.max_io_operations
            },
            'peak_usage': {
                'cpu_percent': peak.cpu_percent,
                'memory_mb': peak.memory_mb,
                'execution_time': peak.execution_time,
                'io_operations': peak.io_operations
            },
            'average_usage': {
                'cpu_percent': average.cpu_percent,
                'memory_mb': average.memory_mb,
                'execution_time': average.execution_time,
                'io_operations': average.io_operations
            },
            'samples_collected': len(self.usage_history),
            'monitoring_duration': self.usage_history[-1].execution_time if self.usage_history else 0
        }
    
    def format_report(self) -> str:
        """Format usage report as human-readable string"""
        report_data = self.get_usage_report()
        
        if report_data['status'] == 'no_data':
            return report_data['message']
        
        lines = []
        lines.append("Resource Usage Report")
        lines.append("=" * 50)
        lines.append(f"Status: {'❌ VIOLATION' if report_data['status'] == 'violation' else '✅ OK'}")
        lines.append(f"\nLimits:")
        lines.append(f"  CPU: {report_data['limits']['cpu_percent']}%")
        lines.append(f"  Memory: {report_data['limits']['memory_mb']}MB")
        lines.append(f"  Time: {report_data['limits']['execution_time']}s")
        
        lines.append(f"\nPeak Usage:")
        lines.append(f"  CPU: {report_data['peak_usage']['cpu_percent']:.1f}%")
        lines.append(f"  Memory: {report_data['peak_usage']['memory_mb']:.1f}MB")
        lines.append(f"  Time: {report_data['peak_usage']['execution_time']:.2f}s")
        
        lines.append(f"\nAverage Usage:")
        lines.append(f"  CPU: {report_data['average_usage']['cpu_percent']:.1f}%")
        lines.append(f"  Memory: {report_data['average_usage']['memory_mb']:.1f}MB")
        
        lines.append(f"\nMonitoring:")
        lines.append(f"  Samples: {report_data['samples_collected']}")
        lines.append(f"  Duration: {report_data['monitoring_duration']:.2f}s")
        
        return '\n'.join(lines)
