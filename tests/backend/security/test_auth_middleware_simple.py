"""
Simplified unit tests for AuthenticationMiddleware
Focus on testing individual methods and logic without full middleware stack
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, HTTPException
import jwt

from backend.security.auth_middleware import (
    AuthenticationMiddleware,
    get_current_user,
    get_current_user_roles,
    require_permission,
    require_role,
)
from backend.security.jwt_manager import JWTManager, TokenType, TokenConfig
from backend.security.rbac_manager import RBACManager, Permission
from backend.security.rate_limiter import RateLimiter, RateLimitConfig


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def jwt_manager():
    """Create JWT manager"""
    return JWTManager(config=TokenConfig())


@pytest.fixture
def rbac_manager():
    """Create RBAC manager"""
    return RBACManager()


@pytest.fixture
def rate_limiter():
    """Create rate limiter"""
    return RateLimiter(config=RateLimitConfig())


@pytest.fixture
def middleware(jwt_manager, rbac_manager, rate_limiter):
    """Create middleware instance"""
    from fastapi import FastAPI
    app = FastAPI()
    
    middleware = AuthenticationMiddleware(
        app,
        public_paths=["/public", "/health"],
        rate_limit_config=None
    )
    
    # Inject mocked managers
    middleware.jwt_manager = jwt_manager
    middleware.rbac_manager = rbac_manager
    middleware.rate_limiter = rate_limiter
    
    return middleware


# ============================================================================
# TEST PUBLIC PATH CHECKING
# ============================================================================

class TestPublicPathChecking:
    """Test _is_public_path method"""
    
    def test_public_path_returns_true(self, middleware):
        """Test public paths return True"""
        assert middleware._is_public_path("/public") is True
        assert middleware._is_public_path("/health") is True
        assert middleware._is_public_path("/public/subpath") is True
    
    def test_protected_path_returns_false(self, middleware):
        """Test protected paths return False"""
        assert middleware._is_public_path("/protected") is False
        assert middleware._is_public_path("/api/data") is False
        assert middleware._is_public_path("/admin") is False


# ============================================================================
# TEST TOKEN EXTRACTION
# ============================================================================

class TestTokenExtractionMethod:
    """Test _extract_token method"""
    
    def test_extract_from_authorization_header(self, middleware):
        """Test token extraction from Authorization header"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test_token_123"}
        request.query_params = {}
        
        # Mock jwt_manager to return token from header
        middleware.jwt_manager.extract_token_from_request = Mock(return_value="test_token_123")
        
        token = middleware._extract_token(request)
        assert token == "test_token_123"
    
    def test_extract_from_query_parameter(self, middleware):
        """Test token extraction from query parameter"""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {"token": "query_token_456"}
        
        # Mock jwt_manager to return None (no cookie/header)
        middleware.jwt_manager.extract_token_from_request = Mock(return_value=None)
        
        token = middleware._extract_token(request)
        assert token == "query_token_456"
    
    def test_no_token_returns_none(self, middleware):
        """Test missing token returns None"""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {}
        
        middleware.jwt_manager.extract_token_from_request = Mock(return_value=None)
        
        token = middleware._extract_token(request)
        assert token is None


# ============================================================================
# TEST REQUEST COST CALCULATION
# ============================================================================

class TestRequestCostCalculation:
    """Test _calculate_request_cost method"""
    
    def test_get_request_costs_1(self, middleware):
        """Test GET requests cost 1 token"""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/api/data"
        
        cost = middleware._calculate_request_cost(request)
        assert cost == 1
    
    def test_post_request_costs_2(self, middleware):
        """Test POST requests cost 2 tokens"""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/create"
        
        cost = middleware._calculate_request_cost(request)
        assert cost == 2
    
    def test_backtest_post_costs_5(self, middleware):
        """Test backtest POST costs 5 tokens"""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/backtest/run"
        
        cost = middleware._calculate_request_cost(request)
        assert cost == 5
    
    def test_batch_operation_costs_10(self, middleware):
        """Test batch operations cost 10 tokens"""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/api/batch/process"
        
        cost = middleware._calculate_request_cost(request)
        assert cost == 10
    
    def test_execute_operation_costs_10(self, middleware):
        """Test execute operations cost 10 tokens"""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/execute/strategy"
        
        cost = middleware._calculate_request_cost(request)
        assert cost == 10


