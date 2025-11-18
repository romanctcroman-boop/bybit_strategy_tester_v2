"""
Тестирование интегрированного main app с JWT Auth, Rate Limiting и Sandbox
Phase 1 Security Integration Test
"""
import time
import requests

import os
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

def test_public_endpoints():
    """Тест 1: Публичные endpoints должны работать без JWT"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Публичные endpoints")
    print("="*60)
    
    # Health check
    resp = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"✅ Health check: {resp.status_code}")
    
    # Docs
    resp = requests.get(f"{BASE_URL}/docs")
    print(f"✅ Swagger docs: {resp.status_code}")
    
    return True

def test_login_and_jwt():
    """Тест 2: Login endpoint и получение JWT токена"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Login и JWT токены")
    print("="*60)
    
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    print(f"Login response: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        print(f"✅ Access token: {access_token[:50]}...")
        print(f"✅ Refresh token: {refresh_token[:50]}...")
        print(f"✅ Token type: {data.get('token_type')}")
        print(f"✅ Expires in: {data.get('expires_in')} seconds")
        return access_token
    else:
        print(f"❌ Login failed: {resp.text}")
        return None

def test_protected_endpoint(token):
    """Тест 3: Protected endpoint с JWT"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Protected endpoint /auth/me")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ User: {data.get('user')}")
        print(f"✅ Scopes: {data.get('scopes')}")
        return True
    else:
        print(f"❌ Failed: {resp.text}")
        return False

def test_rate_limiting():
    """Тест 4: Rate limiting - проверка лимитов"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Rate Limiting")
    print("="*60)
    
    # Сделаем 25 запросов к /api/v1/health (лимит 20 за 30 сек)
    success_count = 0
    rate_limited = False
    
    for i in range(25):
        resp = requests.get(f"{BASE_URL}/api/v1/health")
        if resp.status_code == 200:
            success_count += 1
        elif resp.status_code == 429:
            rate_limited = True
            print(f"⚠️ Rate limited after {success_count} requests!")
            print(f"Response: {resp.text}")
            break
        time.sleep(0.1)  # Small delay
    
    if rate_limited:
        print(f"✅ Rate limiting works! Limited after {success_count} requests")
        return True
    else:
        print(f"⚠️ Made {success_count} requests without hitting rate limit")
        return False

def test_unauthorized_access():
    """Тест 5: Доступ без токена к protected endpoint"""
    print("\n" + "="*60)
    print("ТЕСТ 5: Unauthorized access")
    print("="*60)
    
    # Попытка доступа к /auth/me без токена
    resp = requests.get(f"{BASE_URL}/api/v1/auth/me")
    
    if resp.status_code == 401 or resp.status_code == 403:
        print(f"✅ Access denied without token: {resp.status_code}")
        return True
    else:
        print(f"❌ Should have been denied but got: {resp.status_code}")
        return False

def main():
    print("="*60)
    print("PHASE 1 SECURITY INTEGRATION TEST")
    print("Main App: backend.api.app:app")
    print("="*60)
    
    try:
        # Test 1: Public endpoints
        test_public_endpoints()
        
        # Test 2: Login
        token = test_login_and_jwt()
        if not token:
            print("\n❌ Cannot continue without token")
            return
        
        # Test 3: Protected endpoint
        test_protected_endpoint(token)
        
        # Test 4: Unauthorized
        test_unauthorized_access()
        
        # Test 5: Rate limiting (последний, т.к. может заблокировать IP)
        test_rate_limiting()
        
        print("\n" + "="*60)
        print("✅ INTEGRATION TEST COMPLETE!")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server at localhost:8000")
        print("Make sure the server is running:")
        print("  py -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()
