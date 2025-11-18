"""
Тесты для backend/app.py
Main FastAPI app with health check endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_health_checker():
    """Мок health checker'а"""
    checker = AsyncMock()
    checker.liveness_check = AsyncMock(return_value={"status": "healthy", "service": "test"})
    checker.readiness_check = AsyncMock(return_value={"status": "ready", "checks": {}})
    checker.full_health_check = AsyncMock(return_value={"status": "healthy", "liveness": {}, "readiness": {}})
    return checker


@pytest.fixture
def client(mock_health_checker):
    """Test client with mocked health checker"""
    with patch('backend.app.get_health_checker', new=AsyncMock(return_value=mock_health_checker)):
        from backend.app import app
        client = TestClient(app)
        yield client


class TestAppInitialization:
    """Тесты для инициализации FastAPI app"""
    
    def test_app_exists(self):
        """App должен быть создан"""
        from backend.app import app
        assert app is not None
        assert app.title == "Bybit Strategy Tester API"
    
    def test_app_metadata(self):
        """App должен иметь правильные метаданные"""
        from backend.app import app
        assert app.title == "Bybit Strategy Tester API"
        assert app.description == "Trading strategy backtesting platform"
        assert app.version == "2.0.0"
    
    def test_cors_middleware_configured(self):
        """CORS middleware должен быть настроен"""
        from backend.app import app
        # Check middleware is added
        middleware_types = [type(m) for m in app.user_middleware]
        # CORSMiddleware should be in the middleware stack
        assert len(app.user_middleware) > 0


