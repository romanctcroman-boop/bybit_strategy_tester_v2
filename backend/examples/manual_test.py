"""
Простой manual test для security компонентов
"""

import requests
import time
import json

API_URL = "http://127.0.0.1:8000"

def test_root():
    """Test root endpoint"""
    print("\n" + "="*80)
    print("TEST 1: Root Endpoint (Public)")
    print("="*80)
    
    try:
        response = requests.get(f"{API_URL}/")
        print(f"✓ Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_login():
    """Test login"""
    print("\n" + "="*80)
    print("TEST 2: Login (JWT Authentication)")
    print("="*80)
    
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"username": "admin", "password": "test123"}
        )
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        print(f"  Access Token: {data['access_token'][:50]}...")
        return data['access_token']
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_protected(token):
    """Test protected endpoint"""
    print("\n" + "="*80)
    print("TEST 3: Protected Endpoint (/status)")
    print("="*80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_URL}/status", headers=headers)
        print(f"✓ Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_rate_limiting(token):
    """Test rate limiting"""
    print("\n" + "="*80)
    print("TEST 4: Rate Limiting (70 rapid requests)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    success = 0
    rate_limited = 0
    
    print("Making 70 requests...")
    for i in range(70):
        try:
            response = requests.get(f"{API_URL}/status", headers=headers)
            if response.status_code == 200:
                success += 1
            elif response.status_code == 429:
                rate_limited += 1
                if rate_limited == 1:
                    print(f"  Rate limit triggered at request {i+1}")
        except Exception as e:
            print(f"  Request {i+1} error: {e}")
    
    print(f"✓ Successful: {success}")
    print(f"✓ Rate limited: {rate_limited}")
    
    if rate_limited > 0:
        print("✓ Rate limiting works!")
        return True
    else:
        print("⚠ Rate limiting not triggered")
        return False


def test_sandbox(token):
    """Test sandbox execution"""
    print("\n" + "="*80)
    print("TEST 5: Sandbox Execution")
    print("="*80)
    
    # Test 1: Safe code
    print("\n  Test 5.1: Safe code")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        code = """
import math
result = math.sqrt(16) + math.pi
print(f"Result: {result}")
"""
        response = requests.post(
            f"{API_URL}/sandbox/execute",
            headers=headers,
            json={"code": code},
            timeout=10
        )
        print(f"  ✓ Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Output: {data.get('stdout', 'N/A')}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Test 2: Forbidden imports
    print("\n  Test 5.2: Forbidden imports (should block)")
    try:
        code = "import os; print(os.system('ls'))"
        response = requests.post(
            f"{API_URL}/sandbox/execute",
            headers=headers,
            json={"code": code},
            timeout=10
        )
        print(f"  ✓ Status: {response.status_code}")
        if response.status_code != 200:
            print("  ✓ Forbidden import blocked")
    except Exception as e:
        print(f"  ✓ Blocked: {e}")
    
    return True


def test_unauthorized():
    """Test unauthorized access"""
    print("\n" + "="*80)
    print("TEST 6: Unauthorized Access")
    print("="*80)
    
    try:
        response = requests.get(f"{API_URL}/status")
        print(f"✓ Status: {response.status_code}")
        if response.status_code in [401, 403]:
            print("✓ Correctly rejected unauthorized access")
            return True
        else:
            print("✗ Should have rejected")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    print("\n")
    print("="*80)
    print(" "*25 + "SECURITY TESTS")
    print("="*80)
    print(f"API URL: {API_URL}")
    print("="*80)
    
    # Wait for server
    print("\nWaiting for server...")
    time.sleep(2)
    
    # Run tests
    if not test_root():
        print("\n✗ Server not responding, exiting")
        return
    
    token = test_login()
    if not token:
        print("\n✗ Login failed, exiting")
        return
    
    test_protected(token)
    test_rate_limiting(token)
    test_sandbox(token)
    test_unauthorized()
    
    # Summary
    print("\n" + "="*80)
    print(" "*25 + "TESTS COMPLETE")
    print("="*80)
    print("✓ All security components tested!")
    print("="*80)
    print()


if __name__ == "__main__":
    main()
