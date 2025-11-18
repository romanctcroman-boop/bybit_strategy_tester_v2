"""
Tests for AI Analysis Router (backend/api/routers/ai.py)

Tests cover:
- Backtest analysis via Perplexity AI
- Health check endpoint
- API key configuration handling
- Error scenarios (network failures, invalid responses)
- Request/response validation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import httpx


@pytest.fixture
def client():
    """FastAPI test client with AI router"""
    from fastapi import FastAPI
    from backend.api.routers.ai import router
    
    app = FastAPI()
    app.include_router(router)
    
    return TestClient(app)


@pytest.fixture
def mock_api_key():
    """Mock PERPLEXITY_API_KEY module variable"""
    with patch("backend.api.routers.ai.PERPLEXITY_API_KEY", "test_perplexity_key_12345"):
        yield "test_perplexity_key_12345"


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for Perplexity API calls"""
    with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
        # Create mock client instance
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Анализ бэктеста показывает стабильную прибыльность..."
                    }
                }
            ],
            "usage": {
                "total_tokens": 450
            }
        }
        mock_response.raise_for_status = MagicMock()
        
        # Mock post method
        mock_client.post = AsyncMock(return_value=mock_response)
        
        yield mock_client


class TestAnalyzeBacktest:
    """Tests for POST /ai/analyze-backtest endpoint"""
    
    def test_analyze_backtest_success(self, client, mock_api_key, mock_httpx_client):
        """Should successfully analyze backtest with valid request"""
        request_data = {
            "context": {
                "backtest_id": "test_123",
                "strategy": "RSI_Strategy",
                "total_return": 15.5,
                "sharpe_ratio": 1.8,
                "max_drawdown": -8.2
            },
            "query": "Проанализируй результаты бэктеста RSI стратегии",
            "model": "sonar"
        }
        
        response = client.post("/ai/analyze-backtest", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "analysis" in data
        assert "Анализ бэктеста" in data["analysis"]
        assert data["model"] == "sonar"
        assert data["tokens"] == 450
        
        # Verify API call was made with correct parameters
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args.kwargs["json"]["model"] == "sonar"
        assert "RSI стратегии" in call_args.kwargs["json"]["messages"][1]["content"]
    
    def test_analyze_backtest_default_model(self, client, mock_api_key, mock_httpx_client):
        """Should use default 'sonar' model when not specified"""
        request_data = {
            "context": {"backtest_id": "test_456"},
            "query": "Анализ стратегии"
        }
        
        response = client.post("/ai/analyze-backtest", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "sonar"
    
    def test_analyze_backtest_no_api_key(self, client):
        """Should return 503 when API key not configured"""
        # Patch module-level PERPLEXITY_API_KEY variable
        with patch("backend.api.routers.ai.PERPLEXITY_API_KEY", None):
            request_data = {
                "context": {"backtest_id": "test_789"},
                "query": "Analyze strategy"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 503
            assert "API key not configured" in response.json()["detail"]
    
    def test_analyze_backtest_perplexity_http_error(self, client, mock_api_key):
        """Should handle Perplexity API HTTP errors gracefully"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Simulate HTTP error
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Rate limit exceeded"
            
            error = httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=MagicMock(),
                response=mock_response
            )
            mock_client.post = AsyncMock(side_effect=error)
            
            request_data = {
                "context": {"backtest_id": "test_rate_limit"},
                "query": "Analyze"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_analyze_backtest_network_error(self, client, mock_api_key):
        """Should handle network connection errors"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Simulate network error
            error = httpx.RequestError("Connection timeout")
            mock_client.post = AsyncMock(side_effect=error)
            
            request_data = {
                "context": {"backtest_id": "test_network_error"},
                "query": "Analyze"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 503
            assert "Failed to connect to Perplexity API" in response.json()["detail"]
    
    def test_analyze_backtest_invalid_perplexity_response(self, client, mock_api_key):
        """Should handle invalid response structure from Perplexity API"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Invalid response (no choices)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"error": "Invalid response"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client.post = AsyncMock(return_value=mock_response)
            
            request_data = {
                "context": {"backtest_id": "test_invalid_response"},
                "query": "Analyze"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 500
            assert "Invalid response from Perplexity API" in response.json()["detail"]
    
    def test_analyze_backtest_empty_choices(self, client, mock_api_key):
        """Should handle empty choices array in Perplexity response"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Empty choices array
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": []}
            mock_response.raise_for_status = MagicMock()
            
            mock_client.post = AsyncMock(return_value=mock_response)
            
            request_data = {
                "context": {"backtest_id": "test_empty_choices"},
                "query": "Analyze"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 500
            assert "Invalid response from Perplexity API" in response.json()["detail"]
    
    def test_analyze_backtest_missing_tokens_field(self, client, mock_api_key, mock_httpx_client):
        """Should handle missing usage/tokens field gracefully"""
        # Modify mock response to not include usage
        mock_httpx_client.post.return_value.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Analysis result"
                    }
                }
            ]
            # No usage field
        }
        
        request_data = {
            "context": {"backtest_id": "test_no_tokens"},
            "query": "Analyze"
        }
        
        response = client.post("/ai/analyze-backtest", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["tokens"] is None
    
    def test_analyze_backtest_request_validation(self, client, mock_api_key):
        """Should validate request schema (missing required fields)"""
        # Missing query field
        invalid_request = {
            "context": {"backtest_id": "test_validation"}
            # Missing "query"
        }
        
        response = client.post("/ai/analyze-backtest", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    def test_analyze_backtest_custom_model(self, client, mock_api_key, mock_httpx_client):
        """Should support custom Perplexity model selection"""
        request_data = {
            "context": {"backtest_id": "test_custom_model"},
            "query": "Analyze strategy",
            "model": "sonar-medium"
        }
        
        response = client.post("/ai/analyze-backtest", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "sonar-medium"
        
        # Verify correct model was sent to API
        call_args = mock_httpx_client.post.call_args
        assert call_args.kwargs["json"]["model"] == "sonar-medium"
    
    def test_analyze_backtest_timeout_handling(self, client, mock_api_key):
        """Should handle API timeout gracefully"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Simulate timeout
            error = httpx.TimeoutException("Request timeout")
            mock_client.post = AsyncMock(side_effect=error)
            
            request_data = {
                "context": {"backtest_id": "test_timeout"},
                "query": "Analyze"
            }
            
            response = client.post("/ai/analyze-backtest", json=request_data)
            
            assert response.status_code == 503
            assert "Failed to connect to Perplexity API" in response.json()["detail"]


class TestAIHealthCheck:
    """Tests for GET /ai/health endpoint"""
    
    def test_health_check_configured(self, client, mock_api_key):
        """Should return healthy when API key is configured"""
        response = client.get("/ai/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["perplexity_configured"] is True
        assert "operational" in data["message"]
    
    def test_health_check_not_configured(self, client):
        """Should return degraded when API key is not configured"""
        # Patch module-level PERPLEXITY_API_KEY variable
        with patch("backend.api.routers.ai.PERPLEXITY_API_KEY", None):
            response = client.get("/ai/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "degraded"
            assert data["perplexity_configured"] is False
            assert "not configured" in data["message"].lower()
    
    def test_health_check_empty_api_key(self, client):
        """Should return degraded when API key is empty string"""
        # Patch module-level PERPLEXITY_API_KEY variable
        with patch("backend.api.routers.ai.PERPLEXITY_API_KEY", ""):
            response = client.get("/ai/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "degraded"
            assert data["perplexity_configured"] is False


class TestAIIntegration:
    """Integration tests for AI router workflows"""
    
    def test_health_then_analysis_workflow(self, client, mock_api_key, mock_httpx_client):
        """Should perform health check before analysis in realistic workflow"""
        # 1. Check health
        health_response = client.get("/ai/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"
        
        # 2. Perform analysis
        analysis_request = {
            "context": {
                "backtest_id": "workflow_test",
                "total_return": 25.3
            },
            "query": "Analyze this backtest"
        }
        
        analysis_response = client.post("/ai/analyze-backtest", json=analysis_request)
        assert analysis_response.status_code == 200
        assert "analysis" in analysis_response.json()
    
    def test_multiple_analyses_sequence(self, client, mock_api_key, mock_httpx_client):
        """Should handle multiple sequential analysis requests"""
        analyses = [
            {"context": {"strategy": "RSI"}, "query": "Analyze RSI"},
            {"context": {"strategy": "MACD"}, "query": "Analyze MACD"},
            {"context": {"strategy": "BB"}, "query": "Analyze Bollinger Bands"}
        ]
        
        for analysis_data in analyses:
            response = client.post("/ai/analyze-backtest", json=analysis_data)
            assert response.status_code == 200
            assert response.json()["analysis"]
        
        # Verify 3 API calls were made
        assert mock_httpx_client.post.call_count == 3
    
    def test_degraded_service_workflow(self, client):
        """Should gracefully handle degraded service (no API key) workflow"""
        # Patch module-level PERPLEXITY_API_KEY variable
        with patch("backend.api.routers.ai.PERPLEXITY_API_KEY", None):
            # 1. Health check shows degraded
            health_response = client.get("/ai/health")
            assert health_response.json()["status"] == "degraded"
            
            # 2. Analysis request fails gracefully
            analysis_request = {
                "context": {"backtest_id": "degraded_test"},
                "query": "Analyze"
            }
            
            analysis_response = client.post("/ai/analyze-backtest", json=analysis_request)
            assert analysis_response.status_code == 503
            assert "not configured" in analysis_response.json()["detail"]


class TestPerplexityAPIIntegration:
    """Tests specific to Perplexity API integration details"""
    
    def test_api_request_structure(self, client, mock_api_key, mock_httpx_client):
        """Should send correctly formatted request to Perplexity API"""
        request_data = {
            "context": {"backtest_id": "api_structure_test"},
            "query": "Test query",
            "model": "sonar"
        }
        
        client.post("/ai/analyze-backtest", json=request_data)
        
        # Verify API call structure
        call_args = mock_httpx_client.post.call_args
        assert call_args.args[0] == "https://api.perplexity.ai/chat/completions"
        
        headers = call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test_perplexity_key_12345"
        assert headers["Content-Type"] == "application/json"
        
        payload = call_args.kwargs["json"]
        assert payload["model"] == "sonar"
        assert payload["temperature"] == 0.2
        assert payload["top_p"] == 0.9
        assert payload["max_tokens"] == 1500
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Test query"
    
    def test_api_timeout_configuration(self, client, mock_api_key):
        """Should configure 30 second timeout for API requests"""
        with patch("backend.api.routers.ai.httpx.AsyncClient") as mock_client_class:
            request_data = {
                "context": {"backtest_id": "timeout_config_test"},
                "query": "Test"
            }
            
            client.post("/ai/analyze-backtest", json=request_data)
            
            # Verify timeout was set
            mock_client_class.assert_called_once_with(timeout=30.0)
    
    def test_system_prompt_content(self, client, mock_api_key, mock_httpx_client):
        """Should include correct system prompt for trading analysis"""
        request_data = {
            "context": {"backtest_id": "system_prompt_test"},
            "query": "Analyze"
        }
        
        client.post("/ai/analyze-backtest", json=request_data)
        
        call_args = mock_httpx_client.post.call_args
        system_message = call_args.kwargs["json"]["messages"][0]["content"]
        
        assert "эксперт" in system_message
        assert "торговых стратегий" in system_message
        assert "бэктестов" in system_message
        assert "оптимизации" in system_message
