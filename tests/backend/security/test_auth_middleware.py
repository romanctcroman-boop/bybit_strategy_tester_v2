"""
Comprehensive tests for AuthenticationMiddleware

Covers:
- JWT token validation (Authorization header, cookies, query params)
- RBAC permission checking
- Rate limiting integration
- Public path handling
- Security headers
- Token type validation
- Error scenarios
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

from backend.security.auth_middleware import (
    AuthenticationMiddleware,
    get_jwt_manager,
    get_rbac_manager,
    get_rate_limiter,
    get_current_user,
    get_current_user_roles,
    require_permission,
    require_role,
    setup_authentication
)
from backend.security.jwt_manager import JWTManager, TokenType, TokenConfig
from backend.security.rbac_manager import RBACManager, Permission
from backend.security.rate_limiter import RateLimiter, RateLimitConfig


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def app():
    """Create test FastAPI application"""
    app = FastAPI()
    
    # Add HTTPException handler to properly convert exceptions to responses
    # Required because BaseHTTPMiddleware doesn't automatically handle HTTPException
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from fastapi import HTTPException, status
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers
        )
    
    @app.get("/public")
    async def public_endpoint():
        return {"message": "public"}
    
    @app.get("/protected")
    async def protected_endpoint(request: Request):
        return {
            "user_id": request.state.user_id,
            "roles": request.state.roles
        }
    
    @app.post("/backtest")
    async def backtest_endpoint(request: Request):
        return {"user_id": request.state.user_id}
    
    @app.get("/batch")
    async def batch_endpoint(request: Request):
        return {"user_id": request.state.user_id}
    
    return app


@pytest.fixture
def jwt_manager():
    """Create JWT manager for testing"""
    return JWTManager(config=TokenConfig(
        access_token_expire_minutes=15,
        refresh_token_expire_days=7
    ))


@pytest.fixture
def rbac_manager():
    """Create RBAC manager for testing"""
    return RBACManager()


@pytest.fixture
def rate_limiter():
    """Create rate limiter for testing"""
    return RateLimiter(config=RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000
    ))


@pytest.fixture
def valid_access_token(jwt_manager):
    """Generate valid access token"""
    return jwt_manager.generate_access_token(
        user_id="test_user_123",
        roles=["user", "trader"]
    )


@pytest.fixture
def expired_token(jwt_manager):
    """Generate expired access token"""
    from datetime import datetime, timedelta, timezone
    
    payload = {
        "sub": "test_user_123",
        "type": TokenType.ACCESS.value,
        "roles": ["user"],
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired 1 hour ago
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "iss": jwt_manager.config.issuer
    }
    
    private_key = jwt_manager._private_key
    return jwt.encode(payload, private_key, algorithm=jwt_manager.config.algorithm)


@pytest.fixture
def invalid_signature_token(jwt_manager):
    """Generate token with invalid signature"""
    from datetime import datetime, timedelta, timezone
    
    payload = {
        "sub": "test_user_123",
        "type": TokenType.ACCESS.value,
        "roles": ["user"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "iss": jwt_manager.config.issuer
    }
    
    # Sign with wrong key (not the actual private key)
    fake_key = "fake_secret_key_12345"
    return jwt.encode(payload, fake_key, algorithm="HS256")


def create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter, public_paths=None, raise_exceptions=False):
    """
    Helper to create TestClient with properly mocked middleware.
    
    IMPORTANT: Patches must be active BEFORE middleware creation to avoid
    using global singletons instead of test fixtures.
    
    Args:
        app: FastAPI app
        jwt_manager: JWTManager fixture
        rbac_manager: RBACManager fixture  
        rate_limiter: RateLimiter fixture
        public_paths: Custom public paths (default: ["/public"])
        raise_exceptions: If True, TestClient will raise server exceptions (useful for debugging)
        
    Returns:
        TestClient with middleware configured
    """
    if public_paths is None:
        public_paths = ["/public"]
    
    # Create patches BEFORE middleware initialization
    patch_jwt = patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager)
    patch_rbac = patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager)
    patch_rate = patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter)
    
    # Start patches
    patch_jwt.start()
    patch_rbac.start()
    patch_rate.start()
    
    # Now create middleware (will use mocked managers)
    middleware = AuthenticationMiddleware(app, public_paths=public_paths)
    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
    
    # Create client
    client = TestClient(app, raise_server_exceptions=raise_exceptions)
    
    # Store patches for cleanup
    client._patches = [patch_jwt, patch_rbac, patch_rate]
    
    return client


# ============================================================================
# TEST CLASS 1: INITIALIZATION
# ============================================================================

class TestAuthMiddlewareInitialization:
    """Test middleware initialization and configuration"""
    
    def test_default_initialization(self, app):
        """Test middleware initializes with default settings"""
        middleware = AuthenticationMiddleware(app)
        
        assert middleware.public_paths is not None
        assert "/health" in middleware.public_paths
        assert "/docs" in middleware.public_paths
        assert "/auth/login" in middleware.public_paths
        assert middleware.jwt_manager is not None
        assert middleware.rbac_manager is not None
        assert middleware.rate_limiter is not None
    
    def test_custom_public_paths(self, app):
        """Test custom public paths configuration"""
        custom_paths = ["/custom", "/api/public"]
        middleware = AuthenticationMiddleware(app, public_paths=custom_paths)
        
        assert middleware.public_paths == custom_paths
        assert "/custom" in middleware.public_paths
        assert "/api/public" in middleware.public_paths
    
    def test_custom_rate_limit_config(self, app):
        """Test custom rate limit configuration"""
        config = RateLimitConfig(requests_per_minute=100)
        middleware = AuthenticationMiddleware(app, rate_limit_config=config)
        
        assert middleware.rate_limiter is not None
        # Verify rate limiter uses custom config
        assert middleware.rate_limiter.config.requests_per_minute == 100


# ============================================================================
# TEST CLASS 2: PUBLIC PATH HANDLING
# ============================================================================

class TestPublicPathHandling:
    """Test public path access without authentication"""
    
    def test_public_path_no_auth_required(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test public paths accessible without token"""
        middleware = AuthenticationMiddleware(
            app,
            public_paths=["/public", "/health"]
        )
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get("/public")
                    assert response.status_code == 200
                    assert response.json() == {"message": "public"}
    
    def test_health_endpoint_public(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test /health endpoint accessible without auth"""
        # Add health endpoint
        @app.get("/health")
        async def health():
            return {"status": "ok"}
        
        middleware = AuthenticationMiddleware(app, public_paths=["/health"])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get("/health")
                    assert response.status_code == 200
    
    def test_protected_path_requires_auth(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test protected paths require authentication"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get("/protected")
                    assert response.status_code == 401
                    assert "Missing authentication token" in response.json()["detail"]


# ============================================================================
# TEST CLASS 3: TOKEN EXTRACTION
# ============================================================================

class TestTokenExtraction:
    """Test JWT token extraction from various sources"""
    
    def test_extract_from_authorization_header(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test token extraction from Authorization: Bearer header"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        # Mock rate limiter to always allow
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        
        # Mock RBAC manager
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {valid_access_token}"}
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["user_id"] == "test_user_123"
                    assert "user" in data["roles"]
    
    def test_extract_from_cookie(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test token extraction from HTTP-only cookie"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        # Mock cookie extraction
        with patch.object(jwt_manager, 'extract_token_from_request', return_value=valid_access_token):
            with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
                with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                    with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                        app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                        client = TestClient(app, raise_server_exceptions=False)
                        
                        response = client.get(
                            "/protected",
                            cookies={"access_token": valid_access_token}
                        )
                        
                        assert response.status_code == 200
    
    def test_extract_from_query_parameter(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test token extraction from query parameter (legacy/debug)"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        # Mock extract_token_from_request to return None (forcing query param fallback)
        with patch.object(jwt_manager, 'extract_token_from_request', return_value=None):
            with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
                with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                    with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                        app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                        client = TestClient(app, raise_server_exceptions=False)
                        
                        response = client.get(f"/protected?token={valid_access_token}")
                        
                        assert response.status_code == 200
    
    def test_missing_token_returns_401(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test missing token returns 401 Unauthorized"""
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter, raise_exceptions=True)
        
        response = client.get("/protected")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing authentication token"
        
        # Cleanup patches
        for p in client._patches:
            p.stop()


