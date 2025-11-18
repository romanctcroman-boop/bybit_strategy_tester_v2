"""
JWT Bearer Authentication для FastAPI
Реализует полную систему аутентификации с токенами
"""

import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Prometheus метрики
AUTH_ATTEMPTS = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['status', 'method']
)

AUTH_FAILURES = Counter(
    'auth_failures_total',
    'Authentication failures',
    ['reason']
)

# Configuration
SECRET_KEY = "your-secret-key-change-in-production-use-env-variable"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # subject (user_id)
    exp: int  # expiration
    iat: int  # issued at
    type: str  # access или refresh
    scopes: list[str] = []  # permissions


class JWTBearer(HTTPBearer):
    """
    JWT Bearer Token Authentication
    
    Usage:
        from fastapi import Depends
        
        @app.get("/protected")
        async def protected_route(token: str = Depends(jwt_bearer)):
            return {"user": token}
    """
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Dict[str, Any]:
        """Validate JWT token from Authorization header"""
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            AUTH_ATTEMPTS.labels(status='failure', method='bearer').inc()
            AUTH_FAILURES.labels(reason='missing_credentials').inc()
            logger.warning("Missing credentials")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authorization code"
            )
        
        if not credentials.scheme == "Bearer":
            AUTH_ATTEMPTS.labels(status='failure', method='bearer').inc()
            AUTH_FAILURES.labels(reason='invalid_scheme').inc()
            logger.warning(f"Invalid scheme: {credentials.scheme}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication scheme"
            )
        
        # Verify token
        token_data = self.verify_jwt(credentials.credentials)
        if not token_data:
            AUTH_ATTEMPTS.labels(status='failure', method='bearer').inc()
            AUTH_FAILURES.labels(reason='invalid_token').inc()
            logger.warning("Token verification failed")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token or expired token"
            )
        
        AUTH_ATTEMPTS.labels(status='success', method='bearer').inc()
        logger.info(f"Successfully authenticated user: {token_data.get('sub')}")
        return token_data
    
    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM]
            )
            
            # Проверяем тип токена
            if payload.get('type') != 'access':
                logger.warning(f"Invalid token type: {payload.get('type')}")
                return None
            
            # JWT уже проверяет expiration автоматически
            # если токен expired, будет Exception выше
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token signature expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None


class TokenManager:
    """Manager для создания и обновления JWT токенов"""
    
    @staticmethod
    def create_access_token(
        user_id: str,
        scopes: list[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Создать access token
        
        Args:
            user_id: User ID
            scopes: Список разрешений (permissions)
            expires_delta: Время жизни токена
        
        Returns:
            JWT access token
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        
        payload = {
            'sub': user_id,
            'exp': int(expire.timestamp()),
            'iat': int(now.timestamp()),
            'type': 'access',
            'scopes': scopes or []
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Created access token for user {user_id}")
        
        return token
    
    @staticmethod
    def create_refresh_token(
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Создать refresh token
        
        Args:
            user_id: User ID
            expires_delta: Время жизни токена
        
        Returns:
            JWT refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        
        payload = {
            'sub': user_id,
            'exp': int(expire.timestamp()),
            'iat': int(now.timestamp()),
            'type': 'refresh'
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Created refresh token for user {user_id}")
        
        return token
    
    @staticmethod
    def verify_refresh_token(token: str) -> Optional[str]:
        """
        Verify refresh token и вернуть user_id
        
        Args:
            token: Refresh token
        
        Returns:
            User ID or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM]
            )
            
            if payload.get('type') != 'refresh':
                logger.warning("Invalid token type for refresh")
                return None
            
            return payload.get('sub')
            
        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {e}")
            return None
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token без проверки signature (для отладки)
        
        Args:
            token: JWT token
        
        Returns:
            Decoded payload or None
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False}
            )
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            return None


class PermissionChecker:
    """Проверка разрешений пользователя"""
    
    def __init__(self, required_scopes: list[str]):
        """
        Args:
            required_scopes: Требуемые разрешения
        """
        self.required_scopes = required_scopes
    
    async def __call__(self, token_data: Dict[str, Any] = None):
        """Проверить разрешения"""
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authenticated"
            )
        
        user_scopes = token_data.get('scopes', [])
        
        # Проверяем все требуемые scopes
        missing_scopes = [
            scope for scope in self.required_scopes 
            if scope not in user_scopes
        ]
        
        if missing_scopes:
            AUTH_FAILURES.labels(reason='insufficient_permissions').inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {missing_scopes}"
            )
        
        return token_data


# Predefined scopes (permissions)
class Scopes:
    """Predefined permission scopes"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    RUN_TASK = "run_task"
    VIEW_LOGS = "view_logs"
    MANAGE_WORKERS = "manage_workers"
    SANDBOX_EXEC = "sandbox_exec"
    ALL = [READ, WRITE, ADMIN, RUN_TASK, VIEW_LOGS, MANAGE_WORKERS, SANDBOX_EXEC]


# Singleton instances
jwt_bearer = JWTBearer()
token_manager = TokenManager()


# Convenience functions
def require_permissions(*scopes: str):
    """
    Decorator для проверки разрешений
    
    Usage:
        @app.get("/admin")
        @require_permissions(Scopes.ADMIN)
        async def admin_route():
            return {"message": "Admin access"}
    """
    return PermissionChecker(list(scopes))
