"""
Простой тест подключения к Perplexity API
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def test_perplexity_connection():
    """Тест базового подключения к Perplexity API"""
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found in environment")
        return False
    
    print(f"✅ API Key found: {api_key[:20]}...")
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Connection successful!' in one sentence."}
        ],
        "max_tokens": 50
    }
    
    print("\n🔍 Testing connection to Perplexity API...")
    print(f"URL: {url}")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            print("⏳ Sending request (timeout=30s)...")
            response = client.post(url, json=payload, headers=headers)
            
            print(f"📡 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"✅ SUCCESS! Response: {content}")
                return True
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False
                
    except httpx.TimeoutException as e:
        print(f"❌ Timeout error: {e}")
        print("\n💡 Possible issues:")
        print("   1. No internet connection")
        print("   2. Firewall blocking the request")
        print("   3. VPN/Proxy issues")
        return False
        
    except httpx.ConnectError as e:
        print(f"❌ Connection error: {e}")
        print("\n💡 Possible issues:")
        print("   1. DNS resolution failed")
        print("   2. Network unavailable")
        print("   3. Perplexity API is down")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("="*80)
    print("🧪 Perplexity API Connection Test")
    print("="*80)
    
    success = test_perplexity_connection()
    
    print("\n" + "="*80)
    if success:
        print("✅ Test PASSED - Perplexity API is accessible")
    else:
        print("❌ Test FAILED - Cannot connect to Perplexity API")
    print("="*80)
