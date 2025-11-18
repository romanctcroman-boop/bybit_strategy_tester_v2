"""
System Metrics Collector
=========================

Collects system-level metrics (CPU, memory, disk).
"""

import logging
import psutil
import os
from prometheus_client import Gauge

logger = logging.getLogger(__name__)


# ============================================================
# Global System Metrics (singleton pattern)
# ============================================================

# System metrics (created once globally)
_system_cpu_percent = Gauge(
    'system_cpu_percent',
    'System CPU usage percentage'
)

_system_memory_percent = Gauge(
    'system_memory_percent',
    'System memory usage percentage'
)

_system_disk_percent = Gauge(
    'system_disk_percent',
    'System disk usage percentage',
    ['path']
)

_process_cpu = Gauge(
    'process_cpu_seconds_total',
    'Total process CPU time'
)

_process_memory = Gauge(
    'process_resident_memory_bytes',
    'Process resident memory in bytes'
)

_process_open_fds = Gauge(
    'process_open_file_descriptors',
    'Number of open file descriptors'
)

_process_threads = Gauge(
    'process_threads_count',
    'Number of process threads'
)


class SystemCollector:
    """
    Collects system-level metrics.
    
    Monitors CPU, memory, disk usage, and other system resources.
    Uses global metrics to avoid duplicate registration.
    """
    
    def __init__(self):
        """Initialize system metrics collector."""
        self.process = psutil.Process(os.getpid())
        
        # Reference global metrics
        self.cpu_percent = _system_cpu_percent
        self.memory_percent = _system_memory_percent
        self.disk_percent = _system_disk_percent
        self.process_cpu = _process_cpu
        self.process_memory = _process_memory
        self.process_open_fds = _process_open_fds
        self.process_threads = _process_threads
        
        logger.info("✅ System metrics collector initialized")
    
    def collect_cpu(self):
        """Collect CPU metrics."""
        # System CPU
        self.cpu_percent.set(psutil.cpu_percent(interval=0.1))
        
        # Process CPU
        cpu_times = self.process.cpu_times()
        self.process_cpu.set(cpu_times.user + cpu_times.system)
    
    def collect_memory(self):
        """Collect memory metrics."""
        # System memory
        mem = psutil.virtual_memory()
        self.memory_percent.set(mem.percent)
        
        # Process memory
        mem_info = self.process.memory_info()
        self.process_memory.set(mem_info.rss)
    
    def collect_disk(self, paths=None):
        """
        Collect disk metrics.
        
        Args:
            paths: List of paths to monitor (default: current working directory)
        """
        if paths is None:
            paths = [os.getcwd()]
        
        for path in paths:
            try:
                usage = psutil.disk_usage(path)
                self.disk_percent.labels(path=path).set(usage.percent)
            except Exception as e:
                logger.debug(f"Could not get disk usage for {path}: {e}")
    
    def collect_process(self):
        """Collect process-level metrics."""
        try:
            # Open file descriptors (Unix-like systems)
            if hasattr(self.process, 'num_fds'):
                self.process_open_fds.set(self.process.num_fds())
        except Exception as e:
            logger.debug(f"Could not get open FDs: {e}")
        
        # Thread count
        self.process_threads.set(self.process.num_threads())
    
    def collect_all(self):
        """Collect all system metrics."""
        self.collect_cpu()
        self.collect_memory()
        self.collect_disk()
        self.collect_process()
        
        logger.debug("System metrics collected")
