"""
Security module for API key management, encryption, authentication, authorization, and secure logging
"""
from .key_manager import KeyManager, get_decrypted_key
from .crypto import CryptoManager
from .audit_logger import audit_logger
from .jwt_manager import JWTManager, TokenType, TokenConfig
from .rbac_manager import RBACManager, Role, Permission
from .rate_limiter import RateLimiter, RateLimitConfig
from .auth_middleware import (
    AuthenticationMiddleware,
    get_current_user,
    get_current_user_roles,
    require_permission,
    require_role,
    setup_authentication
)
from .secure_logger import (
    StructuredLogger,
    SensitiveDataFilter,
    security_logger,
    api_logger,
    sandbox_logger,
    backtest_logger
)
from .logging_middleware import (
    SecureLoggingMiddleware,
    SecurityEventMiddleware
)

__all__ = [
    # Key management
    'KeyManager',
    'get_decrypted_key',
    'CryptoManager',
    'audit_logger',
    
    # Authentication & Authorization
    'JWTManager',
    'TokenType',
    'TokenConfig',
    'RBACManager',
    'Role',
    'Permission',
    'RateLimiter',
    'RateLimitConfig',
    'AuthenticationMiddleware',
    'get_current_user',
    'get_current_user_roles',
    'require_permission',
    'require_role',
    'setup_authentication',
    
    # Secure Logging
    'StructuredLogger',
    'SensitiveDataFilter',
    'security_logger',
    'api_logger',
    'sandbox_logger',
    'backtest_logger',
    'SecureLoggingMiddleware',
    'SecurityEventMiddleware'
]
