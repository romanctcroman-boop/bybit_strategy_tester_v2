"""
Authentication Middleware - FastAPI middleware for JWT + RBAC + Rate Limiting
Protects API endpoints with comprehensive security
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Callable
import logging
import jwt

from backend.security.jwt_manager import JWTManager, TokenType
from backend.security.rbac_manager import RBACManager, Permission
from backend.security.rate_limiter import RateLimiter, RateLimitConfig

logger = logging.getLogger('security.middleware')


# Global instances (singleton pattern)
_jwt_manager: Optional[JWTManager] = None
_rbac_manager: Optional[RBACManager] = None
_rate_limiter: Optional[RateLimiter] = None


def get_jwt_manager() -> JWTManager:
    """Get global JWT manager instance"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def get_rbac_manager() -> RBACManager:
    """Get global RBAC manager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for authentication, authorization, and rate limiting.
    
    Features:
    - JWT token validation
    - RBAC permission checking
    - Rate limiting per user
    - Automatic token refresh
    - Public/protected endpoint configuration
    """
    
    def __init__(
        self,
        app,
        public_paths: Optional[List[str]] = None,
        rate_limit_config: Optional[RateLimitConfig] = None
    ):
        """
        Initialize authentication middleware.
        
        Args:
            app: FastAPI application
            public_paths: List of paths that don't require authentication
            rate_limit_config: Rate limiting configuration
        """
        super().__init__(app)
        
        self.public_paths = public_paths or [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register"
        ]
        
        self.jwt_manager = get_jwt_manager()
        self.rbac_manager = get_rbac_manager()
        self.rate_limiter = get_rate_limiter() if rate_limit_config is None else RateLimiter(rate_limit_config)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through authentication pipeline"""
        
        # Skip authentication for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        try:
            # Extract and validate JWT token
            token = self._extract_token(request)
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authentication token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Verify token
            try:
                payload = self.jwt_manager.verify_token(token)
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            except jwt.InvalidTokenError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Extract user info
            user_id = payload.get("sub")
            token_type = payload.get("type")
            roles = payload.get("roles", [])
            
            # Validate token type
            if token_type not in [TokenType.ACCESS.value, TokenType.API_KEY.value]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type for API access"
                )
            
            # Rate limiting check
            allowed, reason = self.rate_limiter.check_rate_limit(
                user_id=user_id,
                endpoint=request.url.path,
                cost=self._calculate_request_cost(request)
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=reason,
                    headers={"Retry-After": "60"}
                )
            
            # Attach user info to request state
            request.state.user_id = user_id
            request.state.roles = roles
            request.state.token_type = token_type
            request.state.permissions = self.rbac_manager.get_user_permissions(user_id)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error"
            )
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)"""
        return any(path.startswith(public_path) for public_path in self.public_paths)
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request - Week 1, Day 1 Enhancement.
        
        Priority:
        1. HTTP-only cookie (most secure, XSS-protected)
        2. Authorization header (backward compatibility)
        3. Query parameter (legacy, debugging only)
        """
        # Priority 1: HTTP-only cookie (secure, XSS-protected)
        token = self.jwt_manager.extract_token_from_request(
            request,
            TokenType.ACCESS,
            fallback_to_header=True  # Allow header fallback for backward compatibility
        )
        
        if token:
            return token
        
        # Priority 3: Query parameter (less secure, for debugging only)
        # NOTE: This should be disabled in production!
        query_token = request.query_params.get("token")
        if query_token:
            logger.warning("Token extracted from query parameter - insecure method!")
            return query_token
        
        return None
    
    def _calculate_request_cost(self, request: Request) -> int:
        """
        Calculate rate limit cost for request.
        
        Expensive operations cost more tokens:
        - POST/PUT/DELETE: 2 tokens
        - Backtest execution: 5 tokens
        - Batch operations: 10 tokens
        - GET: 1 token
        """
        method = request.method
        path = request.url.path
        
        # Expensive operations
        if "execute" in path or "batch" in path:
            return 10
        elif "backtest" in path and method == "POST":
            return 5
        elif method in ["POST", "PUT", "DELETE"]:
            return 2
        else:
            return 1


# Dependency injection functions for FastAPI routes

async def get_current_user(request: Request) -> str:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}
    """
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.state.user_id


async def get_current_user_roles(request: Request) -> List[str]:
    """
    FastAPI dependency to get current user roles.
    
    Usage:
        @app.get("/admin")
        async def admin_route(roles: List[str] = Depends(get_current_user_roles)):
            if "admin" not in roles:
                raise HTTPException(403)
    """
    if not hasattr(request.state, "roles"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.state.roles


def require_permission(permission: Permission):
    """
    FastAPI dependency factory for permission checking.
    
    Usage:
        @app.post("/backtest")
        async def create_backtest(
            user_id: str = Depends(require_permission(Permission.BACKTEST_CREATE))
        ):
            # Only users with BACKTEST_CREATE permission can access
            return {"status": "ok"}
    """
    async def permission_checker(request: Request) -> str:
        if not hasattr(request.state, "user_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        user_id = request.state.user_id
        rbac_manager = get_rbac_manager()
        
        if not rbac_manager.has_permission(user_id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}"
            )
        
        return user_id
    
    return permission_checker


def require_role(role: str):
    """
    FastAPI dependency factory for role checking.
    
    Usage:
        @app.get("/admin/users")
        async def list_users(
            user_id: str = Depends(require_role("admin"))
        ):
            # Only admin users can access
            return {"users": [...]}
    """
    async def role_checker(request: Request) -> str:
        if not hasattr(request.state, "roles"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        roles = request.state.roles
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required role: {role}"
            )
        
        return request.state.user_id
    
    return role_checker


# Helper function to setup authentication in FastAPI app

def setup_authentication(
    app,
    public_paths: Optional[List[str]] = None,
    rate_limit_config: Optional[RateLimitConfig] = None
):
    """
    Setup authentication middleware for FastAPI app.
    
    Usage:
        from fastapi import FastAPI
        from backend.security.auth_middleware import setup_authentication
        
        app = FastAPI()
        setup_authentication(app)
    
    Args:
        app: FastAPI application
        public_paths: Paths that don't require authentication
        rate_limit_config: Rate limiting configuration
    """
    middleware = AuthenticationMiddleware(
        app,
        public_paths=public_paths,
        rate_limit_config=rate_limit_config
    )
    
    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
    
    logger.info("Authentication middleware configured")
