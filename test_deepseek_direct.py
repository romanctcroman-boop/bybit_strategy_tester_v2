"""
Quick test to verify DeepSeek API keys are working
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_deepseek_key(api_key: str, key_name: str):
    """Test single DeepSeek API key"""
    print(f"\n🔍 Testing {key_name}: {api_key[-8:]}...")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "user", "content": "Hello! Just testing the API. Respond with OK."}
                    ],
                    "max_tokens": 50
                }
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"   ✅ SUCCESS: {content[:100]}")
                return True
            else:
                print(f"   ❌ FAILED: {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        return False


async def main():
    """Test all DeepSeek keys"""
    print("\n" + "="*80)
    print("🧪 DEEPSEEK API KEYS DIRECT TEST")
    print("="*80)
    
    results = []
    
    # Test all 8 keys
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            success = await test_deepseek_key(key, f"Key {i}")
            results.append((f"Key {i}", success))
            await asyncio.sleep(1)  # Rate limit
        else:
            print(f"\n⚠️  DEEPSEEK_API_KEY_{i} not found in .env")
    
    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    for key_name, success in results:
        status = "✅ Working" if success else "❌ Failed"
        print(f"  {key_name}: {status}")
    
    print(f"\n✅ {successful}/{total} keys working ({successful/total*100:.1f}%)")
    
    if successful == 0:
        print("\n⚠️  WARNING: No DeepSeek keys are working!")
        print("   Possible issues:")
        print("   1. API keys are invalid/expired")
        print("   2. DeepSeek API is down")
        print("   3. Rate limit exceeded")
        print("   4. Network/firewall issues")


if __name__ == "__main__":
    asyncio.run(main())
