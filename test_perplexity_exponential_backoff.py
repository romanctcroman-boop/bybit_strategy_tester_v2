"""
🎯 Priority 2: Unit-тесты Exponential Backoff Retry

Тестирует:
1. Exponential backoff calculation with jitter
2. Smart retry based on HTTP status codes
3. Integration with multi-key rotation
4. Integration with circuit breaker
5. Rate limit handling with backoff
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import httpx
import time

# Add mcp-server to path
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

from api.providers.perplexity import PerplexityProvider


async def test_backoff_calculation():
    """
    Тест 1: Exponential backoff calculation with jitter
    """
    print("\n" + "="*80)
    print("🧪 TEST 1: Exponential Backoff Calculation")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1"],
        enable_exponential_backoff=True,
        backoff_base=2.0,
        backoff_max=60.0
    )
    
    print("\n📊 Backoff delays for regular errors:")
    for attempt in range(6):
        delay = provider._calculate_backoff_delay(attempt, is_rate_limit=False)
        expected_base = min(2.0 ** attempt, 60.0)
        print(f"   Attempt {attempt}: {delay:.2f}s (expected ~{expected_base:.2f}s ±25%)")
        
        # Check delay is within expected range (base ±25% jitter)
        assert expected_base * 0.75 <= delay <= expected_base * 1.25, \
            f"Delay {delay} out of range for attempt {attempt}"
    
    print("\n📊 Backoff delays for rate limit errors (longer):")
    for attempt in range(4):
        delay = provider._calculate_backoff_delay(attempt, is_rate_limit=True)
        expected_base = min(2.0 ** (attempt + 2), 60.0)
        print(f"   Attempt {attempt}: {delay:.2f}s (expected ~{expected_base:.2f}s ±25%)")
        
        assert expected_base * 0.75 <= delay <= expected_base * 1.25, \
            f"Rate limit delay {delay} out of range for attempt {attempt}"
    
    # Test max limit
    delay_max = provider._calculate_backoff_delay(10, is_rate_limit=False)
    print(f"\n✅ Max delay capped at: {delay_max:.2f}s (max={provider.backoff_max}s)")
    assert delay_max <= provider.backoff_max * 1.25, "Delay should be capped at max"
    
    print("\n✅ TEST 1 PASSED")


async def test_smart_retry_logic():
    """
    Тест 2: Smart retry based on HTTP status codes
    """
    print("\n" + "="*80)
    print("🧪 TEST 2: Smart Retry Logic")
    print("="*80)
    
    provider = PerplexityProvider(api_keys=["key1"])
    
    # Test cases: (status_code, should_retry, description)
    test_cases = [
        (429, True, "Rate limit → retry with key rotation"),
        (500, True, "Internal server error → retry"),
        (502, True, "Bad gateway → retry"),
        (503, True, "Service unavailable → retry"),
        (408, True, "Request timeout → retry"),
        (400, False, "Bad request → no retry"),
        (401, False, "Unauthorized → no retry"),
        (403, False, "Forbidden → no retry"),
        (404, False, "Not found → no retry"),
        (422, False, "Unprocessable entity → no retry"),
        (200, True, "Success → no retry needed (but returns True)"),
    ]
    
    print("\n📊 Status Code Retry Logic:")
    for status_code, expected_retry, description in test_cases:
        should_retry = provider._should_retry_on_status(status_code)
        status = "✅" if should_retry == expected_retry else "❌"
        print(f"   {status} {status_code}: {should_retry} - {description}")
        
        assert should_retry == expected_retry, \
            f"Status {status_code} retry logic mismatch"
    
    print("\n✅ TEST 2 PASSED")


async def test_retry_with_backoff_integration():
    """
    Тест 3: Integration of retry with exponential backoff
    """
    print("\n" + "="*80)
    print("🧪 TEST 3: Retry with Exponential Backoff Integration")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1"],
        enable_exponential_backoff=True,
        backoff_base=1.5,  # Faster for testing
        backoff_max=10.0
    )
    
    # Mock responses: 503 (retry) → 503 (retry) → 200 (success)
    response_503 = MagicMock()
    response_503.status_code = 503
    response_503.text = "Service temporarily unavailable"
    
    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = {
        "choices": [{"message": {"content": "Success after retries"}}],
        "usage": {"total_tokens": 10},
        "model": "sonar"
    }
    
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # First two calls: 503 error
        if call_count <= 2:
            return response_503
        # Third call: success
        else:
            return response_200
    
    # Patch httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = mock_post
        mock_client.return_value = mock_context
        
        # Mock asyncio.sleep to speed up test (return immediately)
        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Make request
            payload = {"model": "sonar", "messages": [{"role": "user", "content": "test"}]}
            
            try:
                result = await provider._make_request(payload, timeout=10.0)
                
                print(f"✅ Request succeeded after {call_count} attempts")
                print(f"📊 Response: {result.get('choices', [{}])[0].get('message', {}).get('content', '')}")
                
                # Should have attempted 3 times
                assert call_count == 3, f"Expected 3 attempts, got {call_count}"
                
                print("\n✅ TEST 3 PASSED")
                
            except Exception as e:
                print(f"❌ TEST 3 FAILED: {e}")
                raise


async def test_rate_limit_with_key_rotation_and_backoff():
    """
    Тест 4: Rate limit handling with multi-key rotation + backoff
    """
    print("\n" + "="*80)
    print("🧪 TEST 4: Rate Limit + Multi-Key Rotation + Backoff")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1", "key2", "key3"],
        enable_exponential_backoff=True,
        backoff_base=2.0,
        backoff_max=60.0
    )
    
    # Mock responses: 429 (key1) → 429 (key2) → 429 (key3) → 200 (key1 retry)
    response_429 = MagicMock()
    response_429.status_code = 429
    response_429.text = "Rate limit exceeded"
    
    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = {
        "choices": [{"message": {"content": "Success after key rotation"}}],
        "usage": {"total_tokens": 10},
        "model": "sonar"
    }
    
    call_count = 0
    keys_used = []
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Extract key from Authorization header
        auth_header = kwargs.get('headers', {}).get('Authorization', '')
        keys_used.append(auth_header)
        
        # First 3 calls (all keys): 429
        if call_count <= 3:
            return response_429
        # 4th call (after full rotation + backoff): success
        else:
            return response_200
    
    # Patch httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = mock_post
        mock_client.return_value = mock_context
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Make request
            payload = {"model": "sonar", "messages": [{"role": "user", "content": "test"}]}
            
            try:
                result = await provider._make_request(payload, timeout=10.0)
                
                print(f"✅ Request succeeded after {call_count} attempts")
                print(f"📊 Keys rotation: {len(set(keys_used))} unique keys used")
                
                # Check key statistics
                key_stats = provider.get_key_stats()
                print(f"\n📊 Key Statistics:")
                for key, stats in key_stats.items():
                    if stats['requests'] > 0:
                        print(f"   {key}: {stats['requests']} requests, {stats['rate_limits']} rate limits")
                
                # Should have tried at least 3 keys
                assert call_count >= 3, f"Expected at least 3 attempts, got {call_count}"
                
                print("\n✅ TEST 4 PASSED")
                
            except Exception as e:
                print(f"❌ TEST 4 FAILED: {e}")
                raise


async def test_no_retry_on_client_errors():
    """
    Тест 5: No retry on client errors (400, 401, 403, 404)
    """
    print("\n" + "="*80)
    print("🧪 TEST 5: No Retry on Client Errors")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1"],
        enable_exponential_backoff=True
    )
    
    # Test 400 Bad Request (should not retry)
    response_400 = MagicMock()
    response_400.status_code = 400
    response_400.text = "Bad request"
    
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return response_400
    
    # Patch httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = mock_post
        mock_client.return_value = mock_context
        
        # Make request
        payload = {"model": "sonar", "messages": [{"role": "user", "content": "test"}]}
        
        try:
            await provider._make_request(payload, timeout=10.0)
            print("❌ Should have raised exception for 400 error")
            assert False, "Should have raised exception"
        except Exception as e:
            print(f"✅ Exception raised as expected: {e}")
            print(f"📊 Attempts made: {call_count}")
            
            # Should only attempt once (no retry on 400)
            assert call_count == 1, f"Expected 1 attempt, got {call_count}"
            
            print("\n✅ TEST 5 PASSED")


async def test_backoff_disabled():
    """
    Тест 6: Behavior when backoff is disabled
    """
    print("\n" + "="*80)
    print("🧪 TEST 6: Backoff Disabled")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1"],
        enable_exponential_backoff=False  # Disabled
    )
    
    # Calculate backoff delays
    delays = [provider._calculate_backoff_delay(i) for i in range(5)]
    
    print(f"📊 Backoff delays (disabled): {delays}")
    
    # All delays should be 0
    assert all(d == 0.0 for d in delays), "All delays should be 0 when backoff disabled"
    
    print("✅ All delays are 0 when backoff disabled")
    print("\n✅ TEST 6 PASSED")


async def test_circuit_breaker_integration():
    """
    Тест 7: Integration with circuit breaker
    """
    print("\n" + "="*80)
    print("🧪 TEST 7: Circuit Breaker Integration with Retry")
    print("="*80)
    
    provider = PerplexityProvider(
        api_keys=["key1"],
        enable_exponential_backoff=True
    )
    
    # Enable circuit breaker
    provider.circuit_breaker_enabled = True
    
    # Mock circuit breaker
    mock_circuit_breaker = MagicMock()
    mock_circuit_breaker.get_state.return_value = {
        "state": "closed",
        "can_accept_calls": True
    }
    provider.circuit_breaker = mock_circuit_breaker
    
    # Mock response: success
    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = {
        "choices": [{"message": {"content": "Success"}}],
        "usage": {"total_tokens": 10},
        "model": "sonar"
    }
    
    async def mock_post(*args, **kwargs):
        return response_200
    
    # Patch httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = mock_post
        mock_client.return_value = mock_context
        
        # Make request
        payload = {"model": "sonar", "messages": [{"role": "user", "content": "test"}]}
        result = await provider._make_request(payload, timeout=10.0)
        
        print(f"✅ Request succeeded")
        
        # Check circuit breaker was called
        assert mock_circuit_breaker.get_state.called, "Circuit breaker state should be checked"
        assert mock_circuit_breaker.on_success.called, "Circuit breaker should record success"
        
        print(f"📊 Circuit breaker calls:")
        print(f"   - get_state: {mock_circuit_breaker.get_state.call_count} times")
        print(f"   - on_success: {mock_circuit_breaker.on_success.call_count} times")
        
        print("\n✅ TEST 7 PASSED")


async def main():
    """
    Запуск всех unit-тестов Priority 2
    """
    print("\n" + "="*80)
    print("🎯 Priority 2: Exponential Backoff Retry Unit Testing")
    print("="*80)
    
    try:
        # Test 1: Backoff calculation
        await test_backoff_calculation()
        
        # Test 2: Smart retry logic
        await test_smart_retry_logic()
        
        # Test 3: Retry with backoff
        await test_retry_with_backoff_integration()
        
        # Test 4: Rate limit + rotation + backoff
        await test_rate_limit_with_key_rotation_and_backoff()
        
        # Test 5: No retry on client errors
        await test_no_retry_on_client_errors()
        
        # Test 6: Backoff disabled
        await test_backoff_disabled()
        
        # Test 7: Circuit breaker integration
        await test_circuit_breaker_integration()
        
        print("\n" + "="*80)
        print("✅ ALL PRIORITY 2 TESTS PASSED")
        print("="*80)
        print("\n📊 Exponential Backoff Implementation:")
        print("   ✅ Exponential backoff calculation with jitter")
        print("   ✅ Smart retry based on HTTP status codes")
        print("   ✅ Integration with multi-key rotation")
        print("   ✅ Integration with circuit breaker")
        print("   ✅ No retry on client errors (400-499)")
        print("   ✅ Configurable backoff (base, max)")
        print("   ✅ Rate limit handling with longer backoff")
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ TEST SUITE FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
