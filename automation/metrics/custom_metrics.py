"""
Custom Prometheus Metrics
==========================

Defines all custom metrics for the automation platform.
"""

from prometheus_client import Counter, Gauge, Histogram, Summary
import time


# ============================================================
# TestWatcher Metrics
# ============================================================

class TestWatcherMetrics:
    """Metrics for TestWatcher component."""
    
    def __init__(self):
        # Counter metrics
        self.files_processed = Counter(
            'test_watcher_files_processed_total',
            'Total number of files processed by TestWatcher'
        )
        
        self.tests_run = Counter(
            'test_watcher_tests_run_total',
            'Total number of test runs executed',
            ['status']  # pass, fail, error
        )
        
        self.api_calls = Counter(
            'test_watcher_api_calls_total',
            'Total number of API calls made',
            ['api', 'status']  # deepseek/perplexity, success/error
        )
        
        self.errors = Counter(
            'test_watcher_errors_total',
            'Total number of errors encountered',
            ['error_type']
        )
        
        # Gauge metrics
        self.changed_files_current = Gauge(
            'test_watcher_changed_files_current',
            'Current number of files in change queue'
        )
        
        self.memory_usage = Gauge(
            'test_watcher_memory_usage_bytes',
            'Current memory usage in bytes'
        )
        
        self.is_running = Gauge(
            'test_watcher_is_running',
            'Whether TestWatcher is currently running (1=running, 0=stopped)'
        )
        
        # Histogram metrics
        self.processing_duration = Histogram(
            'test_watcher_processing_duration_seconds',
            'Time spent processing file changes',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.debounce_duration = Histogram(
            'test_watcher_debounce_duration_seconds',
            'Time spent waiting during debounce',
            buckets=[0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
        )
        
        self.test_execution_duration = Histogram(
            'test_watcher_test_execution_duration_seconds',
            'Time spent executing tests',
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
        )


# ============================================================
# AuditAgent Metrics
# ============================================================

class AuditAgentMetrics:
    """Metrics for AuditAgent component."""
    
    def __init__(self):
        # Counter metrics
        self.runs_total = Counter(
            'audit_agent_runs_total',
            'Total number of audit runs',
            ['trigger']  # scheduled, manual, marker_detected
        )
        
        self.completion_markers_found = Counter(
            'audit_agent_completion_markers_found_total',
            'Total number of completion markers detected'
        )
        
        self.git_commits_detected = Counter(
            'audit_agent_git_commits_detected_total',
            'Total number of git commits analyzed'
        )
        
        self.errors = Counter(
            'audit_agent_errors_total',
            'Total number of errors during audits',
            ['error_type']
        )
        
        # Gauge metrics
        self.coverage_percent = Gauge(
            'audit_agent_coverage_percent',
            'Current test coverage percentage'
        )
        
        self.last_run_timestamp = Gauge(
            'audit_agent_last_run_timestamp',
            'Timestamp of last audit run'
        )
        
        self.active_tasks = Gauge(
            'audit_agent_active_tasks_count',
            'Number of currently active audit tasks'
        )
        
        # Histogram metrics
        self.run_duration = Histogram(
            'audit_agent_run_duration_seconds',
            'Total duration of audit runs',
            buckets=[10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0]
        )
        
        self.analysis_duration = Histogram(
            'audit_agent_analysis_duration_seconds',
            'Time spent analyzing results',
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )


# ============================================================
# SafeAsyncBridge Metrics
# ============================================================

class SafeAsyncBridgeMetrics:
    """Metrics for SafeAsyncBridge component."""
    
    def __init__(self):
        # Counter metrics
        self.calls_total = Counter(
            'safe_async_bridge_calls_total',
            'Total number of async bridge calls',
            ['function_name']
        )
        
        self.errors = Counter(
            'safe_async_bridge_errors_total',
            'Total number of errors in async bridge',
            ['error_type']
        )
        
        self.timeouts = Counter(
            'safe_async_bridge_timeouts_total',
            'Total number of timeout errors'
        )
        
        # Gauge metrics
        self.pending_tasks = Gauge(
            'safe_async_bridge_pending_tasks',
            'Number of pending async tasks'
        )
        
        self.active_loops = Gauge(
            'safe_async_bridge_active_loops',
            'Number of active event loops'
        )
        
        # Histogram metrics
        self.execution_duration = Histogram(
            'safe_async_bridge_execution_duration_seconds',
            'Execution time for async calls',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )


# ============================================================
# API Metrics
# ============================================================

class APIMetrics:
    """Metrics for external API calls."""
    
    def __init__(self):
        # Counter metrics
        self.deepseek_calls = Counter(
            'deepseek_api_calls_total',
            'Total number of DeepSeek API calls',
            ['status']  # success, error, rate_limit
        )
        
        self.perplexity_calls = Counter(
            'perplexity_api_calls_total',
            'Total number of Perplexity API calls',
            ['status']
        )
        
        self.rate_limits = Counter(
            'api_rate_limits_total',
            'Total number of rate limit hits',
            ['api']
        )
        
        self.errors = Counter(
            'api_errors_total',
            'Total number of API errors',
            ['api', 'error_type']
        )
        
        # Gauge metrics
        self.deepseek_response_time = Gauge(
            'deepseek_api_response_time_seconds',
            'Last DeepSeek API response time'
        )
        
        self.perplexity_response_time = Gauge(
            'perplexity_api_response_time_seconds',
            'Last Perplexity API response time'
        )
        
        self.tokens_used = Counter(
            'api_tokens_used_total',
            'Total number of API tokens consumed',
            ['api']
        )
        
        # Histogram metrics
        self.request_duration = Histogram(
            'api_request_duration_seconds',
            'API request duration',
            ['api'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )


# ============================================================
# Global Instances
# ============================================================

test_watcher_metrics = TestWatcherMetrics()
audit_agent_metrics = AuditAgentMetrics()
safe_async_bridge_metrics = SafeAsyncBridgeMetrics()
api_metrics = APIMetrics()
