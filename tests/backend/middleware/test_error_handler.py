"""
Tests for centralized error handler middleware.

Verifies that ErrorHandlerMiddleware:
- Catches all unhandled exceptions
- Returns structured JSON error responses
- Includes correlation ID for tracing
- Hides internal errors in production (DEBUG=false)
- Shows detailed errors in development (DEBUG=true)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.middleware.error_handler import ErrorHandlerMiddleware


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware."""

    @pytest.mark.asyncio
    async def test_catches_unhandled_exception(self):
        """Test that middleware catches unhandled exceptions."""

        # Arrange
        async def mock_call_next(request):
            raise ValueError("Test error")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-client"}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-correlation-id"

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert response.status_code == 500
        assert response.body is not None

    @pytest.mark.asyncio
    async def test_returns_structured_error_response_debug_mode(self):
        """Test structured error response in debug mode."""

        # Arrange
        async def mock_call_next(request):
            raise ValueError("Test error message")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True, include_traceback=True)

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/backtests/"
        mock_request.query_params = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {"user-agent": "pytest"}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-123"

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        import json

        body = json.loads(response.body)
        assert "error" in body
        assert body["error"]["type"] == "ValueError"
        assert body["error"]["message"] == "Test error message"
        assert "traceback" in body["error"]
        assert body["error"]["correlation_id"] == "test-123"
        assert "timestamp" in body["error"]

    @pytest.mark.asyncio
    async def test_hides_internal_errors_production_mode(self):
        """Test that internal errors are hidden in production mode."""

        # Arrange
        async def mock_call_next(request):
            raise RuntimeError("Sensitive internal error")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=False)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = None

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        import json

        body = json.loads(response.body)
        assert body["error"]["message"] == "Internal Server Error"
        assert "traceback" not in body["error"]

    @pytest.mark.asyncio
    async def test_preserves_http_exception_status_code(self):
        """Test that HTTPException status codes are preserved."""
        from fastapi import HTTPException

        # Arrange
        async def mock_call_next(request):
            raise HTTPException(status_code=404, detail="Not found")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/nonexistent"
        mock_request.query_params = {}
        mock_request.client = None
        mock_request.headers = {}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-404"

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert response.status_code == 404
        import json

        body = json.loads(response.body)
        assert body["error"]["type"] == "HTTPException"
        # HTTPException formats message as "404: Not found"
        assert "Not found" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_adds_correlation_id_to_headers(self):
        """Test that correlation ID is added to response headers."""

        # Arrange
        async def mock_call_next(request):
            raise ValueError("Error")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.client = None
        mock_request.headers = {}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "corr-xyz-789"

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert response.headers["X-Correlation-ID"] == "corr-xyz-789"
        assert response.headers["X-Error-Type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_passes_through_successful_requests(self):
        """Test that successful requests pass through unchanged."""
        from fastapi.responses import JSONResponse

        # Arrange
        async def mock_call_next(request):
            return JSONResponse(status_code=200, content={"success": True})

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True)

        mock_request = MagicMock()

        # Act
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert response.status_code == 200
        import json

        body = json.loads(response.body)
        assert body == {"success": True}

    @pytest.mark.asyncio
    async def test_logs_error_with_context(self):
        """Test that errors are logged with full context."""

        # Arrange
        async def mock_call_next(request):
            raise ValueError("Test error for logging")

        mock_app = AsyncMock()
        middleware = ErrorHandlerMiddleware(mock_app, debug=True)

        mock_request = MagicMock()
        mock_request.method = "DELETE"
        mock_request.url.path = "/api/resource/123"
        mock_request.query_params = {"force": "true"}
        mock_request.client = MagicMock()
        mock_request.client.host = "172.16.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "log-test-456"

        with patch("backend.middleware.error_handler.logger") as mock_logger:
            # Act
            await middleware.dispatch(mock_request, mock_call_next)

            # Assert
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Unhandled exception" in call_args[0][0]
            assert "DELETE" in call_args[0][0]
            assert "/api/resource/123" in call_args[0][0]


class TestErrorHandlerMiddlewareIntegration:
    """Integration tests with FastAPI app."""

    @pytest.mark.asyncio
    async def test_middleware_in_fastapi_app(self):
        """Test error handler works within FastAPI application."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        # Arrange
        app = FastAPI()
        from backend.middleware.error_handler import ErrorHandlerMiddleware

        app.add_middleware(ErrorHandlerMiddleware, debug=True)

        @app.get("/error")
        def raise_error():
            raise ValueError("Intentional error")

        # Act
        with TestClient(app) as client:
            response = client.get("/error")

        # Assert
        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert body["error"]["type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_middleware_respects_debug_env_var(self):
        """Test that middleware reads DEBUG environment variable."""
        import os

        from fastapi import FastAPI
        from starlette.testclient import TestClient

        # Arrange
        old_debug = os.environ.get("DEBUG")
        os.environ["DEBUG"] = "false"

        try:
            app = FastAPI()
            app.add_middleware(ErrorHandlerMiddleware)

            @app.get("/error")
            def raise_error():
                raise ValueError("Sensitive error")

            # Act
            with TestClient(app) as client:
                response = client.get("/error")

            # Assert
            body = response.json()
            assert body["error"]["message"] == "Internal Server Error"
            assert "traceback" not in body["error"]

        finally:
            # Cleanup
            if old_debug is not None:
                os.environ["DEBUG"] = old_debug
            else:
                os.environ.pop("DEBUG", None)
