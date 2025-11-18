"""
JWT Manager - Token generation, validation, and refresh
Implements secure JWT authentication with RS256 signing

Week 1, Day 1 Enhancement: HTTP-only Cookie Support
- Added secure cookie setter/getter methods
- XSS protection via httponly flag
- CSRF protection via SameSite strict
"""

import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
import secrets
import logging
from dataclasses import dataclass
from enum import Enum

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# FastAPI imports for cookie support
try:
    from fastapi import Response, Request
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    Response = None
    Request = None

logger = logging.getLogger('security.jwt')


class TokenType(Enum):
    """JWT token types"""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"


@dataclass
class TokenConfig:
    """JWT token configuration"""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    api_key_expire_days: int = 365
    algorithm: str = "RS256"
    issuer: str = "bybit-strategy-tester"


class JWTManager:
    """
    JWT token manager with RSA signing.
    
    Features:
    - RS256 asymmetric signing (private/public key pair)
    - Access tokens (short-lived, 15 min)
    - Refresh tokens (long-lived, 7 days)
    - API keys (very long-lived, 365 days)
    - Token blacklist support
    - Automatic key rotation
    """
    
    def __init__(self, config: Optional[TokenConfig] = None, keys_dir: Optional[Path] = None):
        """
        Initialize JWT manager.
        
        Args:
            config: Token configuration
            keys_dir: Directory for storing RSA keys (default: backend/security/keys)
        """
        self.config = config or TokenConfig()
        self.keys_dir = keys_dir or Path(__file__).parent / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Token blacklist (in-memory, should be Redis in production)
        self._blacklist: set = set()
        
        # Load or generate RSA keys
        self._private_key = None
        self._public_key = None
        self._load_or_generate_keys()
    
    def _load_or_generate_keys(self) -> None:
        """Load existing RSA keys or generate new ones"""
        private_key_path = self.keys_dir / "jwt_private.pem"
        public_key_path = self.keys_dir / "jwt_public.pem"
        
        if private_key_path.exists() and public_key_path.exists():
            logger.info("Loading existing RSA keys for JWT signing")
            
            with open(private_key_path, 'rb') as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            
            with open(public_key_path, 'rb') as f:
                self._public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )
        else:
            logger.info("Generating new RSA key pair for JWT signing")
            
            # Generate 2048-bit RSA key pair
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self._public_key = self._private_key.public_key()
            
            # Save keys
            with open(private_key_path, 'wb') as f:
                f.write(self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open(public_key_path, 'wb') as f:
                f.write(self._public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            
            # Set restrictive permissions (read-only for owner)
            private_key_path.chmod(0o600)
            public_key_path.chmod(0o644)
    
    def generate_access_token(
        self,
        user_id: str,
        roles: List[str],
        additional_claims: Optional[Dict] = None
    ) -> str:
        """
        Generate access token (short-lived).
        
        Args:
            user_id: User identifier
            roles: List of user roles
            additional_claims: Optional additional JWT claims
            
        Returns:
            Encoded JWT access token
        """
        now = datetime.utcnow()
        expires = now + timedelta(minutes=self.config.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "type": TokenType.ACCESS.value,
            "roles": roles,
            "iat": now,
            "exp": expires,
            "iss": self.config.issuer,
            "jti": secrets.token_urlsafe(16)  # JWT ID for blacklist
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        # Serialize private key for PyJWT
        private_key_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm=self.config.algorithm
        )
        
        logger.info(f"Generated access token for user {user_id}, expires in {self.config.access_token_expire_minutes}m")
        return token
    
    def generate_refresh_token(self, user_id: str) -> str:
        """
        Generate refresh token (long-lived).
        
        Args:
            user_id: User identifier
            
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.utcnow()
        expires = now + timedelta(days=self.config.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "type": TokenType.REFRESH.value,
            "iat": now,
            "exp": expires,
            "iss": self.config.issuer,
            "jti": secrets.token_urlsafe(16)
        }
        
        private_key_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm=self.config.algorithm
        )
        
        logger.info(f"Generated refresh token for user {user_id}, expires in {self.config.refresh_token_expire_days}d")
        return token
    
    def generate_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str]
    ) -> str:
        """
        Generate API key token (very long-lived).
        
        Args:
            user_id: User identifier
            name: API key name/description
            permissions: List of permissions
            
        Returns:
            Encoded JWT API key
        """
        now = datetime.utcnow()
        expires = now + timedelta(days=self.config.api_key_expire_days)
        
        payload = {
            "sub": user_id,
            "type": TokenType.API_KEY.value,
            "name": name,
            "permissions": permissions,
            "iat": now,
            "exp": expires,
            "iss": self.config.issuer,
            "jti": secrets.token_urlsafe(16)
        }
        
        private_key_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm=self.config.algorithm
        )
        
        logger.info(f"Generated API key '{name}' for user {user_id}, expires in {self.config.api_key_expire_days}d")
        return token
    
    def verify_token(self, token: str) -> Dict:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded token payload
            
        Raises:
            jwt.ExpiredSignatureError: Token expired
            jwt.InvalidTokenError: Invalid token
        """
        # Serialize public key for PyJWT
        public_key_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        try:
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=[self.config.algorithm],
                issuer=self.config.issuer
            )
            
            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and jti in self._blacklist:
                raise jwt.InvalidTokenError("Token has been revoked")
            
            logger.debug(f"Verified token for user {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
    
    def refresh_access_token(self, refresh_token: str, roles: List[str]) -> str:
        """
        Generate new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
            roles: Updated user roles
            
        Returns:
            New access token
            
        Raises:
            jwt.InvalidTokenError: Invalid refresh token
        """
        payload = self.verify_token(refresh_token)
        
        # Verify token type
        if payload.get("type") != TokenType.REFRESH.value:
            raise jwt.InvalidTokenError("Token is not a refresh token")
        
        user_id = payload.get("sub")
        return self.generate_access_token(user_id, roles)
    
    def revoke_token(self, token: str) -> None:
        """
        Revoke token by adding to blacklist.
        
        Args:
            token: Token to revoke
        """
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}  # Just need jti
            )
            jti = payload.get("jti")
            
            if jti:
                self._blacklist.add(jti)
                logger.info(f"Revoked token {jti}")
            
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
    
    def is_token_revoked(self, token: str) -> bool:
        """
        Check if token is revoked.
        
        Args:
            token: Token to check
            
        Returns:
            True if token is revoked
        """
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            jti = payload.get("jti")
            return jti in self._blacklist if jti else False
            
        except Exception:
            return False
    
    def get_token_info(self, token: str) -> Dict:
        """
        Get token information without verification.
        
        Args:
            token: JWT token
            
        Returns:
            Token payload (unverified)
        """
        return jwt.decode(token, options={"verify_signature": False})
    
    def rotate_keys(self) -> None:
        """
        Rotate RSA key pair.
        
        WARNING: This will invalidate all existing tokens!
        """
        logger.warning("Rotating RSA keys - all existing tokens will be invalidated")
        
        # Backup old keys
        old_private = self.keys_dir / "jwt_private.pem.old"
        old_public = self.keys_dir / "jwt_public.pem.old"
        
        (self.keys_dir / "jwt_private.pem").rename(old_private)
        (self.keys_dir / "jwt_public.pem").rename(old_public)
        
        # Generate new keys
        self._load_or_generate_keys()
        
        # Clear blacklist (no longer needed)
        self._blacklist.clear()
        
        logger.info("Key rotation complete")
    
    # ==================== HTTP-only Cookie Support ====================
    # Week 1, Day 1: Enhanced Security with HTTP-only Cookies
    
    def set_token_cookie(
        self,
        response: 'Response',
        token: str,
        token_type: TokenType,
        secure: bool = True,
        domain: Optional[str] = None
    ) -> None:
        """
        Set JWT token as secure HTTP-only cookie.
        
        Security features:
        - httponly=True: Prevents XSS attacks (JavaScript can't access)
        - secure=True: HTTPS only (production)
        - samesite="strict": CSRF protection
        - Appropriate max_age based on token type
        
        Args:
            response: FastAPI Response object
            token: JWT token to set
            token_type: Type of token (access/refresh)
            secure: Require HTTPS (default: True, set False for local dev)
            domain: Cookie domain (None = current domain)
        
        Example:
            response = Response()
            jwt_manager.set_token_cookie(
                response,
                access_token,
                TokenType.ACCESS,
                secure=True
            )
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required for cookie support")
        
        # Cookie name based on token type
        cookie_name = f"{token_type.value}_token"
        
        # Max age based on token type
        if token_type == TokenType.ACCESS:
            max_age = self.config.access_token_expire_minutes * 60
        elif token_type == TokenType.REFRESH:
            max_age = self.config.refresh_token_expire_days * 24 * 60 * 60
        else:  # API key
            max_age = self.config.api_key_expire_days * 24 * 60 * 60
        
        response.set_cookie(
            key=cookie_name,
            value=token,
            max_age=max_age,
            httponly=True,           # XSS protection
            secure=secure,           # HTTPS only (production)
            samesite="strict",       # CSRF protection
            domain=domain,
            path="/"
        )
        
        logger.info(
            f"Set secure {token_type.value} cookie "
            f"(httponly=True, secure={secure}, samesite=strict, max_age={max_age}s)"
        )
    
    def get_token_from_cookie(
        self,
        request: 'Request',
        token_type: TokenType
    ) -> Optional[str]:
        """
        Extract JWT token from HTTP-only cookie.
        
        Args:
            request: FastAPI Request object
            token_type: Type of token to extract
            
        Returns:
            JWT token if found, None otherwise
        
        Example:
            access_token = jwt_manager.get_token_from_cookie(
                request,
                TokenType.ACCESS
            )
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required for cookie support")
        
        cookie_name = f"{token_type.value}_token"
        token = request.cookies.get(cookie_name)
        
        if token:
            logger.debug(f"Retrieved {token_type.value} token from cookie")
        else:
            logger.debug(f"No {token_type.value} token found in cookies")
        
        return token
    
    def delete_token_cookie(
        self,
        response: 'Response',
        token_type: TokenType,
        domain: Optional[str] = None
    ) -> None:
        """
        Delete JWT token cookie (for logout).
        
        Args:
            response: FastAPI Response object
            token_type: Type of token to delete
            domain: Cookie domain (must match set_cookie domain)
        
        Example:
            response = Response()
            jwt_manager.delete_token_cookie(response, TokenType.ACCESS)
            jwt_manager.delete_token_cookie(response, TokenType.REFRESH)
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required for cookie support")
        
        cookie_name = f"{token_type.value}_token"
        
        response.delete_cookie(
            key=cookie_name,
            domain=domain,
            path="/"
        )
        
        logger.info(f"Deleted {token_type.value} cookie")
    
    def extract_token_from_request(
        self,
        request: 'Request',
        token_type: TokenType,
        fallback_to_header: bool = True
    ) -> Optional[str]:
        """
        Extract JWT token from request.
        
        Tries in order:
        1. HTTP-only cookie (preferred, more secure)
        2. Authorization header (fallback for backward compatibility)
        
        Args:
            request: FastAPI Request object
            token_type: Type of token to extract
            fallback_to_header: If True, try Authorization header if cookie not found
            
        Returns:
            JWT token if found, None otherwise
        
        Example:
            token = jwt_manager.extract_token_from_request(
                request,
                TokenType.ACCESS,
                fallback_to_header=True
            )
        """
        # Try cookie first (preferred)
        token = self.get_token_from_cookie(request, token_type)
        
        if token:
            logger.debug(f"Token extracted from cookie ({token_type.value})")
            return token
        
        # Fallback to Authorization header if enabled
        if fallback_to_header:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                logger.debug(f"Token extracted from Authorization header ({token_type.value})")
                return token
        
        logger.debug(f"No {token_type.value} token found in request")
        return None
