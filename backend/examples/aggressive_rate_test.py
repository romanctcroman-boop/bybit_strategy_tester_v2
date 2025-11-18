"""
Aggressive rate limiting test - без задержек между запросами
"""
import requests
import time

BASE_URL = "http://localhost:8002"

print("=" * 60)
print("AGGRESSIVE RATE LIMITING TEST")
print("=" * 60)
print(f"Target: {BASE_URL}/api/v1/health")
print(f"Expected limit: 10 requests (capacity)")
print(f"Refill rate: 0.3 tokens/sec")
print("=" * 60)

success_count = 0
rate_limited_at = None

start_time = time.time()

for i in range(30):
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=1)
        
        if resp.status_code == 200:
            success_count += 1
            print(f"✅ Request {i+1}: SUCCESS (200)")
        elif resp.status_code == 429:
            rate_limited_at = i + 1
            print(f"\n🛑 Request {i+1}: RATE LIMITED (429)")
            print(f"Response: {resp.json()}")
            print(f"Headers: {dict(resp.headers)}")
            break
        else:
            print(f"⚠️ Request {i+1}: Unexpected status {resp.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Request {i+1}: TIMEOUT")
    except Exception as e:
        print(f"❌ Request {i+1}: ERROR - {e}")
        break

elapsed = time.time() - start_time

print("\n" + "=" * 60)
print("РЕЗУЛЬТАТЫ:")
print("=" * 60)
print(f"Успешных запросов: {success_count}")
print(f"Rate limited на запросе: {rate_limited_at if rate_limited_at else 'НЕТ'}")
print(f"Время теста: {elapsed:.2f} секунд")
print(f"Запросов в секунду: {success_count/elapsed:.2f}")

if rate_limited_at:
    print("\n✅ RATE LIMITING РАБОТАЕТ!")
    print(f"   Заблокирован после {success_count} успешных запросов")
else:
    print("\n⚠️ RATE LIMITING НЕ СРАБОТАЛ")
    print(f"   Прошло {success_count} запросов без блокировки")
