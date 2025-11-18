"""
TestWatcher Metrics Collector
==============================

Collects metrics from TestWatcher component.
"""

import logging
import time
import psutil
import os
from typing import Optional
from ..custom_metrics import test_watcher_metrics

logger = logging.getLogger(__name__)


class TestWatcherCollector:
    """
    Collects and reports TestWatcher metrics.
    
    Integrates with TestWatcher to track file processing,
    test execution, and API calls.
    """
    
    def __init__(self, test_watcher=None):
        """
        Initialize collector.
        
        Args:
            test_watcher: TestWatcher instance (optional)
        """
        self.test_watcher = test_watcher
        self.metrics = test_watcher_metrics
        self.process = psutil.Process(os.getpid())
        
        logger.info("✅ TestWatcher metrics collector initialized")
    
    def record_file_processed(self):
        """Record a file being processed."""
        self.metrics.files_processed.inc()
    
    def record_test_run(self, status: str):
        """
        Record a test run.
        
        Args:
            status: Test status (pass, fail, error)
        """
        self.metrics.tests_run.labels(status=status).inc()
    
    def record_api_call(self, api: str, status: str, duration: float):
        """
        Record an API call.
        
        Args:
            api: API name (deepseek, perplexity)
            status: Call status (success, error)
            duration: Call duration in seconds
        """
        self.metrics.api_calls.labels(api=api, status=status).inc()
    
    def record_error(self, error_type: str):
        """
        Record an error.
        
        Args:
            error_type: Type of error encountered
        """
        self.metrics.errors.labels(error_type=error_type).inc()
    
    def update_changed_files_count(self, count: int):
        """
        Update current changed files count.
        
        Args:
            count: Number of files in change queue
        """
        self.metrics.changed_files_current.set(count)
    
    def update_memory_usage(self):
        """Update current memory usage."""
        memory_bytes = self.process.memory_info().rss
        self.metrics.memory_usage.set(memory_bytes)
    
    def set_running_status(self, is_running: bool):
        """
        Set running status.
        
        Args:
            is_running: Whether TestWatcher is running
        """
        self.metrics.is_running.set(1 if is_running else 0)
    
    def time_processing(self):
        """
        Context manager for timing processing duration.
        
        Returns:
            Timer context manager
        """
        return self.metrics.processing_duration.time()
    
    def time_debounce(self):
        """
        Context manager for timing debounce duration.
        
        Returns:
            Timer context manager
        """
        return self.metrics.debounce_duration.time()
    
    def time_test_execution(self):
        """
        Context manager for timing test execution.
        
        Returns:
            Timer context manager
        """
        return self.metrics.test_execution_duration.time()
    
    def collect_all(self):
        """Collect all current metrics (for manual reporting)."""
        self.update_memory_usage()
        
        if self.test_watcher:
            # Update changed files count if watcher is available
            try:
                changed_files = getattr(self.test_watcher, 'changed_files', set())
                self.update_changed_files_count(len(changed_files))
            except Exception as e:
                logger.debug(f"Could not get changed_files count: {e}")
