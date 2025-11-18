"""
Test script for Perplexity and DeepSeek API connectivity
"""

import os
import sys
from pathlib import Path
import requests

# Load environment variables
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to load from .env
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
    print("[OK] .env file loaded")
except ImportError:
    print("[WARNING] python-dotenv not installed, using manual env vars")

# Import secure key manager
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key

# Get API keys securely
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")

print(f"\n{'='*80}")
print("API CONNECTIVITY TEST")
print(f"{'='*80}\n")

# Test 1: Check environment variables
print("1. Environment Variables:")
print(f"   PERPLEXITY_API_KEY: {'✅ SET' if PERPLEXITY_API_KEY else '❌ MISSING'}")
print(f"   DEEPSEEK_API_KEY: {'✅ SET' if DEEPSEEK_API_KEY else '❌ MISSING'}")

if PERPLEXITY_API_KEY:
    print(f"   Perplexity Key Preview: {PERPLEXITY_API_KEY[:10]}...{PERPLEXITY_API_KEY[-10:]}")
if DEEPSEEK_API_KEY:
    print(f"   DeepSeek Key Preview: {DEEPSEEK_API_KEY[:10]}...{DEEPSEEK_API_KEY[-10:]}")

# Test 2: Perplexity API
print(f"\n2. Testing Perplexity API...")
if PERPLEXITY_API_KEY:
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar",
                "messages": [
                    {"role": "user", "content": "Test message"}
                ],
                "max_tokens": 10
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS: Perplexity API is working!")
            print(f"   Response preview: {response.json()}")
        else:
            print(f"   ❌ ERROR: Status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
else:
    print("   ⏭️ SKIPPED: No API key")

# Test 3: DeepSeek API
print(f"\n3. Testing DeepSeek API...")
if DEEPSEEK_API_KEY:
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": "Test message"}
                ],
                "max_tokens": 10
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS: DeepSeek API is working!")
            print(f"   Response preview: {response.json()}")
        else:
            print(f"   ❌ ERROR: Status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
else:
    print("   ⏭️ SKIPPED: No API key")

print(f"\n{'='*80}")
print("TEST COMPLETED")
print(f"{'='*80}\n")
