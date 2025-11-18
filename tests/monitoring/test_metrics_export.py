"""
Test Prometheus Metrics Export
================================

Tests for metrics collectors and Prometheus integration.
"""

import pytest
import time
from prometheus_client import REGISTRY, CollectorRegistry
from automation.metrics.custom_metrics import (
    test_watcher_metrics,
    audit_agent_metrics,
    safe_async_bridge_metrics,
    api_metrics
)
from automation.metrics.collectors import (
    TestWatcherCollector,
    AuditAgentCollector,
    SystemCollector
)


class TestMetricsDefinitions:
    """Test that all metrics are properly defined."""
    
    def test_test_watcher_metrics_exist(self):
        """Verify TestWatcher metrics are defined."""
        metrics = test_watcher_metrics
        
        # Counter metrics
        assert hasattr(metrics, 'files_processed')
        assert hasattr(metrics, 'tests_run')
        assert hasattr(metrics, 'api_calls')
        assert hasattr(metrics, 'errors')
        
        # Gauge metrics
        assert hasattr(metrics, 'changed_files_current')
        assert hasattr(metrics, 'memory_usage')
        assert hasattr(metrics, 'is_running')
        
        # Histogram metrics
        assert hasattr(metrics, 'processing_duration')
        assert hasattr(metrics, 'debounce_duration')
        assert hasattr(metrics, 'test_execution_duration')
    
    def test_audit_agent_metrics_exist(self):
        """Verify AuditAgent metrics are defined."""
        metrics = audit_agent_metrics
        
        # Counter metrics
        assert hasattr(metrics, 'runs_total')
        assert hasattr(metrics, 'completion_markers_found')
        assert hasattr(metrics, 'git_commits_detected')
        assert hasattr(metrics, 'errors')
        
        # Gauge metrics
        assert hasattr(metrics, 'coverage_percent')
        assert hasattr(metrics, 'last_run_timestamp')
        assert hasattr(metrics, 'active_tasks')
        
        # Histogram metrics
        assert hasattr(metrics, 'run_duration')
        assert hasattr(metrics, 'analysis_duration')
    
    def test_safe_async_bridge_metrics_exist(self):
        """Verify SafeAsyncBridge metrics are defined."""
        metrics = safe_async_bridge_metrics
        
        # Counter metrics
        assert hasattr(metrics, 'calls_total')
        assert hasattr(metrics, 'errors')
        assert hasattr(metrics, 'timeouts')
        
        # Gauge metrics
        assert hasattr(metrics, 'pending_tasks')
        assert hasattr(metrics, 'active_loops')
        
        # Histogram metrics
        assert hasattr(metrics, 'execution_duration')
    
    def test_api_metrics_exist(self):
        """Verify API metrics are defined."""
        metrics = api_metrics
        
        # Counter metrics
        assert hasattr(metrics, 'deepseek_calls')
        assert hasattr(metrics, 'perplexity_calls')
        assert hasattr(metrics, 'rate_limits')
        assert hasattr(metrics, 'errors')
        assert hasattr(metrics, 'tokens_used')
        
        # Gauge metrics
        assert hasattr(metrics, 'deepseek_response_time')
        assert hasattr(metrics, 'perplexity_response_time')
        
        # Histogram metrics
        assert hasattr(metrics, 'request_duration')


class TestTestWatcherCollector:
    """Test TestWatcher metrics collector."""
    
    def test_collector_initialization(self):
        """Test collector can be initialized."""
        collector = TestWatcherCollector()
        assert collector is not None
        assert collector.metrics is not None
    
    def test_record_file_processed(self):
        """Test recording file processing."""
        collector = TestWatcherCollector()
        
        # Get initial value
        before = collector.metrics.files_processed._value.get()
        
        # Record processing
        collector.record_file_processed()
        
        # Verify increment
        after = collector.metrics.files_processed._value.get()
        assert after == before + 1
    
    def test_record_test_run(self):
        """Test recording test runs with different statuses."""
        collector = TestWatcherCollector()
        
        # Record various test statuses
        collector.record_test_run('pass')
        collector.record_test_run('fail')
        collector.record_test_run('error')
        
        # Metrics should be recorded (exact values depend on other tests)
        # Just verify no errors occur
        assert True
    
    def test_record_api_call(self):
        """Test recording API calls."""
        collector = TestWatcherCollector()
        
        # Record API calls
        collector.record_api_call('deepseek', 'success', 1.5)
        collector.record_api_call('perplexity', 'error', 0.5)
        
        # Verify no errors
        assert True
    
    def test_update_changed_files_count(self):
        """Test updating changed files count."""
        collector = TestWatcherCollector()
        
        collector.update_changed_files_count(5)
        assert collector.metrics.changed_files_current._value.get() == 5
        
        collector.update_changed_files_count(10)
        assert collector.metrics.changed_files_current._value.get() == 10
    
    def test_set_running_status(self):
        """Test setting running status."""
        collector = TestWatcherCollector()
        
        collector.set_running_status(True)
        assert collector.metrics.is_running._value.get() == 1
        
        collector.set_running_status(False)
        assert collector.metrics.is_running._value.get() == 0
    
    def test_timing_context_managers(self):
        """Test timing context managers."""
        collector = TestWatcherCollector()
        
        # Test processing timer
        with collector.time_processing():
            time.sleep(0.1)
        
        # Test debounce timer
        with collector.time_debounce():
            time.sleep(0.05)
        
        # Test execution timer
        with collector.time_test_execution():
            time.sleep(0.01)
        
        # Verify no errors occurred
        assert True


