"""
Quick test to verify rate limiting works
"""
import requests
import time

BASE_URL = "http://localhost:8002"

print("Testing rate limiting on /api/v1/health endpoint...")
print("Making 25 requests quickly...")

for i in range(25):
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=2)
        print(f"Request {i+1}: Status {resp.status_code}")
        
        if resp.status_code == 429:
            print(f"\n✅ Rate limiting WORKS! Hit limit at request {i+1}")
            print(f"Response: {resp.json()}")
            break
    except Exception as e:
        print(f"Request {i+1}: Error - {e}")
    
    time.sleep(0.05)  # 50ms между запросами
else:
    print(f"\n⚠️ Completed 25 requests without hitting rate limit")

print("\nRate limiter config check:")
print("- Default capacity: 10 requests")
print("- Default refill_rate: 0.3 tokens/sec (18/min)")
print("- Endpoint /health has no specific limit, uses default")