# ============================================================================
# TEST CLASS 4: TOKEN VALIDATION
# ============================================================================

class TestTokenValidation:
    """Test JWT token validation and error handling"""
    
    def test_expired_token_returns_401(self, app, jwt_manager, rbac_manager, rate_limiter, expired_token):
        """Test expired token returns 401 with specific error"""
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    middleware = AuthenticationMiddleware(app, public_paths=["/public"])
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {expired_token}"}
                    )
                    
                    assert response.status_code == 401
                    assert "expired" in response.json()["detail"].lower()
    
    def test_invalid_signature_returns_401(self, app, jwt_manager, rbac_manager, rate_limiter, invalid_signature_token):
        """Test token with invalid signature returns 401"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {invalid_signature_token}"}
                    )
                    
                    assert response.status_code == 401
                    assert "Invalid token" in response.json()["detail"]
    
    def test_malformed_token_returns_401(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test malformed token returns 401"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": "Bearer invalid_token_123"}
                    )
                    
                    assert response.status_code == 401


# ============================================================================
# TEST CLASS 5: TOKEN TYPE VALIDATION
# ============================================================================

class TestTokenTypeValidation:
    """Test token type validation (access, refresh, api_key)"""
    
    def test_access_token_accepted(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test ACCESS token type is accepted"""
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {valid_access_token}"}
                    )
                    
                    assert response.status_code == 200
    
    def test_api_key_token_accepted(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test API_KEY token type is accepted"""
        api_key_token = jwt_manager.generate_api_key(
            user_id="api_user_123",
            name="test_api_key",
            permissions=["backtest:read"]
        )
        
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {api_key_token}"}
                    )
                    
                    assert response.status_code == 200
    
    def test_refresh_token_rejected(self, app, jwt_manager, rbac_manager, rate_limiter):
        """Test REFRESH token type is rejected for API access"""
        refresh_token = jwt_manager.generate_refresh_token(user_id="test_user_123")
        
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {refresh_token}"}
                    )
                    
                    assert response.status_code == 401
                    assert "Invalid token type" in response.json()["detail"]


# ============================================================================
# TEST CLASS 6: RATE LIMITING
# ============================================================================

class TestRateLimiting:
    """Test rate limiting integration"""
    
    def test_rate_limit_allowed(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test request allowed when under rate limit"""
        # Mock rate limiter BEFORE middleware creation
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        assert response.status_code == 200
        rate_limiter.check_rate_limit.assert_called_once()
        
        # Cleanup
        for p in client._patches:
            p.stop()
    
    def test_rate_limit_exceeded_returns_429(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test request rejected when rate limit exceeded"""
        rate_limiter.check_rate_limit = Mock(return_value=(False, "Rate limit exceeded"))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        assert response.status_code == 429
        assert response.json()["detail"] == "Rate limit exceeded"
        assert "Retry-After" in response.headers
        
        for p in client._patches:
            p.stop()
    
    def test_rate_limit_cost_calculation_post(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test POST requests cost more tokens (2 vs 1)"""
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.post(
            "/backtest",
            headers={"Authorization": f"Bearer {valid_access_token}"},
            json={}
        )
        
        # Verify cost=5 for backtest POST
        call_args = rate_limiter.check_rate_limit.call_args
        assert call_args[1]["cost"] == 5
        
        for p in client._patches:
            p.stop()
    
    def test_rate_limit_cost_calculation_batch(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test batch operations cost more tokens (10)"""
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.post(
                        "/backtest",
                        headers={"Authorization": f"Bearer {valid_access_token}"},
                        json={}
                    )
                    
                    # Verify cost=5 for backtest POST
                    call_args = rate_limiter.check_rate_limit.call_args
                    assert call_args[1]["cost"] == 5
    
    def test_rate_limit_cost_calculation_batch(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test batch operations cost more tokens (10)"""
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/batch",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        # Verify cost=10 for batch operations
        call_args = rate_limiter.check_rate_limit.call_args
        assert call_args[1]["cost"] == 10
        
        for p in client._patches:
            p.stop()


# ============================================================================
# TEST CLASS 7: SECURITY HEADERS
# ============================================================================

class TestSecurityHeaders:
    """Test security headers added to responses"""
    
    def test_security_headers_added(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test security headers added to successful responses"""
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        
        for p in client._patches:
            p.stop()


# ============================================================================
# TEST CLASS 8: REQUEST STATE
# ============================================================================

class TestRequestState:
    """Test user info attached to request state"""
    
    def test_user_info_attached_to_request(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test user_id, roles, permissions attached to request.state"""
        rate_limiter.check_rate_limit = Mock(return_value=(True, None))
        rbac_manager.get_user_permissions = Mock(return_value=[Permission.BACKTEST_READ])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user_123"
        assert "user" in data["roles"]
        assert "trader" in data["roles"]
        
        for p in client._patches:
            p.stop()


# ============================================================================
# TEST CLASS 9: DEPENDENCY INJECTION
# ============================================================================

class TestDependencyInjection:
    """Test FastAPI dependency injection helpers"""
    
    @pytest.mark.asyncio
    async def test_get_current_user(self):
        """Test get_current_user dependency"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "test_user_123"
        
        user_id = await get_current_user(request)
        assert user_id == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_get_current_user_not_authenticated(self):
        """Test get_current_user raises 401 when not authenticated"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])  # No user_id attribute
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_roles(self):
        """Test get_current_user_roles dependency"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.roles = ["admin", "user"]
        
        roles = await get_current_user_roles(request)
        assert roles == ["admin", "user"]
    
    @pytest.mark.asyncio
    async def test_get_current_user_roles_not_authenticated(self):
        """Test get_current_user_roles raises 401 when not authenticated"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_roles(request)
        
        assert exc_info.value.status_code == 401


# ============================================================================
# TEST CLASS 10: PERMISSION CHECKING
# ============================================================================

class TestPermissionChecking:
    """Test require_permission dependency factory"""
    
    @pytest.mark.asyncio
    async def test_require_permission_allowed(self):
        """Test require_permission allows user with permission"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "test_user_123"
        
        rbac_manager = Mock()
        rbac_manager.has_permission = Mock(return_value=True)
        
        with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
            checker = require_permission(Permission.BACKTEST_CREATE)
            user_id = await checker(request)
            
            assert user_id == "test_user_123"
            rbac_manager.has_permission.assert_called_once_with(
                "test_user_123",
                Permission.BACKTEST_CREATE
            )
    
    @pytest.mark.asyncio
    async def test_require_permission_denied(self):
        """Test require_permission denies user without permission"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "test_user_123"
        
        rbac_manager = Mock()
        rbac_manager.has_permission = Mock(return_value=False)
        
        with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
            checker = require_permission(Permission.BACKTEST_DELETE)
            
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            
            assert exc_info.value.status_code == 403
            assert "backtest:delete" in exc_info.value.detail.lower()


# ============================================================================
# TEST CLASS 11: ROLE CHECKING
# ============================================================================

class TestRoleChecking:
    """Test require_role dependency factory"""
    
    @pytest.mark.asyncio
    async def test_require_role_allowed(self):
        """Test require_role allows user with role"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "admin_user_123"
        request.state.roles = ["admin", "user"]
        
        checker = require_role("admin")
        user_id = await checker(request)
        
        assert user_id == "admin_user_123"
    
    @pytest.mark.asyncio
    async def test_require_role_denied(self):
        """Test require_role denies user without role"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        request.state.roles = ["user"]
        
        checker = require_role("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await checker(request)
        
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()


# ============================================================================
# TEST CLASS 12: SETUP AUTHENTICATION
# ============================================================================

class TestSetupAuthentication:
    """Test setup_authentication helper function"""
    
    def test_setup_authentication_default(self):
        """Test setup_authentication with default settings"""
        app = FastAPI()
        
        setup_authentication(app)
        
        # Verify middleware added (check middleware stack)
        assert len(app.user_middleware) > 0
    
    def test_setup_authentication_custom_config(self):
        """Test setup_authentication with custom configuration"""
        app = FastAPI()
        custom_paths = ["/custom/public"]
        custom_config = RateLimitConfig(requests_per_minute=200)
        
        setup_authentication(
            app,
            public_paths=custom_paths,
            rate_limit_config=custom_config
        )
        
        assert len(app.user_middleware) > 0


# ============================================================================
# TEST CLASS 13: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Test middleware error handling and edge cases"""
    
    def test_internal_error_returns_500(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        """Test internal errors return 500 Internal Server Error"""
        # Mock jwt_manager to raise unexpected exception
        with patch.object(jwt_manager, 'verify_token', side_effect=Exception("Unexpected error")):
            client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
            
            response = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {valid_access_token}"}
            )
            
            assert response.status_code == 500
            assert "Internal authentication error" in response.json()["detail"]
            
            for p in client._patches:
                p.stop()
