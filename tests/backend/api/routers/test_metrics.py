"""
Tests for Prometheus Metrics Router (backend/api/routers/metrics.py)

This module tests the metrics endpoints that expose Prometheus-format metrics
for monitoring system health, cache performance, and orchestrator operations.

Test Coverage:
- GET /metrics: Orchestrator metrics in Prometheus format
- GET /metrics/cache: Cache metrics in Prometheus format  
- GET /metrics/health: Metrics system health check
- Import availability scenarios (METRICS_AVAILABLE flag)
- Error handling for metrics collection failures
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from backend.api.routers.metrics import router


@pytest.fixture
def client():
    """FastAPI test client with metrics router"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_metrics_available():
    """Mock METRICS_AVAILABLE to True"""
    with patch("backend.api.routers.metrics.METRICS_AVAILABLE", True):
        yield


@pytest.fixture
def mock_metrics_unavailable():
    """Mock METRICS_AVAILABLE to False"""
    with patch("backend.api.routers.metrics.METRICS_AVAILABLE", False):
        yield


@pytest.fixture
def mock_get_metrics():
    """Mock get_metrics() function with PrometheusMetrics instance"""
    with patch("backend.api.routers.metrics.get_metrics") as mock:
        # Create mock metrics object
        mock_metrics = AsyncMock()
        mock_metrics.queue = MagicMock()  # Simulate connected queue
        mock_metrics.counters = {
            'tasks_enqueued_total': 100,
            'tasks_completed_total': 95,
            'tasks_failed_total': 5
        }
        mock_metrics.gauges = {
            'ack_success_rate': 0.987,
            'queue_depth': 10.0,
            'active_workers': 3
        }
        mock_metrics.latency_histogram = {'default': [1, 2, 3, 4, 5]}
        
        # Mock export_prometheus method
        mock_metrics.export_prometheus = AsyncMock(
            return_value=(
                "# HELP mcp_tasks_completed_total Total tasks completed\n"
                "# TYPE mcp_tasks_completed_total counter\n"
                "mcp_tasks_completed_total 95\n"
                "# HELP mcp_ack_success_rate ACK success rate\n"
                "# TYPE mcp_ack_success_rate gauge\n"
                "mcp_ack_success_rate 0.987\n"
            )
        )
        
        mock.return_value = mock_metrics
        yield mock


@pytest.fixture
def mock_prometheus_generate_latest():
    """Mock prometheus_client.generate_latest()"""
    with patch("backend.api.routers.metrics.generate_latest") as mock:
        mock.return_value = (
            b"# HELP cache_hits_total Total cache hits\n"
            b"# TYPE cache_hits_total counter\n"
            b"cache_hits_total{level=\"l1\"} 5420\n"
            b"cache_hit_rate{level=\"overall\"} 0.958\n"
        )
        yield mock


class TestPrometheusMetricsEndpoint:
    """Tests for GET /metrics (orchestrator metrics)"""
    
    def test_metrics_success(self, client, mock_metrics_available, mock_get_metrics):
        """Should return Prometheus metrics when module available"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert "text/plain; version=0.0.4" in response.headers["content-type"]
        
        # Verify Prometheus format content
        content = response.text
        assert "mcp_tasks_completed_total 95" in content
        assert "mcp_ack_success_rate 0.987" in content
        assert "# HELP" in content
        assert "# TYPE" in content
        
        # Verify export_prometheus was called
        mock_get_metrics.return_value.export_prometheus.assert_called_once()
    
    def test_metrics_unavailable(self, client, mock_metrics_unavailable):
        """Should return unavailable message when metrics module not available"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert "text/plain; version=0.0.4" in response.headers["content-type"]
        assert "Metrics module not available" in response.text
    
    def test_metrics_export_error(self, client, mock_metrics_available, mock_get_metrics):
        """Should return 500 when export_prometheus raises exception"""
        # Mock export to raise exception
        mock_get_metrics.return_value.export_prometheus.side_effect = Exception("Redis connection lost")
        
        response = client.get("/metrics")
        
        assert response.status_code == 500
        assert "text/plain; version=0.0.4" in response.headers["content-type"]
        assert "Error exporting metrics" in response.text
        assert "Redis connection lost" in response.text
    
    def test_metrics_get_metrics_failure(self, client, mock_metrics_available):
        """Should handle get_metrics() raising exception"""
        with patch("backend.api.routers.metrics.get_metrics", side_effect=Exception("Metrics init failed")):
            response = client.get("/metrics")
            
            assert response.status_code == 500
            assert "Error exporting metrics" in response.text
    
    def test_metrics_prometheus_format(self, client, mock_metrics_available, mock_get_metrics):
        """Should return valid Prometheus text exposition format"""
        response = client.get("/metrics")
        
        # Verify Prometheus format structure
        lines = response.text.split("\n")
        
        # Should have HELP and TYPE comments
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        
        assert len(help_lines) >= 1
        assert len(type_lines) >= 1


