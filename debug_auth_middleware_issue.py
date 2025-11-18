"""
Debug auth_middleware 500 errors
"""

import asyncio
from unittest.mock import Mock, patch
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.security.auth_middleware import AuthenticationMiddleware, get_jwt_manager, get_rbac_manager, get_rate_limiter
from backend.security.jwt_manager import JWTManager, TokenConfig
from backend.security.rbac_manager import RBACManager
from backend.security.rate_limiter import RateLimiter, RateLimitConfig

# Create test app
app = FastAPI()

@app.get("/protected")
async def protected_endpoint(request: Request):
    return {
        "user_id": request.state.user_id,
        "roles": request.state.roles
    }

# Create fixtures
jwt_manager = JWTManager(config=TokenConfig(
    access_token_expire_minutes=15,
    refresh_token_expire_days=7
))

rbac_manager = RBACManager()
rate_limiter = RateLimiter(config=RateLimitConfig(
    requests_per_minute=60,
    requests_per_hour=1000
))

# Patch and create middleware
with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
    with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
        with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
            middleware = AuthenticationMiddleware(app, public_paths=["/public"])
            app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
            
            print(f"Middleware created OK")
            print(f"jwt_manager: {middleware.jwt_manager}")
            print(f"rbac_manager: {middleware.rbac_manager}")
            print(f"rate_limiter: {middleware.rate_limiter}")
            
            # Test without TestClient - create minimal request
            from starlette.requests import Request
            from starlette.responses import Response
            from starlette.datastructures import URL, Headers
            
            # Simulate ASGI scope for /protected
            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/protected',
                'query_string': b'',
                'headers': [],
                'server': ('testserver', 80),
                'scheme': 'http',
                'root_path': ''
            }
            
            async def receive():
                return {'type': 'http.request', 'body': b''}
            
            responses = []
            async def send(message):
                responses.append(message)
            
            # Test missing token scenario
            async def test_missing_token():
                try:
                    request = Request(scope)
                    
                    async def call_next(req):
                        return Response("OK", status_code=200)
                    
                    response = await middleware.dispatch(request, call_next)
                    print(f"Response status: {response.status_code}")
                    print(f"Response body: {response.body}")
                    
                except Exception as e:
                    print(f"Exception: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
            
            asyncio.run(test_missing_token())
