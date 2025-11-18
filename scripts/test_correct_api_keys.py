#!/usr/bin/env python3
"""
ПРАВИЛЬНЫЙ тест Perplexity API (с ключами из .env)
"""

import requests
import json
from pathlib import Path

# ПРАВИЛЬНЫЕ API Keys из .env
PERPLEXITY_API_KEY = "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"
DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"

def test_perplexity():
    """Тест Perplexity API с ПРАВИЛЬНЫМ ключом"""
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user",
                "content": "Hello, can you help me with API testing?"
            }
        ]
    }
    
    print("=" * 80)
    print("PERPLEXITY API TEST (ПРАВИЛЬНЫЙ КЛЮЧ)")
    print("=" * 80)
    print(f"API Key: {PERPLEXITY_API_KEY[:20]}...")
    print()
    print("📤 Sending request...")
    
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
            return True
        else:
            print(f"❌ FAILED!")
            print()
            print("Response:")
            print(response.text[:500])
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def test_deepseek():
    """Тест DeepSeek API с ПРАВИЛЬНЫМ ключом"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": "Say 'Hello' if you can hear me"
            }
        ],
        "temperature": 0.2
    }
    
    print("=" * 80)
    print("DEEPSEEK API TEST (ПРАВИЛЬНЫЙ КЛЮЧ)")
    print("=" * 80)
    print(f"API Key: {DEEPSEEK_API_KEY[:20]}...")
    print()
    print("📤 Sending request...")
    
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
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
            return True
        else:
            print(f"❌ FAILED!")
            print()
            print("Response:")
            print(response.text[:500])
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    # Тестируем оба API
    perplexity_ok = test_perplexity()
    print()
    print()
    deepseek_ok = test_deepseek()
    
    print()
    print("=" * 80)
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 80)
    print(f"Perplexity API: {'✅ WORKING' if perplexity_ok else '❌ NOT WORKING'}")
    print(f"DeepSeek API: {'✅ WORKING' if deepseek_ok else '❌ NOT WORKING'}")
    print("=" * 80)
