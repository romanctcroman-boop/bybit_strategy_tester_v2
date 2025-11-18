#!/usr/bin/env python3
"""
Тест Perplexity API - минимальный запрос
"""

import requests
import json

# API Key из .env
PERPLEXITY_API_KEY = "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"

def test_perplexity():
    """Минимальный тест Perplexity API"""
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # МИНИМАЛЬНЫЙ запрос
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user",
                "content": "Hello, can you help me?"
            }
        ]
    }
    
    print("=" * 80)
    print("PERPLEXITY API TEST")
    print("=" * 80)
    print(f"API Key: {PERPLEXITY_API_KEY[:20]}...")
    print(f"Endpoint: https://api.perplexity.ai/chat/completions")
    print()
    print("📤 Sending minimal test request...")
    print()
    
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print("✅ SUCCESS!")
            print()
            print("Response:")
            print(content)
            print()
            print("=" * 80)
            return True
        else:
            print(f"❌ FAILED!")
            print()
            print("Response Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            print()
            print("Response Body:")
            print(response.text[:500])
            print()
            print("=" * 80)
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        print("=" * 80)
        return False

if __name__ == "__main__":
    success = test_perplexity()
    
    if not success:
        print()
        print("💡 TROUBLESHOOTING:")
        print()
        print("1. Проверьте API ключ в .env файле")
        print("2. Проверьте баланс аккаунта Perplexity")
        print("3. Проверьте доступность api.perplexity.ai")
        print("4. Попробуйте другую модель (sonar вместо sonar-pro)")
        print()
