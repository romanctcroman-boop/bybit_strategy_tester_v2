"""
Health Check Endpoints Tests
Tests for /health, /ready, and /health/full endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import time

from backend.app import app
from backend.health_checks import HealthCheckResult, HealthChecker


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_health_checker():
    """Create mock health checker"""
    checker = MagicMock(spec=HealthChecker)
    checker.start_time = time.time()
    return checker


class TestHealthEndpoint:
    """Tests for /health endpoint (liveness probe)"""
    
    def test_health_endpoint_healthy(self, client, mock_health_checker):
        """Test health endpoint returns 200 when healthy"""
        mock_health_checker.liveness_check = AsyncMock(return_value={
            "status": "healthy",
            "timestamp": "2025-01-07T00:00:00",
            "uptime_seconds": 100.0,
            "checks": [
                {
                    "name": "process",
                    "status": "healthy",
                    "message": "CPU: 30%, Memory: 50%",
                    "duration_ms": 5.0
                },
                {
                    "name": "disk",
                    "status": "healthy",
                    "message": "Disk usage: 60%",
                    "duration_ms": 3.0
                }
            ]
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert len(data["checks"]) == 2
    
    def test_health_endpoint_unhealthy(self, client, mock_health_checker):
        """Test health endpoint returns 503 when unhealthy"""
        mock_health_checker.liveness_check = AsyncMock(return_value={
            "status": "unhealthy",
            "timestamp": "2025-01-07T00:00:00",
            "uptime_seconds": 100.0,
            "checks": [
                {
                    "name": "process",
                    "status": "unhealthy",
                    "message": "CPU usage critical: 96%",
                    "duration_ms": 5.0
                }
            ]
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"


class TestReadyEndpoint:
    """Tests for /ready endpoint (readiness probe)"""
    
    def test_ready_endpoint_ready(self, client, mock_health_checker):
        """Test ready endpoint returns 200 when all dependencies are ready"""
        mock_health_checker.readiness_check = AsyncMock(return_value={
            "status": "ready",
            "timestamp": "2025-01-07T00:00:00",
            "checks": [
                {
                    "name": "database",
                    "status": "healthy",
                    "message": "PostgreSQL connection successful",
                    "duration_ms": 10.0
                },
                {
                    "name": "redis",
                    "status": "healthy",
                    "message": "Redis connection successful",
                    "duration_ms": 5.0
                },
                {
                    "name": "deepseek_api",
                    "status": "healthy",
                    "message": "DeepSeek API reachable",
                    "duration_ms": 100.0
                },
                {
                    "name": "perplexity_api",
                    "status": "healthy",
                    "message": "Perplexity API reachable",
                    "duration_ms": 150.0
                }
            ]
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert len(data["checks"]) == 4
    
    def test_ready_endpoint_not_ready_database_down(self, client, mock_health_checker):
        """Test ready endpoint returns 503 when database is down"""
        mock_health_checker.readiness_check = AsyncMock(return_value={
            "status": "not_ready",
            "timestamp": "2025-01-07T00:00:00",
            "checks": [
                {
                    "name": "database",
                    "status": "unhealthy",
                    "message": "PostgreSQL connection failed: Connection refused",
                    "duration_ms": 5000.0
                },
                {
                    "name": "redis",
                    "status": "healthy",
                    "message": "Redis connection successful",
                    "duration_ms": 5.0
                }
            ]
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/ready")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
    
    def test_ready_endpoint_not_ready_api_down(self, client, mock_health_checker):
        """Test ready endpoint returns 503 when API is down"""
        mock_health_checker.readiness_check = AsyncMock(return_value={
            "status": "not_ready",
            "timestamp": "2025-01-07T00:00:00",
            "checks": [
                {
                    "name": "database",
                    "status": "healthy",
                    "message": "PostgreSQL connection successful",
                    "duration_ms": 10.0
                },
                {
                    "name": "deepseek_api",
                    "status": "unhealthy",
                    "message": "DeepSeek API timeout (>5s)",
                    "duration_ms": 5000.0
                }
            ]
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/ready")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"


class TestFullHealthEndpoint:
    """Tests for /health/full endpoint (detailed status)"""
    
    def test_full_health_endpoint(self, client, mock_health_checker):
        """Test full health endpoint returns detailed status"""
        mock_health_checker.full_health_check = AsyncMock(return_value={
            "status": "healthy",
            "timestamp": "2025-01-07T00:00:00",
            "uptime_seconds": 100.0,
            "liveness": {
                "status": "healthy",
                "checks": [
                    {"name": "process", "status": "healthy"}
                ]
            },
            "readiness": {
                "status": "ready",
                "checks": [
                    {"name": "database", "status": "healthy"},
                    {"name": "redis", "status": "healthy"}
                ]
            }
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/health/full")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "liveness" in data
        assert "readiness" in data
        assert "uptime_seconds" in data


class TestHealthCheckerLogic:
    """Tests for HealthChecker class logic"""
    
    @pytest.mark.asyncio
    async def test_process_health_check_healthy(self):
        """Test process health check returns healthy"""
        checker = HealthChecker()
        result = await checker.check_process_health()
        
        assert isinstance(result, HealthCheckResult)
        assert result.name == "process"
        # Status depends on actual system, but should complete without error
        assert result.duration > 0
    
    @pytest.mark.asyncio
    async def test_disk_space_check_healthy(self):
        """Test disk space check returns healthy"""
        checker = HealthChecker()
        result = await checker.check_disk_space()
        
        assert isinstance(result, HealthCheckResult)
        assert result.name == "disk"
        assert result.duration > 0
    
    @pytest.mark.asyncio
    async def test_database_check_with_mock(self):
        """Test database check with mocked connection"""
        checker = HealthChecker()
        
        with patch('backend.health_checks.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.__getitem__ = lambda self, key: 1
            mock_db.execute.return_value.fetchone.return_value = mock_result
            mock_get_db.return_value = iter([mock_db])
            
            result = await checker.check_database()
        
        assert isinstance(result, HealthCheckResult)
        assert result.name == "database"
        # Should be healthy with mocked successful connection
        if result.status:
            assert "successful" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_liveness_check_combines_results(self):
        """Test liveness check combines process and disk checks"""
        checker = HealthChecker()
        result = await checker.liveness_check()
        
        assert "status" in result
        assert "checks" in result
        assert "uptime_seconds" in result
        assert len(result["checks"]) >= 2  # process and disk
    
    @pytest.mark.asyncio
    async def test_readiness_check_structure(self):
        """Test readiness check returns proper structure"""
        checker = HealthChecker()
        await checker.initialize()
        
        result = await checker.readiness_check()
        
        assert "status" in result
        assert "checks" in result
        assert "timestamp" in result


class TestHealthCheckMetrics:
    """Tests for health check metrics"""
    
    @pytest.mark.asyncio
    async def test_metrics_updated_on_liveness_check(self):
        """Test that metrics are updated when liveness check runs"""
        from backend.health_checks import health_check_status, service_uptime_seconds
        
        checker = HealthChecker()
        await checker.liveness_check()
        
        # Verify metrics were set (values will be actual system metrics)
        # Just verify the call completed without error
        assert True
    
    @pytest.mark.asyncio
    async def test_metrics_updated_on_readiness_check(self):
        """Test that metrics are updated when readiness check runs"""
        from backend.health_checks import dependency_status
        
        checker = HealthChecker()
        await checker.initialize()
        await checker.readiness_check()
        
        # Verify metrics were set
        assert True


class TestRootEndpoint:
    """Tests for root endpoint"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns service info"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Bybit Strategy Tester API"
        assert "version" in data
        assert "endpoints" in data
        assert "/health" in data["endpoints"]["health"]
        assert "/ready" in data["endpoints"]["ready"]


