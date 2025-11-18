"""Quick test - check if queue endpoints work"""
import httpx

print("Testing queue endpoints directly...")

try:
    # Test health
    r = httpx.get("http://localhost:8000/api/v1/queue/health", timeout=5)
    print(f"\n✅ /api/v1/queue/health: {r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {r.json()}")
    else:
        print(f"   Error: {r.text}")
        
    # Test metrics  
    r = httpx.get("http://localhost:8000/api/v1/queue/metrics", timeout=5)
    print(f"\n✅ /api/v1/queue/metrics: {r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {r.json()}")
    else:
        print(f"   Error: {r.text}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
