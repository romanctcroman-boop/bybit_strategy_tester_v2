"""
WebSocket Authentication Module.

Provides token-based authentication for WebSocket connections.
Supports:
1. Query parameter token: ws://host/ws?token=xxx
2. API key header: X-API-Key header (for HTTP upgrade requests)

Security:
- Tokens can be short-lived session tokens or long-lived API keys
- Rate limiting applied per token/API key
- Anonymous access configurable via ALLOW_ANONYMOUS_WS env var
"""

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Query, WebSocket

# Configuration
ALLOW_ANONYMOUS_WS = os.environ.get("ALLOW_ANONYMOUS_WS", "true").lower() == "true"
WS_SECRET_KEY = os.environ.get("WS_SECRET_KEY", "dev-secret-change-in-production")
WS_TOKEN_TTL_SECONDS = int(os.environ.get("WS_TOKEN_TTL_SECONDS", "3600"))  # 1 hour


@dataclass
class WSAuthResult:
    """Result of WebSocket authentication."""

    authenticated: bool
    user_id: Optional[str] = None
    is_anonymous: bool = False
    error: Optional[str] = None
    token_type: str = "none"  # none, session, api_key


class WSAuthenticator:
    """
    WebSocket authenticator with support for multiple auth methods.

    Usage:
        auth = WSAuthenticator()

        @router.websocket("/ws/stream")
        async def websocket_stream(websocket: WebSocket, token: str = Query(None)):
            auth_result = await auth.authenticate(websocket, token)
            if not auth_result.authenticated:
                await websocket.close(code=4001, reason=auth_result.error)
                return
            # ... proceed with authenticated connection
    """

    def __init__(
        self,
        allow_anonymous: bool = None,
        secret_key: str = None,
        token_ttl: int = None,
    ):
        self.allow_anonymous = (
            allow_anonymous if allow_anonymous is not None else ALLOW_ANONYMOUS_WS
        )
        self.secret_key = secret_key or WS_SECRET_KEY
        self.token_ttl = token_ttl or WS_TOKEN_TTL_SECONDS

        # API keys cache (in production, load from DB/Redis)
        self._api_keys: dict[str, str] = {}  # api_key_hash -> user_id
        self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from environment or file."""
        # Simple loading from env for development
        # Format: WS_API_KEY_user1=key1,WS_API_KEY_user2=key2
        for key, value in os.environ.items():
            if key.startswith("WS_API_KEY_"):
                user_id = key.replace("WS_API_KEY_", "")
                key_hash = self._hash_key(value)
                self._api_keys[key_hash] = user_id

    def _hash_key(self, key: str) -> str:
        """Hash API key for secure storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    def generate_session_token(self, user_id: str) -> str:
        """
        Generate a short-lived session token.

        Format: base64(user_id:timestamp:signature)
        """
        import base64

        timestamp = int(time.time())
        payload = f"{user_id}:{timestamp}"

        signature = hmac.new(
            self.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:16]

        token_data = f"{payload}:{signature}"
        return base64.urlsafe_b64encode(token_data.encode()).decode()

    def verify_session_token(self, token: str) -> tuple[bool, Optional[str], str]:
        """
        Verify session token.

        Returns: (valid: bool, user_id: Optional[str], error: str)
        """
        import base64

        try:
            token_data = base64.urlsafe_b64decode(token.encode()).decode()
            parts = token_data.split(":")

            if len(parts) != 3:
                return False, None, "Invalid token format"

            user_id, timestamp_str, signature = parts
            timestamp = int(timestamp_str)

            # Check expiration
            if time.time() - timestamp > self.token_ttl:
                return False, None, "Token expired"

            # Verify signature
            payload = f"{user_id}:{timestamp_str}"
            expected_sig = hmac.new(
                self.secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()[:16]

            if not hmac.compare_digest(signature, expected_sig):
                return False, None, "Invalid signature"

            return True, user_id, ""

        except Exception as e:
            return False, None, f"Token verification failed: {e}"

    def verify_api_key(self, api_key: str) -> tuple[bool, Optional[str], str]:
        """
        Verify API key.

        Returns: (valid: bool, user_id: Optional[str], error: str)
        """
        key_hash = self._hash_key(api_key)

        if key_hash in self._api_keys:
            return True, self._api_keys[key_hash], ""

        return False, None, "Invalid API key"

    async def authenticate(
        self, websocket: WebSocket, token: str = None
    ) -> WSAuthResult:
        """
        Authenticate WebSocket connection.

        Checks in order:
        1. Query parameter token
        2. X-API-Key header
        3. Anonymous access (if allowed)
        """
        # 1. Check query token (session token)
        if token:
            valid, user_id, error = self.verify_session_token(token)
            if valid:
                return WSAuthResult(
                    authenticated=True,
                    user_id=user_id,
                    is_anonymous=False,
                    token_type="session",
                )
            # Try as API key
            valid, user_id, error = self.verify_api_key(token)
            if valid:
                return WSAuthResult(
                    authenticated=True,
                    user_id=user_id,
                    is_anonymous=False,
                    token_type="api_key",
                )
            return WSAuthResult(authenticated=False, error=error)

        # 2. Check X-API-Key header
        api_key = websocket.headers.get("x-api-key")
        if api_key:
            valid, user_id, error = self.verify_api_key(api_key)
            if valid:
                return WSAuthResult(
                    authenticated=True,
                    user_id=user_id,
                    is_anonymous=False,
                    token_type="api_key",
                )
            return WSAuthResult(authenticated=False, error=error)

        # 3. Anonymous access
        if self.allow_anonymous:
            # Generate anonymous ID from client IP for rate limiting
            client_ip = websocket.client.host if websocket.client else "unknown"
            anon_id = f"anon:{hashlib.md5(client_ip.encode()).hexdigest()[:8]}"

            return WSAuthResult(
                authenticated=True,
                user_id=anon_id,
                is_anonymous=True,
                token_type="none",
            )

        return WSAuthResult(authenticated=False, error="Authentication required")


# Singleton authenticator
_authenticator: Optional[WSAuthenticator] = None


def get_ws_authenticator() -> WSAuthenticator:
    """Get singleton authenticator instance."""
    global _authenticator
    if _authenticator is None:
        _authenticator = WSAuthenticator()
    return _authenticator


async def ws_auth_dependency(
    websocket: WebSocket, token: str = Query(None)
) -> WSAuthResult:
    """
    FastAPI dependency for WebSocket authentication.

    Usage:
        @router.websocket("/ws/stream")
        async def stream(
            websocket: WebSocket,
            auth: WSAuthResult = Depends(ws_auth_dependency)
        ):
            if not auth.authenticated:
                await websocket.close(4001, auth.error)
                return
            await websocket.accept()
            ...
    """
    auth = get_ws_authenticator()
    return await auth.authenticate(websocket, token)
