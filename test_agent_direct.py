import httpx
import json

# Test DeepSeek agent
deepseek_payload = {
    "from_agent": "copilot",
    "to_agent": "deepseek",
    "message_type": "query",
    "content": "AUDIT REQUEST: Week 5 Day 5 Testing. Module: backend/api/routers/strategies.py, Tests: 26/26, Coverage: 97.60%. Questions: 1. DI-cache pattern OK? 2. Keep @cached decorators? 3. Test fallback logging? 4. Mock recommendations? 5. Priority after executions.py?",
    "max_iterations": 1
}

print("Sending to DeepSeek...")
try:
    resp = httpx.post('http://127.0.0.1:8000/api/v1/agent/send', json=deepseek_payload, timeout=120)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Message ID: {data.get('message_id')}")
    print(f"Content preview: {data.get('content', '')[:500]}")
    print("\n" + "="*80 + "\n")
except Exception as e:
    print(f"Error: {e}")

# Test Perplexity agent
perplexity_payload = {
    "from_agent": "copilot",
    "to_agent": "perplexity",
    "message_type": "query",
    "content": "RESEARCH REQUEST: FastAPI cache testing best practices. Context: strategies.py refactored to DI pattern, 97.6% coverage. Need validation for queue/cache/health modules. Questions: 1. Industry patterns for cache+DI? 2. Decorator vs factory? 3. Coverage expectations? 4. FastAPI gotchas? 5. Multi-level test structure?",
    "max_iterations": 1
}

print("Sending to Perplexity...")
try:
    resp = httpx.post('http://127.0.0.1:8000/api/v1/agent/send', json=perplexity_payload, timeout=120)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Message ID: {data.get('message_id')}")
    print(f"Content preview: {data.get('content', '')[:500]}")
except Exception as e:
    print(f"Error: {e}")
