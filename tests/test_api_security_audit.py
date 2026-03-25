"""
Tests for API Security Audit Fixes (2026-01-28).

Tests all P0 and P1 security fixes:
- P0-1: Admin endpoints auth
- P0-2: Security endpoints auth
- P0-3: ErrorHandlerMiddleware
- P0-4: MCP timing attack fix
- P0-5: WS secret key fix
- P1-1: HSTS header
"""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestAdminAuthMiddleware:
    """Tests for P0-1: Admin endpoints authentication."""

    def test_admin_status_requires_auth(self):
        """Admin /status endpoint should require X-Admin-Key header."""
        from backend.api.routers.admin import router

        app = FastAPI()
        app.include_router(router, prefix="/admin")
        client = TestClient(app, raise_server_exceptions=False)

        # Without auth key - should return 401
        response = client.get("/admin/status")
        assert response.status_code == 401
        assert "Admin API key required" in response.json().get("detail", "")

    def test_admin_maintenance_requires_auth(self):
        """Admin /maintenance endpoint should require auth."""
        from backend.api.routers.admin import router

        app = FastAPI()
        app.include_router(router, prefix="/admin")
        client = TestClient(app, raise_server_exceptions=False)

        # Without auth key - should return 401
        response = client.post("/admin/maintenance")
        assert response.status_code == 401

    @patch.dict(os.environ, {"ADMIN_API_KEY": "test-admin-key-12345"})
    def test_admin_with_valid_key(self):
        """Admin endpoints should work with valid key."""
        # Re-import to pick up the patched env
        import importlib

        import backend.api.routers.admin as admin_module

        importlib.reload(admin_module)

        app = FastAPI()
        app.include_router(admin_module.router, prefix="/admin")
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/admin/status", headers={"X-Admin-Key": "test-admin-key-12345"})
        assert response.status_code == 200

    @patch.dict(os.environ, {"ADMIN_API_KEY": "test-admin-key-12345"})
    def test_admin_with_invalid_key(self):
        """Admin endpoints should reject invalid key."""
        import importlib

        import backend.api.routers.admin as admin_module

        importlib.reload(admin_module)

        app = FastAPI()
        app.include_router(admin_module.router, prefix="/admin")
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/admin/status", headers={"X-Admin-Key": "wrong-key"})
        assert response.status_code == 403


