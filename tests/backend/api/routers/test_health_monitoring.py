"""
Tests for Enhanced Health Monitoring API

Tests cover:
- Enhanced health check (all components)
- Health dashboard aggregation
- Individual component checks
- Health summary endpoint
- Error handling and status codes
"""

import copy

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from backend.api.app import app


client = TestClient(app)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_healthy_components():
    """Mock all components as healthy"""
    return [
        {
            "name": "database",
            "status": "healthy",
            "response_time_ms": 15.5,
            "details": {"pool_size": 5, "checked_out": 2, "utilization_pct": 40.0},
            "last_check": "2025-01-01T00:00:00Z"
        },
        {
            "name": "redis",
            "status": "healthy",
            "response_time_ms": 5.2,
            "details": {"connected": True, "queue_depth": 10},
            "last_check": "2025-01-01T00:00:00Z"
        },
        {
            "name": "celery",
            "status": "healthy",
            "response_time_ms": 20.1,
            "details": {"worker_count": 2, "active_tasks": 5},
            "last_check": "2025-01-01T00:00:00Z"
        },
        {
            "name": "disk",
            "status": "healthy",
            "response_time_ms": 2.3,
            "details": {"used_pct": 45.5, "free_gb": 100.5},
            "last_check": "2025-01-01T00:00:00Z"
        },
        {
            "name": "bybit_api",
            "status": "healthy",
            "response_time_ms": 120.5,
            "details": {"candles_fetched": 10, "latest_price": 50000.0},
            "last_check": "2025-01-01T00:00:00Z"
        }
    ]


@pytest.fixture(autouse=True)
def agent_breaker_snapshot(monkeypatch):
    """Patch breaker telemetry helper to avoid hitting real agent interface."""

    snapshot = {
        "available": True,
        "summary": {
            "mcp_available": True,
            "mcp_breaker_rejections": 2,
            "deepseek_keys_active": 8,
            "perplexity_keys_active": 4,
            "autonomy_score": 8.4,
            "last_health_check": "2025-01-01T00:00:00Z",
            "total_requests": 42,
            "health_monitoring": {"total_components": 3},
            "circuit_breaker_totals": {
                "total_calls": 120,
                "total_failures": 6,
                "total_trips": 1,
            },
        },
        "breakers": {
            "mcp_server": {
                "state": "CLOSED",
                "total_calls": 10,
                "failed_calls": 1,
                "successful_calls": 9,
                "total_trips": 0,
                "last_trip_time": None,
                "breaker_rejections": 2,
            },
            "deepseek_api": {
                "state": "CLOSED",
                "total_calls": 80,
                "failed_calls": 3,
                "successful_calls": 77,
                "total_trips": 1,
                "last_trip_time": "2025-01-01T00:00:00Z",
            },
            "perplexity_api": {
                "state": "CLOSED",
                "total_calls": 30,
                "failed_calls": 2,
                "successful_calls": 28,
                "total_trips": 0,
                "last_trip_time": None,
            },
        },
    }

    def fake_snapshot():
        return copy.deepcopy(snapshot)

    monkeypatch.setattr(
        "backend.api.routers.health_monitoring.get_agent_breaker_snapshot",
        fake_snapshot,
    )

    return snapshot


# ============================================================================
# TESTS: Enhanced Health Check
# ============================================================================

class TestEnhancedHealthCheck:
    """Tests for GET /api/v1/health/enhanced"""
    
    @pytest.mark.asyncio
    async def test_endpoint_exists(self):
        """Should return response (may be mocked or degraded in test env)"""
        response = client.get("/api/v1/health/enhanced")
        
        # Accept 200 (healthy/degraded) or 503 (unhealthy)
        assert response.status_code in [200, 503]
        
        data = response.json()
        if response.status_code == 503:
            # 503 returns detail field
            data = data.get("detail", data)
        
        assert "overall_status" in data
        assert "timestamp" in data
        assert "components" in data
        assert "summary" in data
    
    @pytest.mark.asyncio
    async def test_response_structure(self):
        """Should return proper response structure"""
        response = client.get("/api/v1/health/enhanced")
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        # Verify required fields
        assert "overall_status" in data
        assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]
        
        # Verify components array
        assert isinstance(data["components"], list)
        assert len(data["components"]) == 5  # DB, Redis, Celery, Disk, API
        
        # Verify component structure
        for component in data["components"]:
            assert "name" in component
            assert "status" in component
            assert "response_time_ms" in component
            assert "details" in component
            assert "last_check" in component

        assert "agent_telemetry" in data
        mcp_breaker = data["agent_telemetry"]["breakers"]["mcp_server"]
        assert mcp_breaker["breaker_rejections"] == 2


