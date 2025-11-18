"""
Comprehensive tests for health check router endpoints.

Tests cover:
- Overall health check (Bybit, DB, Cache)
- Bybit API detailed health
- Kubernetes readiness/liveness probes
- Database pool monitoring
- Prometheus metrics endpoint
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from backend.api.app import app
from backend.api.routers import health as health_router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def health_dependency_overrides():
    """Register default dependency overrides for the health router and expose stubs."""
    # Bybit adapter stub
    bybit_adapter = MagicMock()
    bybit_adapter.get_klines.return_value = [
        {
            'open_time': '2025-11-13T10:00:00Z',
            'open': '37000.0',
            'high': '37100.0',
            'low': '36900.0',
            'close': '37050.0',
            'volume': '123.45'
        }
    ] * 10

    def _adapter_factory():
        return bybit_adapter

    app.dependency_overrides[health_router.get_bybit_adapter_dependency] = lambda: _adapter_factory

    # Database session stub
    db_session = MagicMock()
    db_session.execute.return_value = MagicMock()
    db_session.close = MagicMock()

    def _session_factory():
        return db_session

    app.dependency_overrides[health_router.get_db_session_dependency] = lambda: _session_factory

    # Pool monitor stub
    pool_monitor = MagicMock()
    pool_monitor.get_pool_statistics.return_value = {
        'size': 10,
        'checked_in': 8,
        'checked_out': 2,
        'overflow': 0,
        'max_overflow': 5,
        'utilization': 20.0,
        'health': 'healthy',
        'timeout': 30,
        'recycle': 3600,
        'pre_ping': True
    }
    pool_monitor.get_recommendations.return_value = [
        "Pool is healthy",
        "Consider increasing pool size if utilization exceeds 80%"
    ]
    pool_monitor.check_connection_leaks.return_value = False

    def _pool_monitor_factory():
        return pool_monitor

    app.dependency_overrides[health_router.get_pool_monitor_dependency] = lambda: _pool_monitor_factory

    # Prometheus metrics generator stub
    metrics_generator = MagicMock(return_value=b"# HELP metric_name Metric description\nmetric_name 42\n")
    app.dependency_overrides[health_router.get_metrics_generator_dependency] = lambda: metrics_generator

    yield {
        "bybit_adapter": bybit_adapter,
        "db_session": db_session,
        "pool_monitor": pool_monitor,
        "metrics_generator": metrics_generator,
    }

    app.dependency_overrides.pop(health_router.get_bybit_adapter_dependency, None)
    app.dependency_overrides.pop(health_router.get_db_session_dependency, None)
    app.dependency_overrides.pop(health_router.get_pool_monitor_dependency, None)
    app.dependency_overrides.pop(health_router.get_metrics_generator_dependency, None)


@pytest.fixture
def mock_bybit_adapter(health_dependency_overrides):
    return health_dependency_overrides["bybit_adapter"]


@pytest.fixture
def mock_database(health_dependency_overrides):
    return health_dependency_overrides["db_session"]


@pytest.fixture
def mock_cache_dir():
    """Mock cache directory checks"""
    with patch("os.path.exists") as mock_exists, \
         patch("os.listdir") as mock_listdir:
        # Default: cache directory exists with 50 files
        mock_exists.return_value = True
        mock_listdir.return_value = ['file1.pkl', 'file2.pkl'] * 25  # 50 files
        
        yield {"exists": mock_exists, "listdir": mock_listdir}


@pytest.fixture
def mock_pool_monitor(health_dependency_overrides):
    return health_dependency_overrides["pool_monitor"]


@pytest.fixture
def mock_prometheus(health_dependency_overrides):
    return health_dependency_overrides["metrics_generator"]


# ============================================================================
# Test Class: Overall Health Check
# ============================================================================

class TestHealthCheck:
    """Tests for GET /api/v1/health endpoint"""
    
    def test_health_check_all_healthy(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should return 200 when all components are healthy"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Overall status
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "checks" in data
        assert "config" in data
        
        # Bybit API check
        assert data["checks"]["bybit_api"]["status"] == "ok"
        assert data["checks"]["bybit_api"]["candles_fetched"] == 10
        assert "response_time_ms" in data["checks"]["bybit_api"]
        
        # Database check
        assert data["checks"]["database"]["status"] == "ok"
        assert data["checks"]["database"]["message"] == "Database connection successful"
        
        # Cache check
        assert data["checks"]["cache"]["status"] == "ok"
        assert data["checks"]["cache"]["cache_files"] == 50
    
    def test_health_check_bybit_degraded(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should return degraded status when Bybit returns no data"""
        # Simulate empty candles response
        mock_bybit_adapter.get_klines.return_value = []
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["checks"]["bybit_api"]["status"] == "degraded"
        assert data["checks"]["bybit_api"]["candles_fetched"] == 0
    
    def test_health_check_bybit_error(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should return 503 when Bybit API fails"""
        # Simulate API exception
        mock_bybit_adapter.get_klines.side_effect = Exception("API connection timeout")
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 503
        data = response.json()["detail"]
        
        assert data["status"] == "unhealthy"
        assert data["checks"]["bybit_api"]["status"] == "error"
        assert "API connection timeout" in data["checks"]["bybit_api"]["error"]
        assert data["checks"]["bybit_api"]["error_type"] == "Exception"
    
    def test_health_check_database_error(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should return 503 when database fails"""
        # Simulate database exception
        from sqlalchemy.exc import OperationalError
        mock_database.execute.side_effect = OperationalError("statement", "params", "orig")
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 503
        data = response.json()["detail"]
        
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "error"
        assert data["checks"]["database"]["error_type"] == "OperationalError"
    
    def test_health_check_cache_not_found(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should return degraded when cache directory missing"""
        # Simulate missing cache directory
        mock_cache_dir["exists"].return_value = False
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["checks"]["cache"]["status"] == "warning"
        assert "Cache directory not found" in data["checks"]["cache"]["message"]
    
    def test_health_check_cache_error(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should handle cache check exceptions gracefully"""
        # Simulate cache directory error
        mock_cache_dir["listdir"].side_effect = PermissionError("Access denied")
        
        response = client.get("/api/v1/health")
        
        # Should still return (with cache error in checks)
        assert response.status_code in [200, 503]
        data = response.json() if response.status_code == 200 else response.json()["detail"]
        
        assert data["checks"]["cache"]["status"] == "error"
        assert "Access denied" in data["checks"]["cache"]["error"]
    
    def test_health_check_cache_warning_with_healthy_status(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should transition from healthy to degraded when cache directory missing"""
        # Simulate: Bybit OK, DB OK, but cache missing
        mock_cache_dir["exists"].return_value = False
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Overall status should be degraded (line 112->122 branch)
        assert data["status"] == "degraded"
        assert data["checks"]["cache"]["status"] == "warning"
        assert data["checks"]["bybit_api"]["status"] == "ok"
        assert data["checks"]["database"]["status"] == "ok"
    
    def test_health_check_config_included(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should include configuration details in response"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "config" in data
        assert "cache_enabled" in data["config"]
        assert "db_persist_enabled" in data["config"]
        assert "log_level" in data["config"]


# ============================================================================
# Test Class: Bybit Health Check
# ============================================================================

class TestBybitHealth:
    """Tests for GET /api/v1/health/bybit endpoint"""
    
    def test_bybit_health_all_symbols_success(self, client, mock_bybit_adapter):
        """Should test multiple symbols and return success rate"""
        response = client.get("/api/v1/health/bybit")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success_rate"] == 100.0
        assert data["successful"] == 3
        assert data["total"] == 3
        assert "timestamp" in data
        assert "results" in data
        
        # Verify each symbol was tested
        assert "BTCUSDT" in data["results"]
        assert "ETHUSDT" in data["results"]
        assert "SOLUSDT" in data["results"]
        
        # Verify BTCUSDT details
        btc_result = data["results"]["BTCUSDT"]
        assert btc_result["status"] == "ok"
        assert btc_result["candles"] == 10
        assert "response_time_ms" in btc_result
        assert "latest_price" in btc_result
    
    def test_bybit_health_partial_failure(self, client, mock_bybit_adapter):
        """Should handle partial symbol failures"""
        # Simulate failure for ETHUSDT only
        def get_klines_side_effect(symbol, interval, limit):
            if symbol == "ETHUSDT":
                raise Exception("Rate limit exceeded")
            return [{'close': '37050.0', 'open_time': '2025-11-13T10:00:00Z'}] * 10
        
        mock_bybit_adapter.get_klines.side_effect = get_klines_side_effect
        
        response = client.get("/api/v1/health/bybit")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success_rate"] == 66.67  # 2/3 = 66.67%
        assert data["successful"] == 2
        assert data["total"] == 3
        
        # ETHUSDT should show error
        assert data["results"]["ETHUSDT"]["status"] == "error"
        assert "Rate limit exceeded" in data["results"]["ETHUSDT"]["error"]
        
        # Others should succeed
        assert data["results"]["BTCUSDT"]["status"] == "ok"
        assert data["results"]["SOLUSDT"]["status"] == "ok"
    
    def test_bybit_health_all_failures(self, client, mock_bybit_adapter):
        """Should handle all symbols failing"""
        mock_bybit_adapter.get_klines.side_effect = Exception("Network error")
        
        response = client.get("/api/v1/health/bybit")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success_rate"] == 0.0
        assert data["successful"] == 0
        assert data["total"] == 3
        
        # All symbols should show errors
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            assert data["results"][symbol]["status"] == "error"
            assert "Network error" in data["results"][symbol]["error"]


# ============================================================================
# Test Class: Readiness Check
# ============================================================================

class TestReadinessCheck:
    """Tests for GET /api/v1/health/ready endpoint (Kubernetes readiness probe)"""
    
    def test_readiness_check_ready(self, client, mock_bybit_adapter):
        """Should return 200 when service is ready"""
        response = client.get("/api/v1/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert "timestamp" in data
    
    def test_readiness_check_not_ready_no_data(self, client, mock_bybit_adapter):
        """Should return 503 when Bybit returns no data"""
        mock_bybit_adapter.get_klines.return_value = []
        
        response = client.get("/api/v1/health/ready")
        
        assert response.status_code == 503
        assert "Bybit API not responding with data" in response.json()["detail"]
    
    def test_readiness_check_not_ready_exception(self, client, mock_bybit_adapter):
        """Should return 503 when Bybit API fails"""
        mock_bybit_adapter.get_klines.side_effect = Exception("Connection refused")
        
        response = client.get("/api/v1/health/ready")
        
        assert response.status_code == 503
        assert "Service not ready" in response.json()["detail"]
        assert "Connection refused" in response.json()["detail"]


# ============================================================================
# Test Class: Liveness Check
# ============================================================================

class TestLivenessCheck:
    """Tests for GET /api/v1/health/live endpoint (Kubernetes liveness probe)"""
    
    def test_liveness_check_always_alive(self, client):
        """Should always return 200 (service is alive)"""
        response = client.get("/api/v1/health/live")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_liveness_check_no_dependencies(self, client):
        """Should not depend on external services (no mocks needed)"""
        # This test runs without any mocks to verify liveness is independent
        response = client.get("/api/v1/health/live")
        
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


# ============================================================================
# Test Class: Database Pool Status
# ============================================================================

class TestDatabasePoolStatus:
    """Tests for GET /api/v1/health/db_pool endpoint"""
    
    def test_db_pool_status_healthy(self, client, mock_pool_monitor):
        """Should return pool statistics when healthy"""
        response = client.get("/api/v1/health/db_pool")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "pool_status" in data
        assert "recommendations" in data
        assert "leak_detected" in data
        assert "configuration" in data
        
        # Verify pool status
        pool_status = data["pool_status"]
        assert pool_status["size"] == 10
        assert pool_status["checked_in"] == 8
        assert pool_status["checked_out"] == 2
        assert pool_status["utilization"] == 20.0
        assert pool_status["health"] == "healthy"
        
        # Verify configuration
        config = data["configuration"]
        assert config["pool_size"] == 10
        assert config["max_overflow"] == 5
        assert config["pre_ping"] is True
        
        # Verify no leaks
        assert data["leak_detected"] is False
    
    def test_db_pool_status_critical(self, client, mock_pool_monitor):
        """Should return 503 when pool is critical"""
        # Simulate critical pool state
        mock_pool_monitor.get_pool_statistics.return_value = {
            'size': 10,
            'checked_in': 0,
            'checked_out': 10,
            'overflow': 5,
            'max_overflow': 5,
            'utilization': 150.0,  # 150% utilization (overflow in use)
            'health': 'critical',
            'timeout': 30,
            'recycle': 3600,
            'pre_ping': True
        }
        
        response = client.get("/api/v1/health/db_pool")
        
        assert response.status_code == 503
        data = response.json()["detail"]
        
        assert data["pool_status"]["health"] == "critical"
        assert data["pool_status"]["utilization"] == 150.0
        assert data["pool_status"]["overflow"] == 5
    
    def test_db_pool_status_with_leaks(self, client, mock_pool_monitor):
        """Should detect connection leaks"""
        mock_pool_monitor.check_connection_leaks.return_value = True
        
        response = client.get("/api/v1/health/db_pool")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["leak_detected"] is True
    
    def test_db_pool_status_error(self, client):
        """Should return 500 when pool monitoring fails"""
        def failing_factory():
            raise Exception("Pool access failed")

        app.dependency_overrides[health_router.get_pool_monitor_dependency] = lambda: failing_factory

        response = client.get("/api/v1/health/db_pool")
        
        assert response.status_code == 500
        assert "Failed to get DB pool status" in response.json()["detail"]


# ============================================================================
# Test Class: Metrics Endpoint
# ============================================================================

class TestMetricsEndpoint:
    """Tests for GET /api/v1/health/metrics endpoint (Prometheus)"""
    
    def test_metrics_endpoint_success(self, client, mock_prometheus):
        """Should return Prometheus metrics in correct format"""
        response = client.get("/api/v1/health/metrics")
        
        assert response.status_code == 200
        # Prometheus format version can vary (0.0.4 or 1.0.0)
        assert "text/plain" in response.headers["content-type"]
        assert "charset=utf-8" in response.headers["content-type"]
        
        # Verify Prometheus format
        content = response.content.decode('utf-8')
        assert "# HELP" in content
        assert "metric_name" in content
    
    def test_metrics_endpoint_error(self, client, mock_prometheus):
        """Should return 500 when metrics generation fails"""
        mock_prometheus.side_effect = Exception("Metrics registry error")
        
        response = client.get("/api/v1/health/metrics")
        
        assert response.status_code == 500
        assert "Failed to generate metrics" in response.json()["detail"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestHealthIntegration:
    """Integration tests combining multiple health endpoints"""
    
    def test_health_workflow(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should check liveness → readiness → health in workflow"""
        # 1. Liveness check (always passes)
        liveness = client.get("/api/v1/health/live")
        assert liveness.status_code == 200
        
        # 2. Readiness check
        readiness = client.get("/api/v1/health/ready")
        assert readiness.status_code == 200
        
        # 3. Full health check
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"
    
    def test_degraded_workflow(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should handle degraded state gracefully"""
        # Simulate degraded Bybit (returns data but slow/partial)
        mock_bybit_adapter.get_klines.return_value = []
        
        # Liveness should still pass (service alive)
        liveness = client.get("/api/v1/health/live")
        assert liveness.status_code == 200
        
        # Readiness should fail (not ready to serve)
        readiness = client.get("/api/v1/health/ready")
        assert readiness.status_code == 503
        
        # Health should show degraded
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "degraded"
    
    def test_bybit_detailed_after_health_check(self, client, mock_bybit_adapter, mock_database, mock_cache_dir):
        """Should provide detailed Bybit health after overall health check"""
        # 1. Overall health check
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        
        # 2. Detailed Bybit health
        bybit_health = client.get("/api/v1/health/bybit")
        assert bybit_health.status_code == 200
        assert bybit_health.json()["success_rate"] == 100.0