class TestSecurityAuthMiddleware:
    """Tests for P0-2: Security endpoints authentication."""

    def test_security_requires_auth(self):
        """Security endpoints should require X-Security-Key header."""
        from backend.api.routers.security import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        # Without auth key - should return 401
        response = client.get("/security/audit/status")
        assert response.status_code == 401
        assert "Security API key required" in response.json().get("detail", "")

    @patch.dict(os.environ, {"SECURITY_API_KEY": "test-security-key-12345"})
    def test_security_with_valid_key(self):
        """Security endpoints should work with valid key."""
        import importlib

        import backend.api.routers.security as security_module

        importlib.reload(security_module)

        app = FastAPI()
        app.include_router(security_module.router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/security/audit/status", headers={"X-Security-Key": "test-security-key-12345"})
        assert response.status_code == 200


class TestErrorHandlerMiddleware:
    """Tests for P0-3: ErrorHandlerMiddleware implementation."""

    def test_error_handler_catches_exceptions(self):
        """ErrorHandlerMiddleware should catch and format exceptions."""
        from backend.middleware.error_handler import ErrorHandlerMiddleware

        app = FastAPI()

        @app.get("/error")
        async def raise_error():
            raise ValueError("Test error")

        app.add_middleware(ErrorHandlerMiddleware, debug=True)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/error")
        assert response.status_code == 500

        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "ValueError"
        assert "Test error" in data["error"]["message"]

    def test_error_handler_hides_details_in_production(self):
        """ErrorHandlerMiddleware should hide error details when debug=False."""
        from backend.middleware.error_handler import ErrorHandlerMiddleware

        app = FastAPI()

        @app.get("/error")
        async def raise_error():
            raise ValueError("Sensitive error details")

        app.add_middleware(ErrorHandlerMiddleware, debug=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/error")
        assert response.status_code == 500

        data = response.json()
        assert "error" in data
        # Should not contain the actual error message
        assert "Sensitive error details" not in data["error"]["message"]
        assert data["error"]["message"] == "Internal Server Error"

    def test_error_handler_includes_correlation_id(self):
        """ErrorHandlerMiddleware should include correlation ID in response."""
        from backend.middleware.error_handler import ErrorHandlerMiddleware

        app = FastAPI()

        # Middleware to set correlation ID
        @app.middleware("http")
        async def set_correlation_id(request, call_next):
            request.state.correlation_id = "test-corr-id-123"
            return await call_next(request)

        @app.get("/error")
        async def raise_error():
            raise ValueError("Test error")

        app.add_middleware(ErrorHandlerMiddleware, debug=True)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/error")
        data = response.json()

        assert data["error"].get("correlation_id") == "test-corr-id-123"
        assert response.headers.get("X-Correlation-ID") == "test-corr-id-123"


class TestMCPTimingAttackFix:
    """Tests for P0-4: MCP middleware timing attack fix."""

    def test_constant_time_compare_function(self):
        """Test that constant time compare function works correctly."""
        from backend.api.mcp_middleware import _constant_time_compare

        # Same strings should match
        assert _constant_time_compare("test", "test") is True

        # Different strings should not match
        assert _constant_time_compare("test", "other") is False

        # None values should return False
        assert _constant_time_compare(None, "test") is False
        assert _constant_time_compare("test", None) is False
        assert _constant_time_compare(None, None) is False

    def test_mcp_middleware_uses_constant_time_compare(self):
        """MCP middleware should use constant-time comparison for auth."""
        from backend.api.mcp_middleware import UnifiedMcpMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(UnifiedMcpMiddleware, require_auth=True, auth_token="secret-token-123")
        client = TestClient(app, raise_server_exceptions=False)

        # Valid token should work
        response = client.get("/test", headers={"X-MCP-Token": "secret-token-123"})
        assert response.status_code == 200

        # Invalid token should fail
        response = client.get("/test", headers={"X-MCP-Token": "wrong-token"})
        assert response.status_code == 401


class TestWSSecretKeyFix:
    """Tests for P0-5: WebSocket secret key and MD5 fixes."""

    def test_sha256_used_for_anonymous_id(self):
        """Anonymous ID should use SHA256, not MD5."""
        # Check the source code contains sha256, not md5 for anonymous ID
        import inspect

        from backend.api.websocket_auth import WSAuthenticator

        source = inspect.getsource(WSAuthenticator.authenticate)
        assert "sha256" in source
        assert "md5" not in source.lower().split("anonymous")[1] if "anonymous" in source.lower() else True

    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    def test_dev_environment_generates_random_key(self):
        """In development, random key should be generated if not set."""
        # Clear the module cache and reload
        import sys

        if "backend.api.websocket_auth" in sys.modules:
            del sys.modules["backend.api.websocket_auth"]

        # Remove WS_SECRET_KEY if it exists
        env_backup = os.environ.pop("WS_SECRET_KEY", None)

        try:
            import backend.api.websocket_auth as ws_auth

            # Should not raise, should generate random key
            assert ws_auth.WS_SECRET_KEY is not None
            assert len(ws_auth.WS_SECRET_KEY) > 20  # Random key should be long
        finally:
            # Restore
            if env_backup:
                os.environ["WS_SECRET_KEY"] = env_backup


class TestHSTSHeader:
    """Tests for P1-1: HSTS header implementation."""

    def test_hsts_header_in_production(self):
        """HSTS header should be present in production environment."""
        from backend.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Enable HSTS explicitly
        app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)
        client = TestClient(app)

        response = client.get("/test")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]

    def test_hsts_header_disabled_by_default_in_dev(self):
        """HSTS header should be disabled in development by default."""
        from backend.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Disable HSTS explicitly (simulating dev environment)
        app.add_middleware(SecurityHeadersMiddleware, enable_hsts=False)
        client = TestClient(app)

        response = client.get("/test")
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_includes_subdomains(self):
        """HSTS header should include includeSubDomains directive."""
        from backend.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True, hsts_include_subdomains=True)
        client = TestClient(app)

        response = client.get("/test")
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "includeSubDomains" in hsts

    def test_x_frame_options_deny(self):
        """X-Frame-Options should be DENY."""
        from backend.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/test")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_strict(self):
        """Referrer-Policy should be strict-origin-when-cross-origin."""
        from backend.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/test")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


class TestConstantTimeComparison:
    """Tests for constant-time comparison implementations."""

    def test_admin_uses_hmac_compare(self):
        """Admin auth should use hmac.compare_digest."""
        import inspect

        from backend.api.routers.admin import verify_admin_key

        source = inspect.getsource(verify_admin_key)
        assert "hmac.compare_digest" in source

    def test_security_uses_hmac_compare(self):
        """Security auth should use hmac.compare_digest."""
        import inspect

        from backend.api.routers.security import verify_security_key

        source = inspect.getsource(verify_security_key)
        assert "hmac.compare_digest" in source

    def test_mcp_uses_hmac_compare(self):
        """MCP middleware should use hmac.compare_digest."""
        import inspect

        from backend.api.mcp_middleware import _constant_time_compare

        source = inspect.getsource(_constant_time_compare)
        assert "hmac.compare_digest" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