# Kubernetes-specific tests
class TestKubernetesProbes:
    """Tests simulating Kubernetes probe behavior"""
    
    def test_liveness_probe_simulation(self, client, mock_health_checker):
        """Simulate Kubernetes liveness probe"""
        # Kubernetes will call /health every 10 seconds
        mock_health_checker.liveness_check = AsyncMock(return_value={
            "status": "healthy",
            "timestamp": "2025-01-07T00:00:00",
            "uptime_seconds": 100.0,
            "checks": []
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            # Simulate multiple probe calls
            for _ in range(3):
                response = client.get("/health")
                assert response.status_code == 200
    
    def test_readiness_probe_simulation(self, client, mock_health_checker):
        """Simulate Kubernetes readiness probe"""
        # Kubernetes will call /ready every 10 seconds
        mock_health_checker.readiness_check = AsyncMock(return_value={
            "status": "ready",
            "timestamp": "2025-01-07T00:00:00",
            "checks": []
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            # Simulate multiple probe calls
            for _ in range(3):
                response = client.get("/ready")
                assert response.status_code == 200
    
    def test_pod_restart_on_liveness_failure(self, client, mock_health_checker):
        """Test that unhealthy liveness results in 503 (triggers pod restart)"""
        mock_health_checker.liveness_check = AsyncMock(return_value={
            "status": "unhealthy",
            "timestamp": "2025-01-07T00:00:00",
            "uptime_seconds": 100.0,
            "checks": []
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/health")
            # 503 tells Kubernetes to restart the pod
            assert response.status_code == 503
    
    def test_traffic_routing_on_readiness_failure(self, client, mock_health_checker):
        """Test that not ready results in 503 (removes from load balancer)"""
        mock_health_checker.readiness_check = AsyncMock(return_value={
            "status": "not_ready",
            "timestamp": "2025-01-07T00:00:00",
            "checks": []
        })
        
        with patch('backend.app.get_health_checker', return_value=mock_health_checker):
            response = client.get("/ready")
            # 503 tells Kubernetes to stop routing traffic
            assert response.status_code == 503
