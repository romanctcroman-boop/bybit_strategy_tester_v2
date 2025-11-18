"""
Test DeepSeek and Perplexity API connectivity
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from openai import AsyncOpenAI


async def test_deepseek_api():
    """Test DeepSeek API with actual request"""
    print("=" * 80)
    print("TESTING DEEPSEEK API")
    print("=" * 80)
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    print(f"\n✓ API Key: {api_key[:15]}...{api_key[-6:]}")
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        
        print("\n📡 Sending test request to DeepSeek API...")
        print("   Prompt: 'Calculate 2+2 and respond with just the number'")
        
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "Calculate 2+2 and respond with just the number"}
            ],
            max_tokens=10,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip()
        print(f"\n✅ DeepSeek API Response: '{result}'")
        print(f"   Model: {response.model}")
        print(f"   Tokens: {response.usage.total_tokens}")
        
        if "4" in result:
            print("\n🎉 DeepSeek API WORKING! (Correct answer)")
            return True
        else:
            print(f"\n⚠️  DeepSeek API returned unexpected result: {result}")
            return False
            
    except Exception as e:
        print(f"\n❌ DeepSeek API Error: {e}")
        return False


async def test_perplexity_api():
    """Test Perplexity API with actual request"""
    print("\n" + "=" * 80)
    print("TESTING PERPLEXITY API")
    print("=" * 80)
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    print(f"\n✓ API Key: {api_key[:15]}...{api_key[-6:]}")
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        print("\n📡 Sending test request to Perplexity API...")
        print("   Prompt: 'What is the current Bitcoin price? Just give me the number.'")
        
        response = await client.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[
                {"role": "user", "content": "What is the current Bitcoin price? Just give me approximate number."}
            ],
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip()
        print(f"\n✅ Perplexity API Response: '{result[:100]}...'")
        print(f"   Model: {response.model}")
        print(f"   Has citations: {hasattr(response, 'citations')}")
        
        print("\n🎉 Perplexity API WORKING!")
        return True
            
    except Exception as e:
        print(f"\n❌ Perplexity API Error: {e}")
        return False


async def test_deepseek_parallel():
    """Test DeepSeek with multiple keys in parallel"""
    print("\n" + "=" * 80)
    print("TESTING DEEPSEEK PARALLEL (8 KEYS)")
    print("=" * 80)
    
    # Get all 8 keys
    keys = []
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            keys.append(key)
    
    print(f"\n✓ Found {len(keys)} DeepSeek API keys")
    
    async def test_single_key(key_index, api_key):
        """Test single key"""
        try:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "user", "content": f"What is {key_index} + {key_index}? Just the number."}
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip()
            print(f"   ✅ Key {key_index}: {result} (tokens: {response.usage.total_tokens})")
            return True
        except Exception as e:
            print(f"   ❌ Key {key_index}: {str(e)[:50]}")
            return False
    
    # Test all keys in parallel
    print(f"\n📡 Testing {len(keys)} keys in parallel...")
    tasks = [test_single_key(i+1, key) for i, key in enumerate(keys)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    print(f"\n📊 Results: {success_count}/{len(keys)} keys working")
    
    if success_count == len(keys):
        print("🎉 ALL KEYS WORKING! Parallel processing ready!")
        return True
    elif success_count > 0:
        print(f"⚠️  {success_count} keys working, {len(keys) - success_count} failed")
        return True
    else:
        print("❌ No keys working")
        return False


async def main():
    print("\n" + "=" * 80)
    print("API CONNECTIVITY TEST")
    print("=" * 80)
    
    # Test DeepSeek
    deepseek_ok = await test_deepseek_api()
    
    # Test Perplexity
    perplexity_ok = await test_perplexity_api()
    
    # Test DeepSeek Parallel
    parallel_ok = await test_deepseek_parallel()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"\n{'✅' if deepseek_ok else '❌'} DeepSeek API (Single Key)")
    print(f"{'✅' if perplexity_ok else '❌'} Perplexity API")
    print(f"{'✅' if parallel_ok else '❌'} DeepSeek Parallel (8 Keys)")
    
    if deepseek_ok and perplexity_ok and parallel_ok:
        print("\n🎉 ALL APIS WORKING! Ready for production!")
    else:
        print("\n⚠️  Some APIs need attention")


if __name__ == "__main__":
    asyncio.run(main())
