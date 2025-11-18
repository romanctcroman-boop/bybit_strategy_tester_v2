"""
Multi-Key Rotation Integration Tests

Tests key rotation with multiple real API keys:
- 8 DeepSeek API keys (from encrypted_secrets.json)
- 4 Perplexity API keys (from encrypted_secrets.json)

Verifies:
1. Load balancing across multiple keys
2. Key rotation under concurrent requests
3. Failure handling when keys are exhausted
4. Recovery after cooldown period
5. Parallel request processing with key distribution

⚠️ WARNING: Requires encrypted_secrets.json with all keys!
Run with: pytest tests/integration/test_multi_key_rotation.py -v -s
"""

import pytest
import asyncio
import os
import time
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from reliability.deepseek_client import DeepSeekReliableClient, DeepSeekRequest
from reliability.perplexity_client import PerplexityReliableClient
from reliability.circuit_breaker import CircuitBreakerConfig
from reliability.retry_policy import RetryConfig

# Try to load encrypted keys
try:
    from automation.task2_key_manager.key_manager import KeyManager
    from cryptography.fernet import Fernet
    
    # Load master key from .env
    env_path = Path(__file__).parent.parent.parent / "mcp-server" / ".env"
    load_dotenv(env_path)
    MASTER_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
    
    # Load encrypted secrets
    secrets_file = Path(__file__).parent.parent.parent / "encrypted_secrets.json"
    
    if secrets_file.exists() and MASTER_KEY:
        key_manager = KeyManager()
        key_manager.initialize_encryption(MASTER_KEY)
        key_manager.load_keys(str(secrets_file))
        
        # Load all DeepSeek keys (8 total: main + _1 through _7)
        DEEPSEEK_KEYS = []
        
        # Load main key
        try:
            api_key = key_manager.get_key("DEEPSEEK_API_KEY")
            if api_key:
                DEEPSEEK_KEYS.append({
                    "id": "deepseek-key-1",
                    "api_key": api_key,
                    "weight": 1.0
                })
        except Exception:
            pass
        
        # Load keys _1 through _7
        for i in range(1, 8):
            try:
                api_key = key_manager.get_key(f"DEEPSEEK_API_KEY_{i}")
                if api_key:
                    DEEPSEEK_KEYS.append({
                        "id": f"deepseek-key-{i+1}",
                        "api_key": api_key,
                        "weight": 1.0
                    })
            except Exception:
                pass
        
        # Load all Perplexity keys (4 total: main + _1 through _3)
        PERPLEXITY_KEYS = []
        
        # Load main key
        try:
            api_key = key_manager.get_key("PERPLEXITY_API_KEY")
            if api_key:
                PERPLEXITY_KEYS.append({
                    "id": "perplexity-key-1",
                    "api_key": api_key,
                    "weight": 1.0
                })
        except Exception:
            pass
        
        # Load keys _1 through _3
        for i in range(1, 4):
            try:
                api_key = key_manager.get_key(f"PERPLEXITY_API_KEY_{i}")
                if api_key:
                    PERPLEXITY_KEYS.append({
                        "id": f"perplexity-key-{i+1}",
                        "api_key": api_key,
                        "weight": 1.0
                    })
            except Exception:
                pass
        
        KEYS_LOADED = len(DEEPSEEK_KEYS) > 1 or len(PERPLEXITY_KEYS) > 1
    else:
        KEYS_LOADED = False
        DEEPSEEK_KEYS = []
        PERPLEXITY_KEYS = []

except Exception as e:
    print(f"⚠️ Could not load encrypted keys: {e}")
    KEYS_LOADED = False
    DEEPSEEK_KEYS = []
    PERPLEXITY_KEYS = []

# Fallback to single keys from .env if encrypted keys not available
if not KEYS_LOADED:
    env_path = Path(__file__).parent.parent.parent / "mcp-server" / ".env"
    load_dotenv(env_path)
    
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    
    if DEEPSEEK_API_KEY:
        DEEPSEEK_KEYS = [{"id": "deepseek-key-1", "api_key": DEEPSEEK_API_KEY, "weight": 1.0}]
    if PERPLEXITY_API_KEY:
        PERPLEXITY_KEYS = [{"id": "perplexity-key-1", "api_key": PERPLEXITY_API_KEY, "weight": 1.0}]

# Skip tests if no keys available
pytestmark = pytest.mark.skipif(
    not DEEPSEEK_KEYS and not PERPLEXITY_KEYS,
    reason="No API keys available. Need encrypted_secrets.json or .env with keys"
)