# ============================================================================
# TEST DEPENDENCY INJECTION FUNCTIONS
# ============================================================================

class TestGetCurrentUser:
    """Test get_current_user dependency"""
    
    @pytest.mark.asyncio
    async def test_returns_user_id_when_authenticated(self):
        """Test returns user_id from request.state"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        
        user_id = await get_current_user(request)
        assert user_id == "user_123"
    
    @pytest.mark.asyncio
    async def test_raises_401_when_not_authenticated(self):
        """Test raises 401 when user_id not in state"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])  # No user_id attribute
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail


class TestGetCurrentUserRoles:
    """Test get_current_user_roles dependency"""
    
    @pytest.mark.asyncio
    async def test_returns_roles_when_authenticated(self):
        """Test returns roles from request.state"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.roles = ["admin", "user"]
        
        roles = await get_current_user_roles(request)
        assert roles == ["admin", "user"]
    
    @pytest.mark.asyncio
    async def test_raises_401_when_not_authenticated(self):
        """Test raises 401 when roles not in state"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_roles(request)
        
        assert exc_info.value.status_code == 401


class TestRequirePermission:
    """Test require_permission factory"""
    
    @pytest.mark.asyncio
    async def test_allows_user_with_permission(self):
        """Test allows user with required permission"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        
        rbac_manager = Mock()
        rbac_manager.has_permission = Mock(return_value=True)
        
        with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
            checker = require_permission(Permission.BACKTEST_CREATE)
            user_id = await checker(request)
            
            assert user_id == "user_123"
            rbac_manager.has_permission.assert_called_once_with("user_123", Permission.BACKTEST_CREATE)
    
    @pytest.mark.asyncio
    async def test_denies_user_without_permission(self):
        """Test denies user without required permission"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        
        rbac_manager = Mock()
        rbac_manager.has_permission = Mock(return_value=False)
        
        with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
            checker = require_permission(Permission.BACKTEST_DELETE)
            
            with pytest.raises(HTTPException) as exc_info:
                await checker(request)
            
            assert exc_info.value.status_code == 403
            assert "backtest:delete" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_raises_401_when_not_authenticated(self):
        """Test raises 401 when user not authenticated"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        
        checker = require_permission(Permission.BACKTEST_CREATE)
        
        with pytest.raises(HTTPException) as exc_info:
            await checker(request)
        
        assert exc_info.value.status_code == 401


class TestRequireRole:
    """Test require_role factory"""
    
    @pytest.mark.asyncio
    async def test_allows_user_with_role(self):
        """Test allows user with required role"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "admin_123"
        request.state.roles = ["admin", "user"]
        
        checker = require_role("admin")
        user_id = await checker(request)
        
        assert user_id == "admin_123"
    
    @pytest.mark.asyncio
    async def test_denies_user_without_role(self):
        """Test denies user without required role"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        request.state.roles = ["user"]
        
        checker = require_role("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await checker(request)
        
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_raises_401_when_not_authenticated(self):
        """Test raises 401 when roles not in state"""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        
        checker = require_role("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await checker(request)
        
        assert exc_info.value.status_code == 401


# ============================================================================
# TEST SINGLETON MANAGER GETTERS
# ============================================================================

class TestSingletonManagers:
    """Test global manager getter functions"""
    
    def test_get_jwt_manager_returns_singleton(self):
        """Test get_jwt_manager returns same instance"""
        from backend.security.auth_middleware import get_jwt_manager, _jwt_manager
        
        # Reset global
        import backend.security.auth_middleware as auth_module
        auth_module._jwt_manager = None
        
        manager1 = get_jwt_manager()
        manager2 = get_jwt_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, JWTManager)
    
    def test_get_rbac_manager_returns_singleton(self):
        """Test get_rbac_manager returns same instance"""
        from backend.security.auth_middleware import get_rbac_manager
        
        import backend.security.auth_middleware as auth_module
        auth_module._rbac_manager = None
        
        manager1 = get_rbac_manager()
        manager2 = get_rbac_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, RBACManager)
    
    def test_get_rate_limiter_returns_singleton(self):
        """Test get_rate_limiter returns same instance"""
        from backend.security.auth_middleware import get_rate_limiter
        
        import backend.security.auth_middleware as auth_module
        auth_module._rate_limiter = None
        
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2
        assert isinstance(limiter1, RateLimiter)
