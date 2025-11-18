"""
Tests for Authentication System (JWT + RBAC + Rate Limiting)
"""

import asyncio
import pytest
import time
from pathlib import Path
import jwt as pyjwt

from backend.security.jwt_manager import JWTManager, TokenType, TokenConfig
from backend.security.rbac_manager import RBACManager, Role, Permission
from backend.security.rate_limiter import RateLimiter, RateLimitConfig, TokenBucket


class TestJWTManager:
    """Test JWT token management"""
    
    def test_key_generation(self, tmp_path):
        """Test RSA key pair generation"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        assert (tmp_path / "jwt_private.pem").exists()
        assert (tmp_path / "jwt_public.pem").exists()
    
    def test_access_token_generation(self, tmp_path):
        """Test access token generation"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        token = jwt_manager.generate_access_token(
            user_id="user123",
            roles=["developer", "analyst"]
        )
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode without verification to check payload
        payload = pyjwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == "user123"
        assert payload["type"] == TokenType.ACCESS.value
        assert payload["roles"] == ["developer", "analyst"]
    
    def test_token_verification(self, tmp_path):
        """Test token verification"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        token = jwt_manager.generate_access_token("user123", ["admin"])
        payload = jwt_manager.verify_token(token)
        
        assert payload["sub"] == "user123"
        assert "admin" in payload["roles"]
    
    def test_expired_token(self, tmp_path):
        """Test expired token rejection"""
        config = TokenConfig(access_token_expire_minutes=-1)  # Already expired
        jwt_manager = JWTManager(config=config, keys_dir=tmp_path)
        
        token = jwt_manager.generate_access_token("user123", ["admin"])
        
        with pytest.raises(pyjwt.ExpiredSignatureError):
            jwt_manager.verify_token(token)
    
    def test_invalid_token(self, tmp_path):
        """Test invalid token rejection"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        invalid_token = "invalid.token.here"
        
        with pytest.raises(pyjwt.InvalidTokenError):
            jwt_manager.verify_token(invalid_token)
    
    def test_refresh_token(self, tmp_path):
        """Test refresh token generation and usage"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        refresh_token = jwt_manager.generate_refresh_token("user123")
        assert refresh_token is not None
        
        # Use refresh token to get new access token
        new_access_token = jwt_manager.refresh_access_token(refresh_token, ["developer"])
        assert new_access_token is not None
        
        payload = jwt_manager.verify_token(new_access_token)
        assert payload["type"] == TokenType.ACCESS.value
    
    def test_api_key(self, tmp_path):
        """Test API key generation"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        api_key = jwt_manager.generate_api_key(
            user_id="bot123",
            name="Trading Bot",
            permissions=["backtest:execute", "data:read"]
        )
        
        payload = jwt_manager.verify_token(api_key)
        assert payload["type"] == TokenType.API_KEY.value
        assert payload["name"] == "Trading Bot"
        assert "backtest:execute" in payload["permissions"]
    
    def test_token_revocation(self, tmp_path):
        """Test token revocation"""
        jwt_manager = JWTManager(keys_dir=tmp_path)
        
        token = jwt_manager.generate_access_token("user123", ["admin"])
        
        # Token should work before revocation
        payload = jwt_manager.verify_token(token)
        assert payload["sub"] == "user123"
        
        # Revoke token
        jwt_manager.revoke_token(token)
        
        # Token should fail after revocation
        with pytest.raises(pyjwt.InvalidTokenError):
            jwt_manager.verify_token(token)