# ============================================================================
# TESTS: Health Dashboard
# ============================================================================

class TestHealthDashboard:
    """Tests for GET /api/v1/health/dashboard"""
    
    @pytest.mark.asyncio
    async def test_endpoint_exists(self):
        """Should return dashboard response"""
        response = client.get("/api/v1/health/dashboard")
        
        # Accept 200 or 503
        assert response.status_code in [200, 503]
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        assert "overall_status" in data
        assert "components" in data
        assert "summary" in data
        assert "alerts" in data
    
    @pytest.mark.asyncio
    async def test_dashboard_structure(self):
        """Should return complete dashboard structure"""
        response = client.get("/api/v1/health/dashboard")
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        # Verify summary counts
        summary = data["summary"]
        assert "healthy" in summary
        assert "degraded" in summary
        assert "unhealthy" in summary
        
        # Verify alerts is a list
        assert isinstance(data["alerts"], list)
        assert "agent_telemetry" in data


# ============================================================================
# TESTS: Component Health
# ============================================================================

class TestComponentHealth:
    """Tests for GET /api/v1/health/components/{name}"""
    
    @pytest.mark.asyncio
    async def test_get_database_component(self):
        """Should return database component health"""
        response = client.get("/api/v1/health/components/database")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "database"
        assert "status" in data
        assert "response_time_ms" in data
        assert "details" in data
    
    @pytest.mark.asyncio
    async def test_get_redis_component(self):
        """Should return redis component health"""
        response = client.get("/api/v1/health/components/redis")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "redis"
        assert "status" in data
    
    @pytest.mark.asyncio
    async def test_get_invalid_component(self):
        """Should return 404 for invalid component"""
        response = client.get("/api/v1/health/components/invalid_component")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_all_available_components(self):
        """Should be able to query all available components"""
        components = ["database", "redis", "celery", "disk", "bybit_api"]
        
        for component in components:
            response = client.get(f"/api/v1/health/components/{component}")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == component


# ============================================================================
# TESTS: Health Summary
# ============================================================================