class TestCacheMetricsEndpoint:
    """Tests for GET /metrics/cache (cache metrics)"""
    
    def test_cache_metrics_success(self, client, mock_prometheus_generate_latest):
        """Should return cache metrics in Prometheus format"""
        response = client.get("/metrics/cache")
        
        assert response.status_code == 200
        # CONTENT_TYPE_LATEST is typically "text/plain; version=0.0.4; charset=utf-8"
        assert "text/plain" in response.headers["content-type"]
        
        # Verify cache metrics content (bytes response)
        content = response.content.decode()
        assert "cache_hits_total" in content
        assert "cache_hit_rate" in content
        
        # Verify generate_latest was called
        mock_prometheus_generate_latest.assert_called_once()
    
    def test_cache_metrics_generate_error(self, client):
        """Should return 500 when generate_latest raises exception"""
        with patch("backend.api.routers.metrics.generate_latest", side_effect=Exception("Prometheus error")):
            response = client.get("/metrics/cache")
            
            assert response.status_code == 500
            assert "text/plain; version=0.0.4" in response.headers["content-type"]
            assert "Error exporting cache metrics" in response.text
            assert "Prometheus error" in response.text
    
    def test_cache_metrics_format(self, client, mock_prometheus_generate_latest):
        """Should return cache metrics with labels"""
        response = client.get("/metrics/cache")
        
        content = response.content.decode()
        
        # Verify labeled metrics (e.g., cache_hits_total{level="l1"})
        assert 'level="l1"' in content or 'level="overall"' in content


