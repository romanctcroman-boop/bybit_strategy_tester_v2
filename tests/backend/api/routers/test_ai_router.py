"""
Tests for AI analysis router.

Coverage target: 70%+ for backend/api/routers/ai.py
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from backend.api.routers.ai import router, BacktestAnalysisRequest, AIAnalysisResponse


# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestHealthEndpoint:
    """Test /ai/health endpoint."""
    
    def test_health_with_api_key(self):
        """Test health check when API key is configured."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            response = client.get("/ai/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'ok'
            assert data['perplexity_configured'] is True
            assert 'operational' in data['message']
    
    def test_health_without_api_key(self):
        """Test health check when API key is not configured."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', None):
            response = client.get("/ai/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'degraded'
            assert data['perplexity_configured'] is False
            assert 'not configured' in data['message']


class TestAnalyzeBacktestEndpoint:
    """Test /ai/analyze-backtest endpoint."""
    
    def test_analyze_backtest_no_api_key(self):
        """Test analysis fails when API key not configured."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', None):
            payload = {
                "context": {"backtest_id": 123},
                "query": "Analyze this backtest"
            }
            
            response = client.post("/ai/analyze-backtest", json=payload)
            
            assert response.status_code == 503
            assert 'not configured' in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_success(self):
        """Test successful backtest analysis."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            # Mock httpx response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "This is AI analysis of your backtest."
                        }
                    }
                ],
                "usage": {
                    "total_tokens": 150
                }
            }
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 123, "profit": 15.5},
                    "query": "Analyze performance and suggest improvements"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['analysis'] == "This is AI analysis of your backtest."
                assert data['model'] == "sonar"
                assert data['tokens'] == 150
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_custom_model(self):
        """Test analysis with custom model."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Analysis"}}],
                "usage": {"total_tokens": 100}
            }
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 456},
                    "query": "Quick analysis",
                    "model": "sonar-pro"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['model'] == "sonar-pro"
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_http_error(self):
        """Test handling of HTTP error from Perplexity API."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API key"
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Auth error",
                    request=MagicMock(),
                    response=mock_response
                )
            )
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 789},
                    "query": "Analyze"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 401
                assert 'Perplexity API error' in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_request_error(self):
        """Test handling of network/request error."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_client = MagicMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection timeout")
            )
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 999},
                    "query": "Analyze"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 503
                assert 'Failed to connect' in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_invalid_response(self):
        """Test handling of invalid API response."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # Empty response
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 111},
                    "query": "Analyze"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 500
                assert 'Invalid response' in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_empty_choices(self):
        """Test handling of empty choices in API response."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": []}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 222},
                    "query": "Analyze"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 500
                assert 'Invalid response' in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_analyze_backtest_unexpected_error(self):
        """Test handling of unexpected error."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("Unexpected error"))
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                payload = {
                    "context": {"backtest_id": 333},
                    "query": "Analyze"
                }
                
                response = client.post("/ai/analyze-backtest", json=payload)
                
                assert response.status_code == 500
                assert 'Internal error' in response.json()['detail']
    
    def test_analyze_backtest_missing_context(self):
        """Test validation error for missing context."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            payload = {
                "query": "Analyze"
                # Missing context
            }
            
            response = client.post("/ai/analyze-backtest", json=payload)
            
            assert response.status_code == 422  # Validation error
    
    def test_analyze_backtest_missing_query(self):
        """Test validation error for missing query."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'test_key'):
            payload = {
                "context": {"backtest_id": 444}
                # Missing query
            }
            
            response = client.post("/ai/analyze-backtest", json=payload)
            
            assert response.status_code == 422


class TestRequestModels:
    """Test request/response models."""
    
    def test_backtest_analysis_request_valid(self):
        """Test valid BacktestAnalysisRequest."""
        request = BacktestAnalysisRequest(
            context={"backtest_id": 123, "profit": 15.5},
            query="Analyze this",
            model="sonar-pro"
        )
        
        assert request.context == {"backtest_id": 123, "profit": 15.5}
        assert request.query == "Analyze this"
        assert request.model == "sonar-pro"
    
    def test_backtest_analysis_request_default_model(self):
        """Test BacktestAnalysisRequest with default model."""
        request = BacktestAnalysisRequest(
            context={},
            query="Test"
        )
        
        assert request.model == "sonar"
    
    def test_ai_analysis_response_valid(self):
        """Test valid AIAnalysisResponse."""
        response = AIAnalysisResponse(
            analysis="AI analysis text",
            model="sonar",
            tokens=150
        )
        
        assert response.analysis == "AI analysis text"
        assert response.model == "sonar"
        assert response.tokens == 150
    
    def test_ai_analysis_response_no_tokens(self):
        """Test AIAnalysisResponse without tokens."""
        response = AIAnalysisResponse(
            analysis="Analysis",
            model="sonar"
        )
        
        assert response.analysis == "Analysis"
        assert response.tokens is None


class TestIntegration:
    """Integration tests for AI router."""
    
    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        with patch('backend.api.routers.ai.PERPLEXITY_API_KEY', 'valid_key'):
            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "Comprehensive AI analysis:\n1. Strategy performance\n2. Risk metrics\n3. Recommendations"
                        }
                    }
                ],
                "usage": {"total_tokens": 250}
            }
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('httpx.AsyncClient') as mock_async_client:
                mock_async_client.return_value.__aenter__.return_value = mock_client
                
                # Step 1: Check health
                health = client.get("/ai/health")
                assert health.status_code == 200
                assert health.json()['status'] == 'ok'
                
                # Step 2: Analyze backtest
                payload = {
                    "context": {
                        "backtest_id": 555,
                        "profit_pct": 25.5,
                        "sharpe_ratio": 1.8,
                        "max_drawdown": -12.3
                    },
                    "query": "Provide detailed analysis of this backtest performance"
                }
                
                analysis = client.post("/ai/analyze-backtest", json=payload)
                
                assert analysis.status_code == 200
                data = analysis.json()
                assert "Comprehensive AI analysis" in data['analysis']
                assert data['tokens'] == 250
                assert data['model'] == "sonar"
