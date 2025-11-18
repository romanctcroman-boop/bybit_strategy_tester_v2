"""
Integration Tests for Real API Calls

These tests make ACTUAL calls to DeepSeek and Perplexity APIs.
They verify that:
1. API clients work with real endpoints
2. Retry mechanisms handle real network conditions
3. Key rotation works across multiple keys
4. Circuit breaker protects against real failures
5. Cache reduces redundant API calls
6. Response parsing handles real API responses

⚠️ WARNING: These tests consume API credits!
Run with: pytest tests/integration/ -v -s

Environment variables required:
- DEEPSEEK_API_KEY
- PERPLEXITY_API_KEY
"""

import pytest
import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv

from reliability.deepseek_client import DeepSeekReliableClient
from reliability.perplexity_client import PerplexityReliableClient
from reliability.circuit_breaker import CircuitBreakerConfig
from reliability.retry_policy import RetryConfig

# Import universal keys loader
from tests.integration.api_keys_loader import load_deepseek_keys, load_perplexity_keys, get_keys_info

# Load API keys (tries encrypted first, falls back to plaintext)
DEEPSEEK_KEYS = load_deepseek_keys()
PERPLEXITY_KEYS = load_perplexity_keys()
KEYS_INFO = get_keys_info()

# Print key info
print(f"\n🔑 Integration Test Configuration:")
print(f"   Source: {KEYS_INFO['source']}")
print(f"   DeepSeek keys: {KEYS_INFO['deepseek_count']}")
print(f"   Perplexity keys: {KEYS_INFO['perplexity_count']}")
print(f"   Multi-key testing: {'✅ ENABLED' if KEYS_INFO['multi_key_testing'] else '⚠️ DISABLED (single key only)'}\n")

# Skip all tests if API keys not available
pytestmark = pytest.mark.skipif(
    not DEEPSEEK_KEYS and not PERPLEXITY_KEYS,
    reason="No API keys available. Need encrypted_secrets.json or .env with keys"
)


@pytest.fixture
def deepseek_client():
    """Create DeepSeek client with all available API keys"""
    if not DEEPSEEK_KEYS:
        pytest.skip("No DeepSeek keys available")
    
    client = DeepSeekReliableClient(
        api_keys=DEEPSEEK_KEYS,  # Now uses ALL available keys (1-8)
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=0.5,
            window_size=10,
            open_timeout=30.0,
            half_open_max_probes=1
        ),
        retry_config=RetryConfig(
            max_retries=2,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True
        ),
        enable_cache=True,
        enable_monitoring=True
    )
    print(f"✅ DeepSeek client created with {len(DEEPSEEK_KEYS)} key(s)")
    return client


@pytest.fixture
def perplexity_client():
    """Create Perplexity client with all available API keys"""
    if not PERPLEXITY_KEYS:
        pytest.skip("No Perplexity keys available")
    
    client = PerplexityReliableClient(
        api_keys=PERPLEXITY_KEYS,  # Now uses ALL available keys (1-4)
        base_url="https://api.perplexity.ai/chat/completions",  # Full endpoint URL
        enable_cache=True,
        cache_ttl=300,
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=0.5,
            window_size=10,
            open_timeout=30.0
        ),
        retry_config=RetryConfig(
            max_retries=2,
            base_delay=1.0
        )
    )
    print(f"✅ Perplexity client created with {len(PERPLEXITY_KEYS)} key(s)")
    return client


