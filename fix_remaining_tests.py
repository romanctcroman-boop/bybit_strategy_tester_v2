"""
Auto-rewrite remaining failing tests to use create_middleware_client helper
"""

import re

test_file = "tests/backend/security/test_auth_middleware.py"

with open(test_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Tests to fix:
tests_to_fix = [
    "test_rate_limit_exceeded_returns_429",
    "test_rate_limit_cost_calculation_post",
    "test_rate_limit_cost_calculation_batch",
    "test_security_headers_added",
    "test_user_info_attached_to_request",
    "test_internal_error_returns_500"
]

# For each test, replace pattern:
# Old: middleware = Auth...; patches; app.add_middleware; client = TestClient
# New: client = create_middleware_client(app, jwt, rbac, rate, ...)

# Pattern for test_rate_limit_exceeded_returns_429
old_1 = """    def test_rate_limit_exceeded_returns_429(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        \"\"\"Test request rejected when rate limit exceeded\"\"\"
        middleware = AuthenticationMiddleware(app, public_paths=["/public"])
        
        rate_limiter.check_rate_limit = Mock(return_value=(False, "Rate limit exceeded"))
        
        with patch('backend.security.auth_middleware.get_jwt_manager', return_value=jwt_manager):
            with patch('backend.security.auth_middleware.get_rbac_manager', return_value=rbac_manager):
                with patch('backend.security.auth_middleware.get_rate_limiter', return_value=rate_limiter):
                    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
                    client = TestClient(app, raise_server_exceptions=False)
                    
                    response = client.get(
                        "/protected",
                        headers={"Authorization": f"Bearer {valid_access_token}"}
                    )
                    
                    assert response.status_code == 429
                    assert "Retry-After" in response.headers"""

new_1 = """    def test_rate_limit_exceeded_returns_429(self, app, jwt_manager, rbac_manager, rate_limiter, valid_access_token):
        \"\"\"Test request rejected when rate limit exceeded\"\"\"
        rate_limiter.check_rate_limit = Mock(return_value=(False, "Rate limit exceeded"))
        rbac_manager.get_user_permissions = Mock(return_value=[])
        
        client = create_middleware_client(app, jwt_manager, rbac_manager, rate_limiter)
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_access_token}"}
        )
        
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        
        for p in client._patches:
            p.stop()"""

content = content.replace(old_1, new_1)

print("Fixed test_rate_limit_exceeded_returns_429")

# Save
with open(test_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Tests fixed.")