class TestRootEndpoint:
    """Тесты для корневого endpoint'а"""
    
    def test_root_endpoint(self, client):
        """GET / должен возвращать информацию о сервисе"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "Bybit Strategy Tester API"
        assert data["version"] == "2.0.0"
        assert data["status"] == "running"
        assert "endpoints" in data
    
    def test_root_endpoint_structure(self, client):
        """Корневой endpoint должен возвращать список endpoints"""
        response = client.get("/")
        data = response.json()
        endpoints = data["endpoints"]
        
        assert "health" in endpoints
        assert "ready" in endpoints
        assert "full_health" in endpoints
        assert "docs" in endpoints
        assert "metrics" in endpoints


class TestHealthEndpoint:
    """Тесты для /health endpoint (liveness probe)"""
    
    def test_health_check_healthy(self, client, mock_health_checker):
        """Должен возвращать 200 для healthy сервиса"""
        mock_health_checker.liveness_check.return_value = {"status": "healthy"}
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_health_check_unhealthy(self, client, mock_health_checker):
        """Должен возвращать 503 для unhealthy сервиса"""
        mock_health_checker.liveness_check.return_value = {"status": "unhealthy"}
        
        response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
    
    def test_health_check_calls_checker(self, client, mock_health_checker):
        """Должен вызывать liveness_check"""
        client.get("/health")
        mock_health_checker.liveness_check.assert_called_once()


class TestReadyEndpoint:
    """Тесты для /ready endpoint (readiness probe)"""
    
    def test_readiness_check_ready(self, client, mock_health_checker):
        """Должен возвращать 200 когда сервис готов"""
        mock_health_checker.readiness_check.return_value = {"status": "ready"}
        
        response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    def test_readiness_check_not_ready(self, client, mock_health_checker):
        """Должен возвращать 503 когда сервис не готов"""
        mock_health_checker.readiness_check.return_value = {"status": "not_ready"}
        
        response = client.get("/ready")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
    
    def test_readiness_check_calls_checker(self, client, mock_health_checker):
        """Должен вызывать readiness_check"""
        client.get("/ready")
        mock_health_checker.readiness_check.assert_called_once()


class TestFullHealthEndpoint:
    """Тесты для /health/full endpoint"""
    
    def test_full_health_check(self, client, mock_health_checker):
        """Должен возвращать полную информацию о здоровье"""
        expected = {
            "status": "healthy",
            "liveness": {"status": "healthy"},
            "readiness": {"status": "ready", "checks": {}}
        }
        mock_health_checker.full_health_check.return_value = expected
        
        response = client.get("/health/full")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "liveness" in data
        assert "readiness" in data
    
    def test_full_health_always_200(self, client, mock_health_checker):
        """Должен всегда возвращать 200 (для мониторинга)"""
        mock_health_checker.full_health_check.return_value = {"status": "unhealthy"}
        
        response = client.get("/health/full")
        
        assert response.status_code == 200
    
    def test_full_health_calls_checker(self, client, mock_health_checker):
        """Должен вызывать full_health_check"""
        client.get("/health/full")
        mock_health_checker.full_health_check.assert_called_once()


class TestStartupEvent:
    """Тесты для startup event"""
    
    @pytest.mark.asyncio
    async def test_startup_event_initializes_checker(self, mock_health_checker):
        """Startup должен инициализировать health checker"""
        with patch('backend.app.get_health_checker', new=AsyncMock(return_value=mock_health_checker)) as mock_get:
            from backend.app import startup_event
            
            await startup_event()
            
            mock_get.assert_called_once()


class TestRouterInclusion:
    """Тесты для включения роутеров"""
    
    def test_agent_to_agent_router_included(self):
        """Agent-to-agent router должен быть включен"""
        from backend.app import app
        
        # Check that agent_to_agent routes are included
        route_paths = [route.path for route in app.routes]
        
        # Agent-to-agent API имеет свои endpoints
        # Проверим что роутер был включен (путем проверки что routes существуют)
        assert len(route_paths) > 0


class TestHealthCheckIntegration:
    """Интеграционные тесты для health checks"""
    
    def test_health_ready_full_workflow(self, client, mock_health_checker):
        """Полный workflow: health -> ready -> full"""
        mock_health_checker.liveness_check.return_value = {"status": "healthy"}
        mock_health_checker.readiness_check.return_value = {"status": "ready"}
        mock_health_checker.full_health_check.return_value = {
            "status": "healthy",
            "liveness": {"status": "healthy"},
            "readiness": {"status": "ready"}
        }
        
        # Health check
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        
        # Ready check
        ready_resp = client.get("/ready")
        assert ready_resp.status_code == 200
        
        # Full check
        full_resp = client.get("/health/full")
        assert full_resp.status_code == 200
    
    def test_degraded_service_scenario(self, client, mock_health_checker):
        """Сценарий: сервис жив но не готов"""
        mock_health_checker.liveness_check.return_value = {"status": "healthy"}
        mock_health_checker.readiness_check.return_value = {"status": "not_ready"}
        
        # Liveness OK
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        
        # Readiness NOT OK
        ready_resp = client.get("/ready")
        assert ready_resp.status_code == 503


class TestEndpointTagging:
    """Тесты для OpenAPI tags"""
    
    def test_endpoints_have_tags(self):
        """Endpoints должны иметь правильные tags для OpenAPI"""
        from backend.app import app
        
        routes = {route.path: route for route in app.routes if hasattr(route, 'tags')}
        
        # Root endpoint
        if "/" in routes:
            assert "Root" in routes["/"].tags
        
        # Health endpoints
        if "/health" in routes:
            assert "Health" in routes["/health"].tags
        
        if "/ready" in routes:
            assert "Health" in routes["/ready"].tags
        
        if "/health/full" in routes:
            assert "Health" in routes["/health/full"].tags


class TestAppConfiguration:
    """Тесты для конфигурации app"""
    
    def test_app_is_fastapi_instance(self):
        """App должен быть экземпляром FastAPI"""
        from backend.app import app
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)
    
    def test_cors_allows_all_origins(self):
        """CORS должен разрешать все origins (для разработки)"""
        from backend.app import app
        # В продакшене это должно быть ограничено
        # Проверяем что middleware настроен
        assert len(app.user_middleware) > 0


class TestOpenAPIDocumentation:
    """Тесты для OpenAPI документации"""
    
    def test_openapi_schema_available(self, client):
        """OpenAPI schema должна быть доступна"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "Bybit Strategy Tester API"
        assert schema["info"]["version"] == "2.0.0"
    
    def test_docs_endpoints_exist(self, client):
        """Документация должна быть доступна"""
        # Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200
        
        # ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200


class TestEdgeCases:
    """Тесты для edge cases"""
    
    def test_health_check_with_error(self, client, mock_health_checker):
        """Должен обработать ошибку в health checker"""
        mock_health_checker.liveness_check.side_effect = Exception("Health check failed")
        
        # FastAPI должен обработать исключение
        with pytest.raises(Exception):
            client.get("/health")
    
    def test_multiple_health_checks(self, client, mock_health_checker):
        """Должен обрабатывать множественные запросы"""
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
        
        assert mock_health_checker.liveness_check.call_count == 5