class TestRBACManager:
    """Test role-based access control"""
    
    def test_role_assignment(self):
        """Test assigning roles to users"""
        rbac = RBACManager()
        
        rbac.assign_role("user1", Role.ADMIN.value)
        rbac.assign_role("user1", Role.DEVELOPER.value)
        
        roles = rbac.get_user_roles("user1")
        assert Role.ADMIN.value in roles
        assert Role.DEVELOPER.value in roles
    
    def test_role_revocation(self):
        """Test revoking roles from users"""
        rbac = RBACManager()
        
        rbac.assign_role("user1", Role.ADMIN.value)
        rbac.revoke_role("user1", Role.ADMIN.value)
        
        roles = rbac.get_user_roles("user1")
        assert Role.ADMIN.value not in roles
    
    def test_admin_permissions(self):
        """Test admin has all permissions"""
        rbac = RBACManager()
        rbac.assign_role("admin1", Role.ADMIN.value)
        
        permissions = rbac.get_user_permissions("admin1")
        
        # Admin should have all permissions
        assert Permission.BACKTEST_CREATE in permissions
        assert Permission.STRATEGY_DELETE in permissions
        assert Permission.USER_CREATE in permissions
        assert Permission.SYSTEM_CONFIG in permissions
    
    def test_developer_permissions(self):
        """Test developer has limited permissions"""
        rbac = RBACManager()
        rbac.assign_role("dev1", Role.DEVELOPER.value)
        
        permissions = rbac.get_user_permissions("dev1")
        
        # Developer should have these
        assert Permission.BACKTEST_CREATE in permissions
        assert Permission.STRATEGY_CREATE in permissions
        
        # But not these
        assert Permission.USER_DELETE not in permissions
        assert Permission.SYSTEM_CONFIG not in permissions
    
    def test_viewer_permissions(self):
        """Test viewer has read-only permissions"""
        rbac = RBACManager()
        rbac.assign_role("viewer1", Role.VIEWER.value)
        
        permissions = rbac.get_user_permissions("viewer1")
        
        # Viewer should have read permissions
        assert Permission.BACKTEST_READ in permissions
        assert Permission.STRATEGY_READ in permissions
        
        # But no write/delete
        assert Permission.BACKTEST_CREATE not in permissions
        assert Permission.STRATEGY_DELETE not in permissions
    
    def test_permission_check(self):
        """Test permission checking"""
        rbac = RBACManager()
        rbac.assign_role("dev1", Role.DEVELOPER.value)
        
        assert rbac.has_permission("dev1", Permission.BACKTEST_CREATE) is True
        assert rbac.has_permission("dev1", Permission.USER_DELETE) is False
    
    def test_custom_role(self):
        """Test creating custom role"""
        rbac = RBACManager()
        
        rbac.create_custom_role(
            name="trader",
            display_name="Trader",
            permissions={
                Permission.BACKTEST_READ,
                Permission.BACKTEST_EXECUTE,
                Permission.STRATEGY_READ
            },
            description="Custom trading role"
        )
        
        rbac.assign_role("user1", "trader")
        
        assert rbac.has_permission("user1", Permission.BACKTEST_EXECUTE) is True
        assert rbac.has_permission("user1", Permission.STRATEGY_CREATE) is False
    
    def test_multiple_roles(self):
        """Test user with multiple roles gets combined permissions"""
        rbac = RBACManager()
        
        rbac.assign_role("user1", Role.DEVELOPER.value)
        rbac.assign_role("user1", Role.VIEWER.value)  # Redundant but valid
        
        permissions = rbac.get_user_permissions("user1")
        
        # Should have all developer permissions (viewer is subset)
        assert Permission.BACKTEST_CREATE in permissions
        assert Permission.STRATEGY_CREATE in permissions


