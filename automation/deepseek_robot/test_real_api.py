"""
🧪 Test Real API Implementation

Tests DeepSeek and Perplexity API clients with real API calls
"""

import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

from automation.deepseek_robot.api_clients import (
    DeepSeekClient,
    PerplexityClient,
    DeepSeekAPIError,
    PerplexityAPIError
)

load_dotenv()


async def test_deepseek_api():
    """Test DeepSeek API with real key"""
    print("\n" + "="*80)
    print("🧪 TEST 1: DeepSeek API")
    print("="*80)
    
    # Get API key
    api_key = os.getenv("DEEPSEEK_API_KEY_1")
    
    if not api_key:
        print("❌ DEEPSEEK_API_KEY_1 not found in .env")
        return False
    
    print(f"✅ API Key loaded: {api_key[:10]}...{api_key[-4:]}")
    
    # Create client
    client = DeepSeekClient(api_key=api_key, timeout=30.0, max_retries=3)
    
    # Test query
    query = "Write a simple Python function that adds two numbers. Keep it brief."
    
    print(f"\n📝 Query: {query}")
    print(f"⏳ Sending request to DeepSeek API...")
    
    try:
        # Call API
        result = await client.chat_completion(
            messages=[{"role": "user", "content": query}],
            model="deepseek-coder",
            temperature=0.1,
            max_tokens=500
        )
        
        # Check result
        if result.get("success"):
            print(f"\n✅ API call successful!")
            print(f"   • Model: {result.get('model')}")
            print(f"   • Tokens used: {result.get('usage', {}).get('total_tokens', 0)}")
            print(f"   • Finish reason: {result.get('finish_reason')}")
            print(f"\n📄 Response:")
            print("-"*80)
            print(result.get("response", "")[:500])  # First 500 chars
            print("-"*80)
            
            # Client stats
            stats = client.get_stats()
            print(f"\n📊 Client Stats:")
            print(f"   • Total requests: {stats['total_requests']}")
            print(f"   • Success rate: {stats['success_rate']}")
            print(f"   • Total tokens: {stats['total_tokens']}")
            
            return True
        else:
            print(f"❌ API call failed: {result.get('error')}")
            return False
            
    except DeepSeekAPIError as e:
        print(f"❌ DeepSeek API Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_perplexity_api():
    """Test Perplexity API with real key"""
    print("\n" + "="*80)
    print("🧪 TEST 2: Perplexity API")
    print("="*80)
    
    # Get API key
    api_key = os.getenv("PERPLEXITY_API_KEY")
    
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found in .env")
        return False
    
    print(f"✅ API Key loaded: {api_key[:10]}...{api_key[-4:]}")
    
    # Create client
    client = PerplexityClient(api_key=api_key, timeout=30.0, max_retries=3)
    
    # Test query
    query = "What are the latest best practices for async Python programming in 2024?"
    
    print(f"\n📝 Query: {query}")
    print(f"⏳ Sending request to Perplexity API...")
    
    try:
        # Call API
        result = await client.search(
            query=query,
            model="sonar-pro"
        )
        
        # Check result
        if result.get("success"):
            print(f"\n✅ API call successful!")
            print(f"   • Model: {result.get('model')}")
            print(f"   • Sources: {len(result.get('sources', []))}")
            print(f"\n📄 Response:")
            print("-"*80)
            print(result.get("response", "")[:500])  # First 500 chars
            print("-"*80)
            
            # Show sources
            sources = result.get("sources", [])
            if sources:
                print(f"\n🔗 Sources ({len(sources)}):")
                for i, source in enumerate(sources[:5], 1):  # First 5 sources
                    print(f"   {i}. {source}")
            
            # Client stats
            stats = client.get_stats()
            print(f"\n📊 Client Stats:")
            print(f"   • Total requests: {stats['total_requests']}")
            print(f"   • Success rate: {stats['success_rate']}")
            
            return True
        else:
            print(f"❌ API call failed: {result.get('error')}")
            return False
            
    except PerplexityAPIError as e:
        print(f"❌ Perplexity API Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_keys():
    """Test parallel execution with multiple DeepSeek keys"""
    print("\n" + "="*80)
    print("🧪 TEST 3: Multiple API Keys (Parallel)")
    print("="*80)
    
    # Load all 8 keys
    keys = [
        os.getenv(f"DEEPSEEK_API_KEY_{i}")
        for i in range(1, 9)
        if os.getenv(f"DEEPSEEK_API_KEY_{i}")
    ]
    
    if not keys:
        print("❌ No DeepSeek API keys found")
        return False
    
    print(f"✅ Found {len(keys)} API keys")
    
    # Create queries
    queries = [
        "What is Python?",
        "What is async/await?",
        "What is machine learning?",
        "What is Docker?",
    ]
    
    print(f"\n📝 Testing {len(queries)} parallel requests with {len(keys)} keys...")
    
    # Execute in parallel
    tasks = []
    for i, query in enumerate(queries):
        api_key = keys[i % len(keys)]  # Round-robin
        client = DeepSeekClient(api_key=api_key, timeout=30.0)
        
        task = client.chat_completion(
            messages=[{"role": "user", "content": query}],
            model="deepseek-coder",
            temperature=0.1,
            max_tokens=200
        )
        tasks.append(task)
    
    # Wait for all
    import time
    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start
    
    # Analyze results
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = len(results) - successful
    
    print(f"\n✅ Completed in {duration:.2f}s")
    print(f"   • Successful: {successful}/{len(results)}")
    print(f"   • Failed: {failed}/{len(results)}")
    print(f"   • Average: {duration/len(results):.2f}s per request")
    
    # Expected sequential time
    sequential_time = len(results) * 3  # Assume 3s per request
    speedup = sequential_time / duration if duration > 0 else 0
    
    print(f"\n📊 Performance:")
    print(f"   • Sequential (estimated): {sequential_time:.1f}s")
    print(f"   • Parallel (actual): {duration:.2f}s")
    print(f"   • Speedup: {speedup:.1f}x")
    
    return successful > 0


async def test_error_handling():
    """Test error handling and retry logic"""
    print("\n" + "="*80)
    print("🧪 TEST 4: Error Handling & Retry")
    print("="*80)
    
    # Test with invalid key
    print("\n1. Testing with invalid API key...")
    client = DeepSeekClient(api_key="invalid_key_12345", timeout=10.0, max_retries=2)
    
    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100
        )
        
        if not result.get("success"):
            print(f"✅ Error handled correctly: {result.get('error', '')[:100]}")
        else:
            print(f"⚠️  Unexpected success with invalid key")
            
    except DeepSeekAPIError as e:
        print(f"✅ Error caught correctly: {str(e)[:100]}")
    
    # Test timeout (using very short timeout)
    print("\n2. Testing timeout handling...")
    api_key = os.getenv("DEEPSEEK_API_KEY_1")
    if api_key:
        client = DeepSeekClient(api_key=api_key, timeout=0.001, max_retries=1)  # 1ms timeout
        
        try:
            result = await client.chat_completion(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=100
            )
            
            if not result.get("success"):
                print(f"✅ Timeout handled: {result.get('error', '')[:100]}")
            else:
                print(f"⚠️  No timeout (API very fast!)")
                
        except DeepSeekAPIError as e:
            print(f"✅ Timeout caught: {str(e)[:100]}")
    
    return True


async def run_all_tests():
    """Run all API tests"""
    print("\n" + "🎯"*40)
    print("  REAL API IMPLEMENTATION TEST SUITE")
    print("🎯"*40)
    
    results = []
    
    # Test 1: DeepSeek API
    try:
        result = await test_deepseek_api()
        results.append(("DeepSeek API", result))
    except Exception as e:
        print(f"❌ Test 1 crashed: {e}")
        results.append(("DeepSeek API", False))
    
    # Test 2: Perplexity API
    try:
        result = await test_perplexity_api()
        results.append(("Perplexity API", result))
    except Exception as e:
        print(f"❌ Test 2 crashed: {e}")
        results.append(("Perplexity API", False))
    
    # Test 3: Multiple keys
    try:
        result = await test_multiple_keys()
        results.append(("Multiple Keys", result))
    except Exception as e:
        print(f"❌ Test 3 crashed: {e}")
        results.append(("Multiple Keys", False))
    
    # Test 4: Error handling
    try:
        result = await test_error_handling()
        results.append(("Error Handling", result))
    except Exception as e:
        print(f"❌ Test 4 crashed: {e}")
        results.append(("Error Handling", False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print(f"\n   Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Real API implementation working!")
    elif passed > 0:
        print("\n⚠️  SOME TESTS FAILED. Check errors above.")
    else:
        print("\n❌ ALL TESTS FAILED. Check API keys and network.")
    
    return passed == total


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Exit code
    import sys
    sys.exit(0 if success else 1)
