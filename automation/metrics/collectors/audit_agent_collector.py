"""
AuditAgent Metrics Collector
=============================

Collects metrics from AuditAgent component.
"""

import logging
import time
from typing import Optional
from ..custom_metrics import audit_agent_metrics

logger = logging.getLogger(__name__)


class AuditAgentCollector:
    """
    Collects and reports AuditAgent metrics.
    
    Tracks audit runs, completion markers, coverage, and performance.
    """
    
    def __init__(self, audit_agent=None):
        """
        Initialize collector.
        
        Args:
            audit_agent: AuditAgent instance (optional)
        """
        self.audit_agent = audit_agent
        self.metrics = audit_agent_metrics
        
        logger.info("✅ AuditAgent metrics collector initialized")
    
    def record_run(self, trigger: str):
        """
        Record an audit run.
        
        Args:
            trigger: What triggered the run (scheduled, manual, marker_detected)
        """
        self.metrics.runs_total.labels(trigger=trigger).inc()
        self.metrics.last_run_timestamp.set(time.time())
    
    def record_completion_marker_found(self):
        """Record detection of a completion marker."""
        self.metrics.completion_markers_found.inc()
    
    def record_git_commit_detected(self):
        """Record detection of a git commit."""
        self.metrics.git_commits_detected.inc()
    
    def record_error(self, error_type: str):
        """
        Record an error during audit.
        
        Args:
            error_type: Type of error encountered
        """
        self.metrics.errors.labels(error_type=error_type).inc()
    
    def update_coverage(self, coverage_percent: float):
        """
        Update test coverage percentage.
        
        Args:
            coverage_percent: Coverage value (0-100)
        """
        self.metrics.coverage_percent.set(coverage_percent)
    
    def update_active_tasks(self, count: int):
        """
        Update active tasks count.
        
        Args:
            count: Number of active audit tasks
        """
        self.metrics.active_tasks.set(count)
    
    def time_run(self):
        """
        Context manager for timing audit run duration.
        
        Returns:
            Timer context manager
        """
        return self.metrics.run_duration.time()
    
    def time_analysis(self):
        """
        Context manager for timing analysis duration.
        
        Returns:
            Timer context manager
        """
        return self.metrics.analysis_duration.time()
    
    def collect_all(self):
        """Collect all current metrics (for manual reporting)."""
        # Update last run timestamp
        self.metrics.last_run_timestamp.set(time.time())
        
        if self.audit_agent:
            # Update active tasks if agent is available
            try:
                active = getattr(self.audit_agent, 'active_tasks', 0)
                self.update_active_tasks(active)
            except Exception as e:
                logger.debug(f"Could not get active_tasks count: {e}")