class TestAuditAgentCollector:
    """Test AuditAgent metrics collector."""
    
    def test_collector_initialization(self):
        """Test collector can be initialized."""
        collector = AuditAgentCollector()
        assert collector is not None
        assert collector.metrics is not None
    
    def test_record_run(self):
        """Test recording audit runs."""
        collector = AuditAgentCollector()
        
        # Record runs with different triggers
        collector.record_run('scheduled')
        collector.record_run('manual')
        collector.record_run('marker_detected')
        
        # Verify last_run_timestamp was updated
        timestamp = collector.metrics.last_run_timestamp._value.get()
        assert timestamp > 0
        assert abs(timestamp - time.time()) < 1.0
    
    def test_record_completion_marker(self):
        """Test recording completion marker detection."""
        collector = AuditAgentCollector()
        
        before = collector.metrics.completion_markers_found._value.get()
        collector.record_completion_marker_found()
        after = collector.metrics.completion_markers_found._value.get()
        
        assert after == before + 1
    
    def test_update_coverage(self):
        """Test updating coverage percentage."""
        collector = AuditAgentCollector()
        
        collector.update_coverage(85.5)
        assert collector.metrics.coverage_percent._value.get() == 85.5
        
        collector.update_coverage(92.3)
        assert collector.metrics.coverage_percent._value.get() == 92.3
    
    def test_timing_context_managers(self):
        """Test timing context managers."""
        collector = AuditAgentCollector()
        
        # Test run timer
        with collector.time_run():
            time.sleep(0.1)
        
        # Test analysis timer
        with collector.time_analysis():
            time.sleep(0.05)
        
        # Verify no errors occurred
        assert True


class TestSystemCollector:
    """Test system metrics collector."""
    
    def test_collector_initialization(self):
        """Test collector can be initialized."""
        collector = SystemCollector()
        assert collector is not None
        assert collector.process is not None
    
    def test_collect_cpu(self):
        """Test CPU metrics collection."""
        collector = SystemCollector()
        
        collector.collect_cpu()
        
        # Verify metrics were set
        cpu_percent = collector.cpu_percent._value.get()
        assert 0 <= cpu_percent <= 100
        
        process_cpu = collector.process_cpu._value.get()
        assert process_cpu >= 0
    
    def test_collect_memory(self):
        """Test memory metrics collection."""
        collector = SystemCollector()
        
        collector.collect_memory()
        
        # Verify metrics were set
        mem_percent = collector.memory_percent._value.get()
        assert 0 <= mem_percent <= 100
        
        process_mem = collector.process_memory._value.get()
        assert process_mem > 0
    
    def test_collect_disk(self):
        """Test disk metrics collection."""
        collector = SystemCollector()
        
        collector.collect_disk()
        
        # Verify no errors (disk metrics use labels, harder to check exact values)
        assert True
    
    def test_collect_process(self):
        """Test process metrics collection."""
        collector = SystemCollector()
        
        collector.collect_process()
        
        # Verify thread count
        threads = collector.process_threads._value.get()
        assert threads > 0
    
    def test_collect_all(self):
        """Test collecting all metrics at once."""
        collector = SystemCollector()
        
        # Should not raise any errors
        collector.collect_all()
        
        # Verify some metrics were set
        assert collector.cpu_percent._value.get() >= 0
        assert collector.memory_percent._value.get() > 0
        assert collector.process_memory._value.get() > 0


class TestPrometheusIntegration:
    """Test Prometheus registry integration."""
    
    def test_metrics_registered_in_registry(self):
        """Test that metrics are registered in Prometheus registry."""
        # Get all registered metric names
        metric_families = list(REGISTRY.collect())
        metric_names = [family.name for family in metric_families]
        
        # Check for some of our custom metrics
        # NOTE: Counter metrics don't include '_total' suffix in registry
        # Prometheus adds it during scraping
        expected_metrics = [
            'test_watcher_files_processed',  # Counter (no _total in registry)
            'audit_agent_runs',              # Counter (no _total in registry)
            'safe_async_bridge_calls',       # Counter (no _total in registry)
            'deepseek_api_calls',            # Counter (no _total in registry)
        ]
        
        for metric_name in expected_metrics:
            assert metric_name in metric_names, f"Metric {metric_name} not found in registry"
    
    def test_metrics_can_be_scraped(self):
        """Test that metrics can be exported for scraping."""
        from prometheus_client import generate_latest
        
        # Generate metrics output
        output = generate_latest(REGISTRY)
        
        # Verify output format
        assert output is not None
        assert len(output) > 0
        
        # Check for some expected metric names in output
        output_str = output.decode('utf-8')
        
        # Counter metrics should have _total suffix in scraped output
        assert 'test_watcher_files_processed_total' in output_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