class TestHealthSummary:
    """Tests for GET /api/v1/health/summary"""
    
    @pytest.mark.asyncio
    async def test_endpoint_exists(self):
        """Should return summary response"""
        response = client.get("/api/v1/health/summary")
        
        # Accept 200 or 503
        assert response.status_code in [200, 503]
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        assert "status" in data
        assert "timestamp" in data
        assert "agent_telemetry" in data
    
    @pytest.mark.asyncio
    async def test_summary_minimal_response(self):
        """Should return minimal response (fast check)"""
        response = client.get("/api/v1/health/summary")
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        # Should only check critical components (DB + API)
        assert "components_checked" in data
        assert data["components_checked"] == 2
        assert data["agent_telemetry"]["summary"]["mcp_breaker_rejections"] == 2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for health monitoring workflow"""
    
    @pytest.mark.asyncio
    async def test_full_health_check_workflow(self):
        """Test complete health monitoring workflow"""
        # 1. Get summary (quick check)
        response = client.get("/api/v1/health/summary")
        assert response.status_code in [200, 503]
        
        # 2. Get enhanced health (detailed)
        response = client.get("/api/v1/health/enhanced")
        assert response.status_code in [200, 503]
        
        data = response.json()
        if response.status_code == 503:
            data = data.get("detail", data)
        
        # 3. If any component is degraded, check it individually
        for component in data["components"]:
            if component["status"] in ["degraded", "unhealthy"]:
                comp_response = client.get(f"/api/v1/health/components/{component['name']}")
                assert comp_response.status_code == 200
        
        # 4. Get dashboard view
        response = client.get("/api/v1/health/dashboard")
        assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_all_endpoints_return_consistent_data(self):
        """Verify all endpoints return consistent component data"""
        # Get data from different endpoints
        enhanced = client.get("/api/v1/health/enhanced").json()
        dashboard = client.get("/api/v1/health/dashboard").json()
        
        # Handle 503 responses
        if "detail" in enhanced:
            enhanced = enhanced["detail"]
        if "detail" in dashboard:
            dashboard = dashboard["detail"]
        
        # Both should report same components
        enhanced_components = {c["name"] for c in enhanced["components"]}
        dashboard_components = {c["name"] for c in dashboard["components"]}
        
        assert enhanced_components == dashboard_components
        assert "agent_telemetry" in enhanced
        assert "agent_telemetry" in dashboard
    
    @pytest.mark.asyncio
    async def test_status_codes_consistency(self):
        """Verify status codes are consistent across endpoints"""
        enhanced_response = client.get("/api/v1/health/enhanced")
        dashboard_response = client.get("/api/v1/health/dashboard")
        
        # If one returns 503, both should (unhealthy system)
        if enhanced_response.status_code == 503:
            assert dashboard_response.status_code == 503
        
        # If enhanced is 200, dashboard should also be 200 (healthy/degraded)
        if enhanced_response.status_code == 200:
            assert dashboard_response.status_code == 200


# ============================================================================
# UNIT TESTS (Mocked)
# ============================================================================

class TestHealthCheckUnit:
    """Unit tests with mocked components"""
    
    @pytest.mark.asyncio
    @patch('backend.api.routers.health_monitoring.check_database_health')
    @patch('backend.api.routers.health_monitoring.check_redis_health')
    @patch('backend.api.routers.health_monitoring.check_celery_health')
    @patch('backend.api.routers.health_monitoring.check_disk_health')
    @patch('backend.api.routers.health_monitoring.check_api_health')
    async def test_all_healthy_returns_200(self, mock_api, mock_disk, mock_celery, mock_redis, mock_db):
        """Should return 200 when all components are healthy"""
        from backend.api.routers.health_monitoring import ComponentHealth
        
        # Mock all components as healthy
        mock_db.return_value = ComponentHealth(
            name="database", status="healthy", response_time_ms=10.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_redis.return_value = ComponentHealth(
            name="redis", status="healthy", response_time_ms=5.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_celery.return_value = ComponentHealth(
            name="celery", status="healthy", response_time_ms=20.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_disk.return_value = ComponentHealth(
            name="disk", status="healthy", response_time_ms=2.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_api.return_value = ComponentHealth(
            name="bybit_api", status="healthy", response_time_ms=100.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        
        response = client.get("/api/v1/health/enhanced")
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "healthy"
    
    @pytest.mark.asyncio
    @patch('backend.api.routers.health_monitoring.check_database_health')
    @patch('backend.api.routers.health_monitoring.check_redis_health')
    @patch('backend.api.routers.health_monitoring.check_celery_health')
    @patch('backend.api.routers.health_monitoring.check_disk_health')
    @patch('backend.api.routers.health_monitoring.check_api_health')
    async def test_one_unhealthy_returns_503(self, mock_api, mock_disk, mock_celery, mock_redis, mock_db):
        """Should return 503 when any component is unhealthy"""
        from backend.api.routers.health_monitoring import ComponentHealth
        
        # Mock DB as unhealthy
        mock_db.return_value = ComponentHealth(
            name="database", status="unhealthy", response_time_ms=1000.0,
            details={"error": "Connection failed"}, last_check="2025-01-01T00:00:00Z"
        )
        mock_redis.return_value = ComponentHealth(
            name="redis", status="healthy", response_time_ms=5.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_celery.return_value = ComponentHealth(
            name="celery", status="healthy", response_time_ms=20.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_disk.return_value = ComponentHealth(
            name="disk", status="healthy", response_time_ms=2.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        mock_api.return_value = ComponentHealth(
            name="bybit_api", status="healthy", response_time_ms=100.0,
            details={}, last_check="2025-01-01T00:00:00Z"
        )
        
        response = client.get("/api/v1/health/enhanced")
        
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["overall_status"] == "unhealthy"