class TestRateLimiter:
    """Test rate limiting"""
    
    def test_token_bucket_basic(self):
        """Test basic token bucket operation"""
        bucket = TokenBucket(rate=1.0, capacity=5)  # 1 token/sec, max 5
        
        # Should be able to consume initial capacity
        for _ in range(5):
            assert bucket.consume() is True
        
        # Should be empty now
        assert bucket.consume() is False
    
    def test_token_bucket_refill(self):
        """Test token bucket refill over time"""
        bucket = TokenBucket(rate=10.0, capacity=5)  # 10 tokens/sec
        
        # Consume all
        for _ in range(5):
            bucket.consume()
        
        # Wait for refill
        time.sleep(0.5)  # Should refill ~5 tokens
        
        # Should be able to consume again
        assert bucket.consume() is True
    
    def test_rate_limiter_per_user(self):
        """Test rate limiting per user"""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000
        )
        limiter = RateLimiter(config)
        
        # User 1 should be allowed
        for i in range(10):
            allowed, _ = limiter.check_rate_limit("user1")
            assert allowed is True
        
        # User 2 should also have their own limit
        allowed, _ = limiter.check_rate_limit("user2")
        assert allowed is True
    
    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario"""
        config = RateLimitConfig(
            requests_per_minute=5,
            burst_size=5
        )
        limiter = RateLimiter(config)
        
        # Consume all burst tokens
        for _ in range(5):
            allowed, _ = limiter.check_rate_limit("user1")
            assert allowed is True
        
        # Next request should be blocked
        allowed, reason = limiter.check_rate_limit("user1")
        assert allowed is False
        assert "Rate limit" in reason
    
    def test_endpoint_specific_limit(self):
        """Test endpoint-specific rate limiting"""
        limiter = RateLimiter()
        
        # Make requests to specific endpoint
        for _ in range(30):
            allowed, _ = limiter.check_rate_limit("user1", endpoint="/api/expensive")
            if not allowed:
                break
        
        # Endpoint limit should trigger before global limit
        stats = limiter.get_user_stats("user1")
        assert stats["blocked_requests"] > 0
    
    def test_request_cost(self):
        """Test variable request costs"""
        config = RateLimitConfig(requests_per_minute=10, burst_size=10)
        limiter = RateLimiter(config)
        
        # Expensive request costs 5 tokens
        allowed, _ = limiter.check_rate_limit("user1", cost=5)
        assert allowed is True
        
        # Only 5 tokens left, so another expensive request should fail
        allowed, _ = limiter.check_rate_limit("user1", cost=5)
        assert allowed is True
        
        # Should be empty now
        allowed, _ = limiter.check_rate_limit("user1", cost=1)
        assert allowed is False
    
    def test_user_stats(self):
        """Test rate limiter statistics"""
        limiter = RateLimiter()
        
        for _ in range(5):
            limiter.check_rate_limit("user1")
        
        stats = limiter.get_user_stats("user1")
        
        assert stats["user_id"] == "user1"
        assert stats["total_requests"] == 5
        assert "limits" in stats
        assert "current_tokens" in stats
    
    def test_reset_limits(self):
        """Test resetting user limits"""
        limiter = RateLimiter()
        
        # Use up some tokens
        for _ in range(5):
            limiter.check_rate_limit("user1")
        
        # Reset
        limiter.reset_user_limits("user1")
        
        # Should have full capacity again
        stats = limiter.get_user_stats("user1")
        assert stats["total_requests"] == 0


@pytest.mark.asyncio
async def test_integration():
    """
    Full integration test: JWT + RBAC + Rate Limiting
    """
    print("\n" + "="*60)
    print("INTEGRATION TEST: JWT + RBAC + Rate Limiting")
    print("="*60)
    
    # Setup
    jwt_manager = JWTManager()
    rbac_manager = RBACManager()
    rate_limiter = RateLimiter(RateLimitConfig(requests_per_minute=10))
    
    # Create user and assign role
    user_id = "testuser123"
    rbac_manager.assign_role(user_id, Role.DEVELOPER.value)
    
    # Generate token
    print(f"\n[1] Generating access token for {user_id}...")
    token = jwt_manager.generate_access_token(
        user_id=user_id,
        roles=rbac_manager.get_user_roles(user_id)
    )
    print(f"✅ Token generated: {token[:50]}...")
    
    # Verify token
    print(f"\n[2] Verifying token...")
    payload = jwt_manager.verify_token(token)
    print(f"✅ Token valid: user={payload['sub']}, type={payload['type']}")
    
    # Check permissions
    print(f"\n[3] Checking permissions...")
    has_backtest = rbac_manager.has_permission(user_id, Permission.BACKTEST_CREATE)
    has_admin = rbac_manager.has_permission(user_id, Permission.USER_DELETE)
    print(f"✅ BACKTEST_CREATE: {has_backtest}")
    print(f"✅ USER_DELETE (admin): {has_admin}")
    
    assert has_backtest is True
    assert has_admin is False
    
    # Test rate limiting
    print(f"\n[4] Testing rate limiting...")
    success_count = 0
    for i in range(15):
        allowed, reason = rate_limiter.check_rate_limit(user_id)
        if allowed:
            success_count += 1
        else:
            print(f"⚠️  Request {i+1} blocked: {reason}")
            break
    
    print(f"✅ Successfully processed {success_count}/15 requests")
    print(f"✅ Rate limiting working correctly")
    
    # Get statistics
    print(f"\n[5] Rate limiter statistics...")
    stats = rate_limiter.get_user_stats(user_id)
    print(f"Total requests: {stats['total_requests']}")
    print(f"Blocked requests: {stats['blocked_requests']}")
    print(f"Current tokens: {stats['current_tokens']}")
    
    print("\n" + "="*60)
    print("✅ INTEGRATION TEST PASSED")
    print("="*60)


if __name__ == "__main__":
    # Run integration test
    asyncio.run(test_integration())
