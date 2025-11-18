"""
Test DeepSeek API with cache system code review
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

prompt = """
Review this Python multi-level cache system:

CODE ISSUES:
1. Missing timedelta import from datetime
2. No error handling for Redis failures  
3. Using datetime.now() instead of time.monotonic()
4. No parameter validation (ttl, max_size)
5. No cache stampede prevention

QUESTIONS:
1. Rate code quality 1-10
2. List TOP 3 most critical production bugs
3. Compare with Instagram/Twitter caching systems
4. Is 1000x speedup realistic?

Be concise and actionable.
"""

response = requests.post(
    DEEPSEEK_API_URL,
    headers={
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a senior backend engineer specializing in high-performance caching systems. Provide expert code review."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 800,
        "temperature": 0.7
    },
    timeout=30
)

if response.status_code == 200:
    result = response.json()
    print("="*60)
    print("🤖 DEEPSEEK CODE REVIEW")
    print("="*60)
    print("\n" + result['choices'][0]['message']['content'])
    print("\n" + "="*60)
    print(f"📊 Stats:")
    print(f"   Model: {result['model']}")
    print(f"   Tokens: {result['usage']['total_tokens']}")
    print(f"   Prompt: {result['usage']['prompt_tokens']}")
    print(f"   Completion: {result['usage']['completion_tokens']}")
    print("="*60)
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
