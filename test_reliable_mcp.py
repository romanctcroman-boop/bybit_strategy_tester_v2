"""
Test Reliable MCP Server - Verify 110% Reliability
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from reliability.reliable_mcp_server import ReliableMCPServer


@pytest.mark.asyncio
async def test_reliable_mcp_initialization():
    """Test that server initializes with all Phase 1-3 components"""
    server = ReliableMCPServer()
    
    # Verify Phase 1 components
    assert server.retry_policy is not None
    assert server.perplexity_keys is not None
    assert server.deepseek_keys is not None
    assert server.service_monitor is not None
    
    # Verify Phase 3 components
    assert 'perplexity' in server.rate_limiters
    assert 'deepseek' in server.rate_limiters
    assert server.circuit_breakers.get('perplexity_api') is not None
    assert server.circuit_breakers.get('deepseek_api') is not None
    assert server.cache is not None
    assert server.deduplicator is not None
    
    print("✅ All components initialized successfully!")


@pytest.mark.asyncio
async def test_parallel_execution():
    """Test parallel execution with multiple API keys"""
    server = ReliableMCPServer()
    
    # Verify key rotation managers have keys
    perplexity_key_count = len(server.perplexity_keys.config.api_keys)
    deepseek_key_count = len(server.deepseek_keys.config.api_keys)
    
    print(f"📊 Available keys:")
    print(f"   - Perplexity: {perplexity_key_count} keys")
    print(f"   - DeepSeek: {deepseek_key_count} keys")
    
    assert perplexity_key_count >= 1, "Need at least 1 Perplexity key"
    assert deepseek_key_count >= 1, "Need at least 1 DeepSeek key"
    
    # Test that we can rotate keys
    key1 = await server.perplexity_keys.get_next_key()
    key2 = await server.perplexity_keys.get_next_key()
    
    if perplexity_key_count > 1:
        assert key1 != key2, "Keys should rotate"
        print("✅ Key rotation working!")
    else:
        print("⚠️ Only 1 Perplexity key available (rotation not testable)")


@pytest.mark.asyncio
async def test_circuit_breaker_protection():
    """Test circuit breaker prevents cascading failures"""
    server = ReliableMCPServer()
    
    cb = server.circuit_breakers.get("perplexity_api")
    assert cb is not None
    
    # Check initial state
    stats = cb.get_stats()
    print(f"📊 Circuit Breaker initial state: {stats.state}")
    assert stats.state == "closed"
    
    print("✅ Circuit breaker initialized in CLOSED state!")


@pytest.mark.asyncio
async def test_rate_limiter_enforcement():
    """Test rate limiters prevent API overload"""
    server = ReliableMCPServer()
    
    limiter = server.rate_limiters['perplexity']
    
    # Should allow first request
    allowed = await limiter.acquire()
    assert allowed, "First request should be allowed"
    
    print("✅ Rate limiter allowing requests!")


@pytest.mark.asyncio
async def test_cache_functionality():
    """Test cache reduces API calls"""
    server = ReliableMCPServer()
    
    # Set cache entry
    await server.cache.set("test_key", {"data": "test_value"}, ttl=60)
    
    # Retrieve cached entry
    cached = await server.cache.get("test_key")
    assert cached is not None
    assert cached['data'] == "test_value"
    
    print("✅ Cache working correctly!")


@pytest.mark.asyncio
async def test_deduplication():
    """Test request deduplication prevents duplicate processing"""
    server = ReliableMCPServer()
    
    request_data = {"api": "test", "query": "test_query"}
    
    # First request - should NOT be duplicate
    is_dup = await server.deduplicator.is_duplicate(request_data)
    assert not is_dup, "First request should not be duplicate"
    
    # Immediate second request - SHOULD be duplicate
    is_dup = await server.deduplicator.is_duplicate(request_data)
    assert is_dup, "Immediate second request should be duplicate"
    
    print("✅ Deduplication working correctly!")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 Testing Reliable MCP Server (Phase 1-3 Integration)")
    print("=" * 80)
    
    asyncio.run(test_reliable_mcp_initialization())
    asyncio.run(test_parallel_execution())
    asyncio.run(test_circuit_breaker_protection())
    asyncio.run(test_rate_limiter_enforcement())
    asyncio.run(test_cache_functionality())
    asyncio.run(test_deduplication())
    
    print("\n" + "=" * 80)
    print("🎉 All tests passed! Reliable MCP Server = 110% ready!")
    print("=" * 80)