class TestMetricsHealthEndpoint:
    """Tests for GET /metrics/health (health check)"""
    
    def test_health_check_healthy(self, client, mock_metrics_available, mock_get_metrics):
        """Should return healthy status when metrics available and connected"""
        response = client.get("/metrics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["connected"] is True
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data
        
        # Verify counts match mock data
        assert data["counters"] == 3  # tasks_enqueued, completed, failed
        assert data["gauges"] == 3  # ack_success_rate, queue_depth, active_workers
        assert data["histograms"] == 1  # default histogram
    
    def test_health_check_unavailable(self, client, mock_metrics_unavailable):
        """Should return unavailable status when metrics module not available"""
        response = client.get("/metrics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unavailable"
        assert data["message"] == "Metrics module not available"
    
    def test_health_check_disconnected(self, client, mock_metrics_available, mock_get_metrics):
        """Should show connected=False when queue is None"""
        mock_get_metrics.return_value.queue = None
        
        response = client.get("/metrics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["connected"] is False
    
    def test_health_check_error(self, client, mock_metrics_available):
        """Should return error status when get_metrics raises exception"""
        with patch("backend.api.routers.metrics.get_metrics", side_effect=Exception("Init error")):
            response = client.get("/metrics/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "error"
            assert data["message"] == "Init error"
    
    def test_health_check_empty_metrics(self, client, mock_metrics_available, mock_get_metrics):
        """Should handle empty metrics collections"""
        mock_get_metrics.return_value.counters = {}
        mock_get_metrics.return_value.gauges = {}
        mock_get_metrics.return_value.latency_histogram = {}
        
        response = client.get("/metrics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["counters"] == 0
        assert data["gauges"] == 0
        assert data["histograms"] == 0


class TestMetricsIntegration:
    """Integration tests for metrics router workflows"""
    
    def test_health_then_metrics_workflow(self, client, mock_metrics_available, mock_get_metrics, mock_prometheus_generate_latest):
        """Should perform health check before fetching metrics in realistic workflow"""
        # 1. Check health
        health_response = client.get("/metrics/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"
        
        # 2. Fetch orchestrator metrics
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        assert "mcp_tasks_completed_total" in metrics_response.text
        
        # 3. Fetch cache metrics
        cache_response = client.get("/metrics/cache")
        assert cache_response.status_code == 200
        assert "cache_hits_total" in cache_response.content.decode()
    
    def test_all_endpoints_when_unavailable(self, client, mock_metrics_unavailable):
        """Should gracefully handle all endpoints when metrics unavailable"""
        # 1. Health shows unavailable
        health = client.get("/metrics/health")
        assert health.json()["status"] == "unavailable"
        
        # 2. Metrics returns unavailable message
        metrics = client.get("/metrics")
        assert "not available" in metrics.text
        
        # 3. Cache metrics still works (uses prometheus_client directly)
        with patch("backend.api.routers.metrics.generate_latest", return_value=b"cache_data"):
            cache = client.get("/metrics/cache")
            assert cache.status_code == 200
    
    def test_metrics_scraping_simulation(self, client, mock_metrics_available, mock_get_metrics):
        """Should handle multiple scraping requests (Prometheus scrape simulation)"""
        # Simulate Prometheus scraping every 15 seconds (3 requests)
        responses = []
        
        for _ in range(3):
            response = client.get("/metrics")
            responses.append(response)
        
        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Verify export_prometheus called 3 times
        assert mock_get_metrics.return_value.export_prometheus.call_count == 3


class TestPrometheusFormatValidation:
    """Tests for Prometheus format compliance"""
    
    def test_metrics_content_type_header(self, client, mock_metrics_available, mock_get_metrics):
        """Should return correct Prometheus content type"""
        response = client.get("/metrics")
        
        # Prometheus expects "text/plain; version=0.0.4" (FastAPI adds charset=utf-8)
        assert "text/plain; version=0.0.4" in response.headers["content-type"]
    
    def test_cache_metrics_content_type(self, client, mock_prometheus_generate_latest):
        """Should use CONTENT_TYPE_LATEST for cache metrics"""
        response = client.get("/metrics/cache")
        
        # CONTENT_TYPE_LATEST constant from prometheus_client
        assert "text/plain" in response.headers["content-type"]
    
    def test_error_response_format(self, client, mock_metrics_available, mock_get_metrics):
        """Should return error in Prometheus comment format"""
        mock_get_metrics.return_value.export_prometheus.side_effect = Exception("Test error")
        
        response = client.get("/metrics")
        
        assert response.status_code == 500
        # Error should be in comment format (starts with #)
        assert response.text.startswith("# Error")


class TestMetricsEdgeCases:
    """Edge case tests for metrics endpoints"""
    
    def test_metrics_with_no_data(self, client, mock_metrics_available, mock_get_metrics):
        """Should handle metrics with no data collected"""
        mock_get_metrics.return_value.export_prometheus.return_value = "# No data\n"
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert response.text == "# No data\n"
    
    def test_cache_metrics_empty_registry(self, client):
        """Should handle empty Prometheus registry"""
        with patch("backend.api.routers.metrics.generate_latest", return_value=b""):
            response = client.get("/metrics/cache")
            
            assert response.status_code == 200
            assert response.content == b""
    
    def test_health_check_partial_metrics(self, client, mock_metrics_available, mock_get_metrics):
        """Should handle metrics with some collections missing"""
        # Only counters available, no gauges/histograms
        mock_get_metrics.return_value.counters = {'test': 1}
        mock_get_metrics.return_value.gauges = {}
        mock_get_metrics.return_value.latency_histogram = {}
        
        response = client.get("/metrics/health")
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["counters"] == 1
        assert data["gauges"] == 0
        assert data["histograms"] == 0
    
    def test_concurrent_metrics_requests(self, client, mock_metrics_available, mock_get_metrics):
        """Should handle concurrent requests to different endpoints"""
        # Simulate concurrent scraping
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(client.get, "/metrics"),
                executor.submit(client.get, "/metrics/cache"),
                executor.submit(client.get, "/metrics/health")
            ]
            
            results = [f.result() for f in futures]
        
        # All requests should succeed
        assert all(r.status_code == 200 for r in results)


class TestModuleImportPath:
    """Tests for module import exception handling (lines 16-18)"""
    
    def test_import_error_handling(self):
        """Should handle ImportError when orchestrator.api.metrics is unavailable (covers lines 16-18)"""
        import sys
        import importlib
        import builtins
        
        # Remove orchestrator.api.metrics if it exists
        modules_to_remove = [
            'orchestrator.api.metrics',
            'orchestrator.api',
            'orchestrator',
            'backend.api.routers.metrics'
        ]
        for module in modules_to_remove:
            if module in sys.modules:
                del sys.modules[module]
        
        # Mock import to raise ImportError
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'orchestrator.api.metrics':
                raise ImportError("Orchestrator metrics module not available")
            return original_import(name, *args, **kwargs)
        
        # Patch import and reload module
        with patch('builtins.__import__', side_effect=mock_import):
            # Reimport module to trigger exception path
            import backend.api.routers.metrics as metrics_module
            importlib.reload(metrics_module)
            
            # Verify METRICS_AVAILABLE is False after ImportError
            assert metrics_module.METRICS_AVAILABLE is False
            
            # Test that endpoints still work with unavailable metrics
            app = FastAPI()
            app.include_router(metrics_module.router)
            client = TestClient(app)
            
            # GET /metrics should return "not available" message
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "not available" in response.text.lower()
            
            # GET /metrics/health should return unavailable status
            response = client.get("/metrics/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unavailable"
            assert "not available" in data["message"].lower()