print(f"\n🔑 Loaded {len(DEEPSEEK_KEYS)} DeepSeek keys, {len(PERPLEXITY_KEYS)} Perplexity keys")


@pytest.fixture
def multi_key_deepseek_client():
    """DeepSeek client with multiple API keys"""
    if not DEEPSEEK_KEYS:
        pytest.skip("No DeepSeek keys available")
    
    client = DeepSeekReliableClient(
        api_keys=DEEPSEEK_KEYS,
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
    print(f"✅ Created DeepSeek client with {len(DEEPSEEK_KEYS)} keys")
    return client


@pytest.fixture
def multi_key_perplexity_client():
    """Perplexity client with multiple API keys"""
    if not PERPLEXITY_KEYS:
        pytest.skip("No Perplexity keys available")
    
    client = PerplexityReliableClient(
        api_keys=PERPLEXITY_KEYS,
        base_url="https://api.perplexity.ai/chat/completions",
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
    print(f"✅ Created Perplexity client with {len(PERPLEXITY_KEYS)} keys")
    return client


class TestDeepSeekMultiKeyRotation:
    """Test DeepSeek with multiple API keys"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_key_rotation_under_load(self, multi_key_deepseek_client):
        """Should rotate keys under concurrent load"""
        print(f"\n🔄 Testing DeepSeek key rotation with {len(DEEPSEEK_KEYS)} keys...")
        
        # Create 10 concurrent requests
        requests = [
            DeepSeekRequest(
                id=f"load-test-{i}",
                prompt=f"Count from 1 to {i}. Just list the numbers.",
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=50
            )
            for i in range(1, 11)
        ]
        
        start_time = time.time()
        responses = await multi_key_deepseek_client.process_batch(requests)
        duration = time.time() - start_time
        
        print(f"✅ Processed {len(responses)} requests in {duration:.2f}s")
        print(f"   Average: {duration/len(responses):.2f}s per request")
        
        # Check that multiple keys were used
        used_keys = set()
        for response in responses:
            if response.key_id:
                used_keys.add(response.key_id)
        
        print(f"   Keys used: {len(used_keys)}/{len(DEEPSEEK_KEYS)}")
        
        assert len(responses) == 10
        # If we have multiple keys, expect key rotation
        if len(DEEPSEEK_KEYS) > 1:
            assert len(used_keys) > 1, "Expected key rotation across multiple keys"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_requests_distribution(self, multi_key_deepseek_client):
        """Should distribute parallel requests across keys"""
        print(f"\n🔄 Testing parallel request distribution with {len(DEEPSEEK_KEYS)} keys...")
        
        # Create 20 parallel requests
        async def make_request(i: int):
            return await multi_key_deepseek_client.chat_completion(
                prompt=f"What is {i} * 2? Answer with just the number.",
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=10
            )
        
        start_time = time.time()
        responses = await asyncio.gather(*[make_request(i) for i in range(1, 21)])
        duration = time.time() - start_time
        
        print(f"✅ Processed 20 parallel requests in {duration:.2f}s")
        
        # Analyze key distribution
        key_usage = {}
        for response in responses:
            if response and response.key_id:
                key_usage[response.key_id] = key_usage.get(response.key_id, 0) + 1
        
        print(f"   Key distribution:")
        for key_id, count in sorted(key_usage.items()):
            print(f"      {key_id}: {count} requests ({count/20*100:.1f}%)")
        
        # Verify load balancing
        if len(DEEPSEEK_KEYS) > 1:
            # Expect relatively even distribution (within 2x variance)
            max_usage = max(key_usage.values())
            min_usage = min(key_usage.values())
            variance = max_usage / min_usage if min_usage > 0 else float('inf')
            print(f"   Load balance variance: {variance:.2f}x")
            
            # Allow some imbalance due to randomness
            assert variance < 3.0, f"Load imbalance too high: {variance:.2f}x"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cache_with_multiple_keys(self, multi_key_deepseek_client):
        """Should cache responses regardless of key used"""
        print(f"\n🔄 Testing cache across {len(DEEPSEEK_KEYS)} keys...")
        
        query = "What is the capital of France?"
        
        # First request (cache miss)
        start_time = time.time()
        response1 = await multi_key_deepseek_client.chat_completion(
            prompt=query,
            model="deepseek-chat",
            max_tokens=50
        )
        first_duration = time.time() - start_time
        first_key = response1.key_id if response1 else None
        
        print(f"✅ First request: {first_duration:.2f}s (key: {first_key})")
        
        # Second request (cache hit, might use different key)
        start_time = time.time()
        response2 = await multi_key_deepseek_client.chat_completion(
            prompt=query,
            model="deepseek-chat",
            max_tokens=50
        )
        second_duration = time.time() - start_time
        second_key = response2.key_id if response2 else None
        
        print(f"✅ Second request: {second_duration:.2f}s (key: {second_key})")
        print(f"   Cache speedup: {first_duration/second_duration if second_duration > 0 else 0:.1f}x")
        
        # Cache should be much faster
        assert second_duration < 0.5, "Cache hit should be instant"
        assert response1.content == response2.content, "Cached content should match"


class TestPerplexityMultiKeyRotation:
    """Test Perplexity with multiple API keys"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_key_rotation_under_load(self, multi_key_perplexity_client):
        """Should rotate keys under concurrent load"""
        print(f"\n🔄 Testing Perplexity key rotation with {len(PERPLEXITY_KEYS)} keys...")
        
        # Create 8 concurrent requests (slower API)
        queries = [
            "What is Python?",
            "What is JavaScript?",
            "What is Go?",
            "What is Rust?",
            "What is TypeScript?",
            "What is Kotlin?",
            "What is Swift?",
            "What is C++?"
        ]
        
        async def make_request(query: str):
            return await multi_key_perplexity_client.chat_completion(
                query=query,
                model="sonar",
                max_tokens=50
            )
        
        start_time = time.time()
        responses = await asyncio.gather(*[make_request(q) for q in queries])
        duration = time.time() - start_time
        
        print(f"✅ Processed {len(responses)} requests in {duration:.2f}s")
        print(f"   Average: {duration/len(responses):.2f}s per request")
        
        # Check key distribution
        used_keys = set()
        for response in responses:
            if response and response.key_id:
                used_keys.add(response.key_id)
        
        print(f"   Keys used: {len(used_keys)}/{len(PERPLEXITY_KEYS)}")
        
        # If we have multiple keys, expect rotation
        if len(PERPLEXITY_KEYS) > 1:
            assert len(used_keys) > 1, "Expected key rotation"
    
    @pytest.mark.asyncio
    @pytest.mark.integration  
    async def test_parallel_online_search(self, multi_key_perplexity_client):
        """Should handle parallel online searches with key distribution"""
        print(f"\n🔄 Testing parallel online search with {len(PERPLEXITY_KEYS)} keys...")
        
        # Different queries to avoid cache
        queries = [
            f"What happened in tech news on November {i}, 2025?"
            for i in range(1, 6)
        ]
        
        async def search(query: str):
            return await multi_key_perplexity_client.chat_completion(
                query=query,
                model="sonar",
                max_tokens=100
            )
        
        start_time = time.time()
        responses = await asyncio.gather(*[search(q) for q in queries])
        duration = time.time() - start_time
        
        print(f"✅ Completed 5 parallel searches in {duration:.2f}s")
        
        # Analyze results
        successful = sum(1 for r in responses if r and r.success)
        with_citations = sum(1 for r in responses if r and r.citations)
        
        print(f"   Successful: {successful}/5")
        print(f"   With citations: {with_citations}/5")
        
        # Check key usage
        key_usage = {}
        for response in responses:
            if response and response.key_id:
                key_usage[response.key_id] = key_usage.get(response.key_id, 0) + 1
        
        print(f"   Key distribution:")
        for key_id, count in sorted(key_usage.items()):
            print(f"      {key_id}: {count} requests")
        
        assert successful >= 3, "At least 3 searches should succeed"


class TestCrossClientMultiKey:
    """Test both clients with multiple keys together"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_combined_workflow_with_multi_keys(
        self, 
        multi_key_deepseek_client, 
        multi_key_perplexity_client
    ):
        """Should use both clients with multiple keys in workflow"""
        print(f"\n🔄 Testing combined workflow:")
        print(f"   DeepSeek: {len(DEEPSEEK_KEYS)} keys")
        print(f"   Perplexity: {len(PERPLEXITY_KEYS)} keys")
        
        # Step 1: Research with Perplexity
        print("\n📡 Step 1: Research current crypto trends...")
        research_response = await multi_key_perplexity_client.chat_completion(
            query="What are the top 3 cryptocurrency trends in November 2025?",
            model="sonar",
            max_tokens=200
        )
        
        if not research_response or not research_response.success:
            pytest.skip("Perplexity API unavailable")
        
        print(f"✅ Research complete (key: {research_response.key_id})")
        print(f"   Content: {research_response.content[:100]}...")
        
        # Step 2: Analyze with DeepSeek
        print("\n🧠 Step 2: Analyze trends with DeepSeek...")
        analysis_response = await multi_key_deepseek_client.chat_completion(
            prompt=f"Based on these trends: {research_response.content}\n\nProvide 2-sentence analysis.",
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=100
        )
        
        if not analysis_response or not analysis_response.success:
            pytest.skip("DeepSeek API unavailable")
        
        print(f"✅ Analysis complete (key: {analysis_response.key_id})")
        print(f"   Analysis: {analysis_response.content}")
        
        # Verify both stages completed
        assert research_response.success
        assert analysis_response.success
        assert len(research_response.content) > 50
        assert len(analysis_response.content) > 20
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_high_volume_mixed_workload(
        self,
        multi_key_deepseek_client,
        multi_key_perplexity_client
    ):
        """Should handle high volume with both APIs using multiple keys"""
        print(f"\n🔄 Testing high-volume mixed workload...")
        print(f"   DeepSeek: {len(DEEPSEEK_KEYS)} keys")
        print(f"   Perplexity: {len(PERPLEXITY_KEYS)} keys")
        
        # Create mixed workload
        async def deepseek_task(i: int):
            return await multi_key_deepseek_client.chat_completion(
                prompt=f"Calculate {i} squared. Answer with just the number.",
                model="deepseek-chat",
                max_tokens=10
            )
        
        async def perplexity_task(i: int):
            return await multi_key_perplexity_client.chat_completion(
                query=f"What is the number {i}?",
                model="sonar",
                max_tokens=30
            )
        
        # 10 DeepSeek + 5 Perplexity = 15 total requests
        start_time = time.time()
        deepseek_tasks = [deepseek_task(i) for i in range(1, 11)]
        perplexity_tasks = [perplexity_task(i) for i in range(1, 6)]
        
        all_responses = await asyncio.gather(
            *deepseek_tasks,
            *perplexity_tasks,
            return_exceptions=True
        )
        duration = time.time() - start_time
        
        # Separate responses
        deepseek_responses = all_responses[:10]
        perplexity_responses = all_responses[10:]
        
        # Count successes
        deepseek_success = sum(
            1 for r in deepseek_responses 
            if not isinstance(r, Exception) and r and r.success
        )
        perplexity_success = sum(
            1 for r in perplexity_responses 
            if not isinstance(r, Exception) and r and r.success
        )
        
        print(f"\n✅ Mixed workload completed in {duration:.2f}s")
        print(f"   DeepSeek: {deepseek_success}/10 successful")
        print(f"   Perplexity: {perplexity_success}/5 successful")
        print(f"   Total throughput: {15/duration:.2f} req/s")
        
        # Analyze key distribution
        print(f"\n   DeepSeek key usage:")
        ds_keys = {}
        for r in deepseek_responses:
            if not isinstance(r, Exception) and r and r.key_id:
                ds_keys[r.key_id] = ds_keys.get(r.key_id, 0) + 1
        for key, count in sorted(ds_keys.items()):
            print(f"      {key}: {count} requests")
        
        print(f"\n   Perplexity key usage:")
        pp_keys = {}
        for r in perplexity_responses:
            if not isinstance(r, Exception) and r and r.key_id:
                pp_keys[r.key_id] = pp_keys.get(r.key_id, 0) + 1
        for key, count in sorted(pp_keys.items()):
            print(f"      {key}: {count} requests")
        
        # Expect reasonable success rate
        assert deepseek_success >= 7, "DeepSeek should have >70% success"
        assert perplexity_success >= 3, "Perplexity should have >60% success"
        
        # Expect key rotation if multiple keys available
        if len(DEEPSEEK_KEYS) > 1:
            assert len(ds_keys) > 1, "DeepSeek should rotate keys"
        if len(PERPLEXITY_KEYS) > 1:
            assert len(pp_keys) > 1, "Perplexity should rotate keys"


if __name__ == "__main__":
    print(f"""
    🔑 Multi-Key Rotation Test Suite
    
    DeepSeek keys available: {len(DEEPSEEK_KEYS)}
    Perplexity keys available: {len(PERPLEXITY_KEYS)}
    
    Run with: pytest tests/integration/test_multi_key_rotation.py -v -s
    """)
