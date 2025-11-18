import httpx
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("DEEPSEEK_API_KEY_1")

print(f"Testing DeepSeek API...")
print(f"Key: {key[:20]}...{key[-10:]}")

url = "https://api.deepseek.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}
payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Say 'test ok'"}],
    "max_tokens": 10
}

response = httpx.post(url, json=payload, headers=headers, timeout=30)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")
