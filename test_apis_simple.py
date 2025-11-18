#!/usr/bin/env python3
"""Simple API test for DeepSeek and Perplexity"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def test_deepseek():
    """Test DeepSeek API"""
    key = os.getenv('DEEPSEEK_API_KEY')
    if not key:
        print("ERROR: No DEEPSEEK_API_KEY in .env")
        return False
    
    print(f"\n=== TESTING DEEPSEEK ===")
    print(f"Key: {key[:20]}...")
    
    try:
        response = httpx.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': 'Say "OK" if you work'}],
                'max_tokens': 50
            },
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            print(f"Response: {answer}")
            print("✅ DEEPSEEK WORKS!")
            return True
        else:
            print(f"ERROR: {response.text}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_perplexity():
    """Test Perplexity API"""
    key = os.getenv('PERPLEXITY_API_KEY')
    if not key:
        print("ERROR: No PERPLEXITY_API_KEY in .env")
        return False
    
    print(f"\n=== TESTING PERPLEXITY ===")
    print(f"Key: {key[:20]}...")
    
    # Try different models
    models = ['sonar', 'sonar-pro', 'llama-3.1-sonar-small-128k-chat']
    
    for model in models:
        print(f"\nTrying model: {model}")
        try:
            response = httpx.post(
                'https://api.perplexity.ai/chat/completions',
                headers={
                    'Authorization': f'Bearer {key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Say "OK" if you work'}],
                    'max_tokens': 50
                },
                timeout=30.0
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content']
                print(f"Response: {answer}")
                print(f"✅ PERPLEXITY WORKS with model: {model}")
                return True
            else:
                print(f"Failed: {response.text[:200]}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    print("❌ PERPLEXITY FAILED with all models")
    return False

if __name__ == "__main__":
    deepseek_ok = test_deepseek()
    perplexity_ok = test_perplexity()
    
    print("\n" + "="*60)
    print("FINAL RESULTS:")
    print(f"  DeepSeek: {'✅ WORKING' if deepseek_ok else '❌ FAILED'}")
    print(f"  Perplexity: {'✅ WORKING' if perplexity_ok else '❌ FAILED'}")
    print("="*60)
