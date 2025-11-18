"""
Диагностический тест для Agent-to-Agent Backend
"""

import requests
import asyncio
import websockets
import json

print("=" * 80)
print(" Agent-to-Agent Backend Diagnostic")
print("=" * 80)

# 1. Проверка порта 8000
print("\n1. Checking if port 8000 is open...")
try:
    response = requests.get("http://localhost:8000/", timeout=5)
    print(f"✅ Port 8000 is open")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to port 8000 - backend не запущен!")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# 2. Проверка health endpoint
print("\n2. Checking Agent-to-Agent health endpoint...")
try:
    response = requests.get("http://localhost:8000/api/v1/agent/health", timeout=5)
    print(f"✅ Health endpoint accessible")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"⚠️ Health endpoint error: {e}")

# 3. Проверка WebSocket
print("\n3. Testing WebSocket connection...")
async def test_ws():
    uri = "ws://localhost:8000/api/v1/agent/ws/test-diag"
    print(f"   Connecting to {uri}...")
    try:
        async with websockets.connect(uri, ping_timeout=10, close_timeout=10) as ws:
            print("✅ WebSocket connected!")
            
            # Ping
            await ws.send(json.dumps({"command": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"   Ping response: {response}")
            
            return True
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

success = asyncio.run(test_ws())

if success:
    print("\n" + "=" * 80)
    print(" ✅ ALL DIAGNOSTICS PASSED")
    print("=" * 80)
else:
    print("\n" + "=" * 80)
    print(" ❌ DIAGNOSTICS FAILED")
    print("=" * 80)