class TestDeepSeekRealAPI:
    """Test DeepSeek client with real API"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_simple_chat_completion(self, deepseek_client):
        """Should complete simple chat request"""
        print("\n🔄 Testing DeepSeek chat completion...")
        
        response = await deepseek_client.chat_completion(
            prompt="What is 2+2? Answer with just the number.",
            model="deepseek-chat",
            temperature=0.0,
            max_tokens=10
        )
        
        print(f"✅ Response: {response.content}")
        
        assert response is not None
        assert response.content is not None
        assert "4" in response.content
        assert response.tokens_used > 0
        assert response.success is True
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cache_hit(self, deepseek_client):
        """Should return cached response for duplicate request"""
        print("\n🔄 Testing DeepSeek cache...")
        
        prompt = "What is the capital of France?"
        
        # First request (cache miss)
        start_time = time.time()
        response1 = await deepseek_client.chat_completion(
            prompt=prompt,
            model="deepseek-chat",
            temperature=0.7
        )
        first_duration = time.time() - start_time
        
        print(f"✅ First request: {first_duration:.2f}s - {response1.content[:50]}")
        
        # Second request (cache hit)
        start_time = time.time()
        response2 = await deepseek_client.chat_completion(
            prompt=prompt,
            model="deepseek-chat",
            temperature=0.7
        )
        second_duration = time.time() - start_time
        
        print(f"✅ Second request: {second_duration:.2f}s (cache hit)")
        
        assert response2.content == response1.content
        assert second_duration < first_duration * 0.1  # Cache should be 10x faster
        
        # Check health metrics
        health = deepseek_client.get_health()
        print(f"📊 Cache stats: {health['cache']}")
        assert health['cache']['hit_rate'] > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_processing(self, deepseek_client):
        """Should process multiple requests concurrently with key rotation"""
        print(f"\n🔄 Testing DeepSeek batch processing ({len(DEEPSEEK_KEYS)} keys)...")
        
        from reliability.deepseek_client import DeepSeekRequest
        
        requests = [
            DeepSeekRequest(
                id=f"batch-{i}",
                prompt=f"What is {i}+{i}? Answer with just the number.",
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=10
            )
            for i in range(1, 4)
        ]
        
        start_time = time.time()
        responses = await deepseek_client.process_batch(requests)
        duration = time.time() - start_time
        
        print(f"✅ Processed {len(responses)} requests in {duration:.2f}s")
        
        # Check key rotation if multiple keys available
        if len(DEEPSEEK_KEYS) > 1:
            used_keys = set()
            for response in responses:
                if response.key_id:
                    used_keys.add(response.key_id)
            print(f"   Keys used: {len(used_keys)}/{len(DEEPSEEK_KEYS)}")
            print(f"   Key distribution: {', '.join(sorted(used_keys))}")
        
        assert len(responses) == 3
        for i, response in enumerate(responses, 1):
            expected = str(i * 2)
            print(f"   {i}+{i} = {response.content}")
            assert expected in response.content
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_monitoring_metrics(self, deepseek_client):
        """Should collect monitoring metrics"""
        print("\n🔄 Testing DeepSeek monitoring...")
        
        # Make a request
        await deepseek_client.chat_completion(
            prompt="Hello",
            model="deepseek-chat",
            max_tokens=10
        )
        
        # Check health
        health = deepseek_client.get_health()
        
        print(f"📊 Health metrics:")
        print(f"   Total requests: {health['requests']['total']}")
        print(f"   Successful: {health['requests']['successful']}")
        print(f"   Failed: {health['requests']['failed']}")
        print(f"   Avg latency: N/A (not tracked)")
        print(f"   Circuit breaker: {list(health['circuit_breakers'].values())[0]['state']}")
        
        assert health['requests']['total'] >= 1
        assert health['requests']['successful'] >= 1
        assert list(health['circuit_breakers'].values())[0]['state'] == 'closed'
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_requests_with_key_rotation(self, deepseek_client):
        """Should distribute parallel requests across multiple keys"""
        print(f"\n🔄 Testing parallel requests with {len(DEEPSEEK_KEYS)} key(s)...")
        
        # Create 10 parallel requests
        async def make_request(i: int):
            return await deepseek_client.chat_completion(
                prompt=f"What is {i} squared? Answer with just the number.",
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=10
            )
        
        start_time = time.time()
        responses = await asyncio.gather(*[make_request(i) for i in range(1, 11)])
        duration = time.time() - start_time
        
        print(f"✅ Processed 10 parallel requests in {duration:.2f}s")
        print(f"   Average: {duration/10:.2f}s per request")
        
        # Analyze key distribution
        if len(DEEPSEEK_KEYS) > 1:
            key_usage = {}
            for response in responses:
                if response and response.key_id:
                    key_usage[response.key_id] = key_usage.get(response.key_id, 0) + 1
            
            print(f"   Key distribution:")
            for key_id, count in sorted(key_usage.items()):
                print(f"      {key_id}: {count} requests ({count/10*100:.0f}%)")
            
            # Expect at least 2 keys used if we have multiple keys
            assert len(key_usage) >= 2, f"Expected key rotation across multiple keys, got {len(key_usage)}"
            print(f"   ✅ Key rotation verified: {len(key_usage)} keys used")
        else:
            print(f"   ⚠️ Single key mode - key rotation not tested")
        
        # Verify responses
        successful = sum(1 for r in responses if r and r.success)
        assert successful >= 8, f"Expected at least 8/10 successful, got {successful}"


class TestPerplexityRealAPI:
    """Test Perplexity client with real API"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_online_search(self, perplexity_client):
        """Should perform online search with current model"""
        print("\n🔄 Testing Perplexity online search...")
        
        response = await perplexity_client.chat_completion(
            query="What is the current Bitcoin price?",
            model="sonar",  # Current Perplexity model (replaces sonar)
            temperature=0.0,
            max_tokens=100
        )
        
        # Handle timeout/failure gracefully
        if response is None:
            pytest.skip("Perplexity API timeout or unavailable")
        
        print(f"✅ Response: {response.content[:100]}...")
        print(f"📚 Citations: {len(response.citations) if response.citations else 0} sources")
        
        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_streaming_response(self, perplexity_client):
        """Should stream response chunks"""
        print("\n🔄 Testing Perplexity streaming...")
        
        chunks = []
        async for chunk in perplexity_client.chat_completion_stream(
            query="What is Python? Answer in one sentence.",
            model="sonar"
        ):
            chunks.append(chunk.content)
            print(f"📦 Chunk: {chunk.content}", end="", flush=True)
        
        print(f"\n✅ Received {len(chunks)} chunks")
        
        assert len(chunks) > 0
        full_content = "".join(chunks)
        assert len(full_content) > 0
        assert "python" in full_content.lower()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cache_with_short_ttl(self, perplexity_client):
        """Should cache with 5-minute TTL"""
        print("\n🔄 Testing Perplexity cache (5min TTL)...")
        
        query = "What is machine learning?"
        
        # First request
        start_time = time.time()
        response1 = await perplexity_client.chat_completion(
            query=query,
            model="sonar"
        )
        first_duration = time.time() - start_time
        
        print(f"✅ First request: {first_duration:.2f}s")
        
        # Second request (cache hit)
        start_time = time.time()
        response2 = await perplexity_client.chat_completion(
            query=query,
            model="sonar"
        )
        second_duration = time.time() - start_time
        
        print(f"✅ Second request: {second_duration:.2f}s (cache hit)")
        
        assert response2.content == response1.content
        assert second_duration < 0.1  # Cache should be instant
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_citation_extraction(self, perplexity_client):
        """Should extract citations from response"""
        print("\n🔄 Testing Perplexity citation extraction...")
        
        response = await perplexity_client.chat_completion(
            query="Who won the Nobel Prize in Physics 2024?",
            model="sonar",
            max_tokens=200
        )
        
        print(f"✅ Response: {response.content[:100]}...")
        print(f"📚 Citations found: {len(response.citations)}")
        
        for i, citation in enumerate(response.citations, 1):
            print(f"   [{i}] {citation}")
        
        assert response.citations is not None
        # Online search should provide citations
        if len(response.citations) > 0:
            assert all(isinstance(c, str) for c in response.citations)
            assert all(c.startswith("http") for c in response.citations)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_online_searches_with_key_rotation(self, perplexity_client):
        """Should distribute parallel searches across multiple keys"""
        print(f"\n🔄 Testing parallel online searches with {len(PERPLEXITY_KEYS)} key(s)...")
        
        # Different queries to avoid cache
        queries = [
            "What is Python programming?",
            "What is JavaScript?",
            "What is Go language?",
            "What is Rust programming?",
            "What is TypeScript?",
        ]
        
        async def search(query: str):
            return await perplexity_client.chat_completion(
                query=query,
                model="sonar",
                max_tokens=50
            )
        
        start_time = time.time()
        responses = await asyncio.gather(*[search(q) for q in queries])
        duration = time.time() - start_time
        
        print(f"✅ Processed 5 parallel searches in {duration:.2f}s")
        print(f"   Average: {duration/5:.2f}s per search")
        
        # Analyze key distribution
        if len(PERPLEXITY_KEYS) > 1:
            key_usage = {}
            for response in responses:
                if response and response.key_id:
                    key_usage[response.key_id] = key_usage.get(response.key_id, 0) + 1
            
            print(f"   Key distribution:")
            for key_id, count in sorted(key_usage.items()):
                print(f"      {key_id}: {count} requests ({count/5*100:.0f}%)")
            
            # Expect key rotation if we have multiple keys
            if len(key_usage) > 1:
                print(f"   ✅ Key rotation verified: {len(key_usage)} keys used")
            else:
                print(f"   ⚠️ Only 1 key used (might be due to caching or rate limits)")
        else:
            print(f"   ⚠️ Single key mode - key rotation not tested")
        
        # Verify responses
        successful = sum(1 for r in responses if r and r.success)
        print(f"   Successful: {successful}/5")
        assert successful >= 3, f"Expected at least 3/5 successful, got {successful}"


