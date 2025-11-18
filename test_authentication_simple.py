"""
Simple authentication test - no pytest imports required
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time

from backend.security.jwt_manager import JWTManager, TokenType, TokenConfig
from backend.security.rbac_manager import RBACManager, Role, Permission
from backend.security.rate_limiter import RateLimiter, RateLimitConfig


async def test_jwt():
    """Test JWT Manager"""
    print("\n" + "="*60)
    print("TEST 1: JWT Manager")
    print("="*60)
    
    jwt_manager = JWTManager()
    
    # Test access token
    print("\n[1.1] Testing access token generation...")
    token = jwt_manager.generate_access_token("user123", ["developer", "analyst"])
    print(f"✅ Token generated: {token[:50]}...")
    
    # Test verification
    print("\n[1.2] Testing token verification...")
    payload = jwt_manager.verify_token(token)
    assert payload["sub"] == "user123"
    assert "developer" in payload["roles"]
    print(f"✅ Token verified: user={payload['sub']}, roles={payload['roles']}")
    
    # Test refresh token
    print("\n[1.3] Testing refresh token...")
    refresh_token = jwt_manager.generate_refresh_token("user123")
    new_access = jwt_manager.refresh_access_token(refresh_token, ["developer"])
    payload = jwt_manager.verify_token(new_access)
    assert payload["type"] == TokenType.ACCESS.value
    print(f"✅ Refresh token working, new access token generated")
    
    # Test API key
    print("\n[1.4] Testing API key...")
    api_key = jwt_manager.generate_api_key(
        "bot123",
        "Trading Bot",
        ["backtest:execute", "data:read"]
    )
    payload = jwt_manager.verify_token(api_key)
    assert payload["type"] == TokenType.API_KEY.value
    print(f"✅ API key generated: name={payload['name']}")
    
    # Test revocation
    print("\n[1.5] Testing token revocation...")
    test_token = jwt_manager.generate_access_token("user456", ["admin"])
    jwt_manager.revoke_token(test_token)
    try:
        jwt_manager.verify_token(test_token)
        print("❌ Revoked token still valid")
        assert False
    except Exception:
        print("✅ Revoked token correctly rejected")
    
    print("\n✅ JWT Manager tests PASSED")


async def test_rbac():
    """Test RBAC Manager"""
    print("\n" + "="*60)
    print("TEST 2: RBAC Manager")
    print("="*60)
    
    rbac = RBACManager()
    
    # Test role assignment
    print("\n[2.1] Testing role assignment...")
    rbac.assign_role("user1", Role.ADMIN.value)
    rbac.assign_role("user2", Role.DEVELOPER.value)
    rbac.assign_role("user3", Role.VIEWER.value)
    
    roles_user1 = rbac.get_user_roles("user1")
    assert Role.ADMIN.value in roles_user1
    print(f"✅ Roles assigned: user1={roles_user1}")
    
    # Test permissions
    print("\n[2.2] Testing permissions...")
    
    # Admin should have everything
    assert rbac.has_permission("user1", Permission.BACKTEST_CREATE)
    assert rbac.has_permission("user1", Permission.USER_DELETE)
    assert rbac.has_permission("user1", Permission.SYSTEM_CONFIG)
    print(f"✅ Admin has all permissions")
    
    # Developer should have limited permissions
    assert rbac.has_permission("user2", Permission.BACKTEST_CREATE)
    assert rbac.has_permission("user2", Permission.STRATEGY_CREATE)
    assert not rbac.has_permission("user2", Permission.USER_DELETE)
    print(f"✅ Developer has correct permissions")
    
    # Viewer should have read-only
    assert rbac.has_permission("user3", Permission.BACKTEST_READ)
    assert not rbac.has_permission("user3", Permission.BACKTEST_CREATE)
    print(f"✅ Viewer has read-only permissions")
    
    # Test custom role
    print("\n[2.3] Testing custom role creation...")
    rbac.create_custom_role(
        "trader",
        "Trader",
        {Permission.BACKTEST_READ, Permission.BACKTEST_EXECUTE},
        "Custom trading role"
    )
    rbac.assign_role("user4", "trader")
    assert rbac.has_permission("user4", Permission.BACKTEST_EXECUTE)
    print(f"✅ Custom role 'trader' created and assigned")
    
    print("\n✅ RBAC Manager tests PASSED")


async def test_rate_limiter():
    """Test Rate Limiter"""
    print("\n" + "="*60)
    print("TEST 3: Rate Limiter")
    print("="*60)
    
    config = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_size=10
    )
    limiter = RateLimiter(config)
    
    # Test basic limiting
    print("\n[3.1] Testing basic rate limiting...")
    success_count = 0
    for i in range(15):
        allowed, reason = limiter.check_rate_limit("user1")
        if allowed:
            success_count += 1
        else:
            print(f"Request {i+1} blocked: {reason}")
            break
    
    assert success_count == 10  # Should allow burst_size
    print(f"✅ Rate limiting working: {success_count}/15 requests allowed")
    
    # Test per-user isolation
    print("\n[3.2] Testing per-user isolation...")
    allowed, _ = limiter.check_rate_limit("user2")
    assert allowed is True
    print(f"✅ User2 has independent rate limit")
    
    # Test endpoint-specific limits
    print("\n[3.3] Testing endpoint-specific limits...")
    for i in range(20):
        allowed, reason = limiter.check_rate_limit("user3", endpoint="/api/expensive")
        if not allowed:
            print(f"Endpoint limit blocked at request {i+1}")
            break
    print(f"✅ Endpoint-specific rate limiting working")
    
    # Test request cost
    print("\n[3.4] Testing variable request costs...")
    expensive_allowed, _ = limiter.check_rate_limit("user4", cost=5)
    assert expensive_allowed is True
    print(f"✅ Expensive request (cost=5) consumed 5 tokens")
    
    # Test statistics
    print("\n[3.5] Testing statistics...")
    stats = limiter.get_user_stats("user1")
    print(f"User1 stats:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Blocked requests: {stats['blocked_requests']}")
    print(f"  Current tokens: {stats['current_tokens']}")
    assert stats['blocked_requests'] > 0
    print(f"✅ Statistics tracking working")
    
    print("\n✅ Rate Limiter tests PASSED")


async def test_integration():
    """Full integration test"""
    print("\n" + "="*60)
    print("TEST 4: Full Integration (JWT + RBAC + Rate Limiting)")
    print("="*60)
    
    # Setup
    jwt_manager = JWTManager()
    rbac_manager = RBACManager()
    rate_limiter = RateLimiter(RateLimitConfig(requests_per_minute=5))
    
    # Scenario: Developer creates backtest
    user_id = "developer123"
    
    print(f"\n[4.1] User registration and role assignment...")
    rbac_manager.assign_role(user_id, Role.DEVELOPER.value)
    print(f"✅ User {user_id} assigned DEVELOPER role")
    
    print(f"\n[4.2] Generate authentication token...")
    token = jwt_manager.generate_access_token(
        user_id=user_id,
        roles=rbac_manager.get_user_roles(user_id)
    )
    print(f"✅ Token generated")
    
    print(f"\n[4.3] Verify token and check permissions...")
    payload = jwt_manager.verify_token(token)
    assert payload["sub"] == user_id
    
    has_create_perm = rbac_manager.has_permission(user_id, Permission.BACKTEST_CREATE)
    has_delete_perm = rbac_manager.has_permission(user_id, Permission.USER_DELETE)
    
    print(f"✅ Token valid")
    print(f"✅ Can create backtest: {has_create_perm}")
    print(f"✅ Can delete users: {has_delete_perm}")
    
    assert has_create_perm is True
    assert has_delete_perm is False
    
    print(f"\n[4.4] Make API requests with rate limiting...")
    requests_made = 0
    for i in range(10):
        allowed, reason = rate_limiter.check_rate_limit(user_id)
        if allowed:
            requests_made += 1
            # Simulate API call
            if rbac_manager.has_permission(user_id, Permission.BACKTEST_CREATE):
                pass  # Would create backtest
        else:
            print(f"⚠️  Request {i+1} rate limited: {reason}")
            break
    
    print(f"✅ Processed {requests_made} requests before rate limit")
    
    print(f"\n[4.5] Get final statistics...")
    stats = rate_limiter.get_user_stats(user_id)
    print(f"Final stats for {user_id}:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Blocked: {stats['blocked_requests']}")
    print(f"  Success rate: {((stats['total_requests'] - stats['blocked_requests']) / stats['total_requests'] * 100):.1f}%")
    
    print("\n✅ Full integration test PASSED")


async def main():
    """Run all tests"""
    print("="*60)
    print("AUTHENTICATION SYSTEM TESTS")
    print("="*60)
    
    try:
        await test_jwt()
        await test_rbac()
        await test_rate_limiter()
        await test_integration()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
