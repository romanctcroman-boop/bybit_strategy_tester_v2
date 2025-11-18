"""
🔑 DeepSeek Agent - Test All 8 API Keys
Быстрый тест всех доступных API ключей
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Change to project root and load .env
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Add backend to path
sys.path.insert(0, str(project_root))

from backend.security.key_manager import get_key_manager


class SimpleDeepSeekTester:
    """Simple DeepSeek API tester with multi-key support"""
    
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        print(f"\n🔑 Loaded {len(api_keys)} DeepSeek API keys")
    
    async def test_single_key(self, key_index: int, key: str) -> Dict[str, Any]:
        """Test single API key"""
        import httpx
        
        key_suffix = key[-8:]
        print(f"\n[Key {key_index + 1}/{len(self.api_keys)}] Testing ...{key_suffix}")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "user",
                                "content": f"Say 'Key {key_index + 1} working!' and explain DeepSeek in one sentence."
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 100
                    }
                )
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    
                    print(f"  ✅ SUCCESS ({elapsed:.2f}s, {tokens} tokens)")
                    print(f"  📝 Response: {content[:100]}...")
                    
                    return {
                        "key_index": key_index + 1,
                        "key_suffix": key_suffix,
                        "status": "success",
                        "elapsed": elapsed,
                        "tokens": tokens,
                        "response": content
                    }
                else:
                    print(f"  ❌ FAILED: HTTP {response.status_code}")
                    print(f"  📝 Error: {response.text[:200]}")
                    
                    return {
                        "key_index": key_index + 1,
                        "key_suffix": key_suffix,
                        "status": "failed",
                        "elapsed": elapsed,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                    
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"  ⏱️ TIMEOUT after {elapsed:.2f}s")
            return {
                "key_index": key_index + 1,
                "key_suffix": key_suffix,
                "status": "timeout",
                "elapsed": elapsed,
                "error": "Request timeout"
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ ERROR: {str(e)}")
            return {
                "key_index": key_index + 1,
                "key_suffix": key_suffix,
                "status": "error",
                "elapsed": elapsed,
                "error": str(e)
            }
    
    async def test_all_keys(self) -> Dict[str, Any]:
        """Test all API keys sequentially"""
        print("\n" + "=" * 80)
        print("🧪 DEEPSEEK API KEYS TEST")
        print("=" * 80)
        
        results = []
        
        for i, key in enumerate(self.api_keys):
            result = await self.test_single_key(i, key)
            results.append(result)
            
            # Small delay between requests
            if i < len(self.api_keys) - 1:
                await asyncio.sleep(1)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] != "success"]
        
        print(f"\n✅ Successful: {len(successful)}/{len(results)}")
        print(f"❌ Failed: {len(failed)}/{len(results)}")
        
        if successful:
            avg_time = sum(r["elapsed"] for r in successful) / len(successful)
            total_tokens = sum(r.get("tokens", 0) for r in successful)
            print(f"⏱️  Average time: {avg_time:.2f}s")
            print(f"🔢 Total tokens: {total_tokens}")
        
        if failed:
            print("\n❌ Failed keys:")
            for r in failed:
                print(f"  - Key {r['key_index']} (...{r['key_suffix']}): {r.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 80)
        
        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) * 100,
            "results": results
        }


async def main():
    """Main test function"""
    
    # Load API keys
    key_manager = get_key_manager()
    api_keys = []
    
    # Try to load all 8 keys
    for i in range(1, 9):
        try:
            if i == 1:
                key = key_manager.get_decrypted_key("DEEPSEEK_API_KEY")
            else:
                key = key_manager.get_decrypted_key(f"DEEPSEEK_API_KEY_{i}")
            
            api_keys.append(key)
            print(f"✓ Loaded DEEPSEEK_API_KEY{'_' + str(i) if i > 1 else ''}")
            
        except ValueError:
            # Key not found, stop looking
            if i == 1:
                print(f"❌ DEEPSEEK_API_KEY not found!")
                return
            else:
                print(f"ℹ️  DEEPSEEK_API_KEY_{i} not found (stopping)")
                break
        except Exception as e:
            print(f"⚠️  Error loading key {i}: {e}")
            break
    
    if not api_keys:
        print("\n❌ No API keys found! Please configure in encrypted_secrets.json")
        return
    
    # Run tests
    tester = SimpleDeepSeekTester(api_keys)
    results = await tester.test_all_keys()
    
    # Final verdict
    if results["success_rate"] == 100:
        print("\n🎉 ALL KEYS WORKING! DeepSeek Agent ready for production!")
    elif results["success_rate"] >= 50:
        print(f"\n⚠️  {results['successful']}/{results['total']} keys working. Check failed keys.")
    else:
        print(f"\n❌ Most keys failing ({results['failed']}/{results['total']}). Check configuration.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