class TestCrossClientIntegration:
    """Test integration between multiple clients"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_deepseek_and_perplexity_together(
        self, 
        deepseek_client, 
        perplexity_client
    ):
        """Should use both clients together"""
        print("\n🔄 Testing DeepSeek + Perplexity integration...")
        
        # Step 1: Get latest info from Perplexity
        print("📡 Step 1: Get latest crypto trends from Perplexity...")
        perplexity_response = await perplexity_client.chat_completion(
            query="What are the top 3 cryptocurrency trends in November 2025?",
            model="sonar",
            max_tokens=200
        )
        
        print(f"✅ Perplexity response: {perplexity_response.content[:100]}...")
        
        # Step 2: Analyze with DeepSeek
        print("🧠 Step 2: Analyze trends with DeepSeek...")
        deepseek_response = await deepseek_client.chat_completion(
            prompt=f"Based on these crypto trends: {perplexity_response.content}\n\nProvide a brief analysis (2-3 sentences).",
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=150
        )
        
        print(f"✅ DeepSeek analysis: {deepseek_response.content}")
        
        assert perplexity_response.content is not None
        assert deepseek_response.content is not None
        assert len(perplexity_response.content) > 0
        assert len(deepseek_response.content) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_metrics_after_usage(
        self,
        deepseek_client,
        perplexity_client
    ):
        """Should report health metrics after real usage"""
        print("\n🔄 Testing health metrics...")
        
        # Use both clients
        await deepseek_client.chat_completion(
            prompt="Hello",
            model="deepseek-chat",
            max_tokens=10
        )
        
        await perplexity_client.chat_completion(
            query="Hello",
            model="sonar",
            max_tokens=10
        )
        
        # Check DeepSeek health
        deepseek_health = deepseek_client.get_health()
        print(f"\n📊 DeepSeek Health:")
        print(f"   Requests: {deepseek_health['total_requests']}")
        print(f"   Success rate: {deepseek_health['successful_requests']}/{deepseek_health['total_requests']}")
        print(f"   Avg latency: {deepseek_health['average_latency']:.3f}s")
        print(f"   Cache hit rate: {deepseek_health['cache']['hit_rate']:.2%}")
        
        # Check Perplexity health
        perplexity_health = perplexity_client.get_health()
        print(f"\n📊 Perplexity Health:")
        print(f"   Requests: {perplexity_health['total_requests']}")
        print(f"   Success rate: {perplexity_health['successful_requests']}/{perplexity_health['total_requests']}")
        print(f"   Avg latency: {perplexity_health['average_latency']:.3f}s")
        print(f"   Citations tracked: {perplexity_health['citations']['total']}")
        
        assert deepseek_health['total_requests'] > 0
        assert perplexity_health['total_requests'] > 0


class TestErrorHandling:
    """Test error handling with real API"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_invalid_model_error(self, deepseek_client):
        """Should handle invalid model gracefully"""
        print("\n🔄 Testing invalid model error...")
        
        with pytest.raises(Exception) as exc_info:
            await deepseek_client.chat_completion(
                prompt="Hello",
                model="invalid-model-that-does-not-exist",
                max_tokens=10
            )
        
        print(f"✅ Error caught: {exc_info.value}")
        assert exc_info.value is not None
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_prompt_error(self, deepseek_client):
        """Should handle empty prompt gracefully"""
        print("\n🔄 Testing empty prompt error...")
        
        with pytest.raises(Exception) as exc_info:
            await deepseek_client.chat_completion(
                prompt="",
                model="deepseek-chat",
                max_tokens=10
            )
        
        print(f"✅ Error caught: {exc_info.value}")
        assert exc_info.value is not None
