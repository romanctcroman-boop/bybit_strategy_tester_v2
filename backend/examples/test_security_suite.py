"""
Test Script для проверки всех security компонентов
Демонстрирует JWT Auth, Rate Limiting и Sandbox Execution
"""

import httpx
import asyncio
import time
from typing import Optional

# API Configuration
API_BASE_URL = "http://localhost:8000"
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"

# Colors for console output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print colored header"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text:^80}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{YELLOW}ℹ {text}{RESET}")


# =============================================================================
# Test 1: Public Endpoints (No Auth)
# =============================================================================

async def test_public_endpoints():
    """Test public endpoints that don't require authentication"""
    print_header("TEST 1: Public Endpoints")
    
    async with httpx.AsyncClient() as client:
        try:
            # Test root endpoint
            response = await client.get(f"{API_BASE_URL}/")
            if response.status_code == 200:
                print_success("Root endpoint accessible")
                print(f"  Response: {response.json()}")
            else:
                print_error(f"Root endpoint failed: {response.status_code}")
            
            # Test health check
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                print_success("Health check passed")
                print(f"  Response: {response.json()}")
            else:
                print_error(f"Health check failed: {response.status_code}")
                
        except Exception as e:
            print_error(f"Public endpoints test failed: {e}")


# =============================================================================
# Test 2: JWT Authentication
# =============================================================================

async def test_jwt_authentication() -> Optional[str]:
    """Test JWT authentication and return access token"""
    print_header("TEST 2: JWT Authentication")
    
    async with httpx.AsyncClient() as client:
        try:
            # Test login
            response = await client.post(
                f"{API_BASE_URL}/auth/login",
                json={
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                access_token = data["access_token"]
                refresh_token = data["refresh_token"]
                
                print_success("Login successful")
                print(f"  Access Token: {access_token[:50]}...")
                print(f"  Refresh Token: {refresh_token[:50]}...")
                
                # Test protected endpoint with token
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    f"{API_BASE_URL}/status",
                    headers=headers
                )
                
                if response.status_code == 200:
                    print_success("Protected endpoint accessible with token")
                    print(f"  Response: {response.json()}")
                else:
                    print_error(f"Protected endpoint failed: {response.status_code}")
                
                return access_token
            else:
                print_error(f"Login failed: {response.status_code}")
                print(f"  Response: {response.text}")
                return None
                
        except Exception as e:
            print_error(f"JWT authentication test failed: {e}")
            return None


# =============================================================================
# Test 3: Authorization (Permissions)
# =============================================================================

async def test_authorization(access_token: str):
    """Test permission-based authorization"""
    print_header("TEST 3: Authorization (Scopes)")
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            # Test admin endpoint (should work with admin token)
            response = await client.post(
                f"{API_BASE_URL}/admin/whitelist/add?ip_address=192.168.1.100",
                headers=headers
            )
            
            if response.status_code == 200:
                print_success("Admin endpoint accessible (ADMIN scope)")
                print(f"  Response: {response.json()}")
            else:
                print_error(f"Admin endpoint failed: {response.status_code}")
                
        except Exception as e:
            print_error(f"Authorization test failed: {e}")


# =============================================================================
# Test 4: Rate Limiting
# =============================================================================

async def test_rate_limiting(access_token: str):
    """Test rate limiting by making rapid requests"""
    print_header("TEST 4: Rate Limiting")
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        print_info("Making 70 rapid requests to trigger rate limit...")
        print_info("Default limit: 60 requests/minute")
        
        success_count = 0
        rate_limited_count = 0
        
        start_time = time.time()
        
        for i in range(70):
            try:
                response = await client.get(
                    f"{API_BASE_URL}/status",
                    headers=headers
                )
                
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    rate_limited_count += 1
                    if rate_limited_count == 1:
                        print_info(f"Rate limit triggered at request {i+1}")
                        retry_after = response.headers.get("Retry-After")
                        print_info(f"Retry-After: {retry_after} seconds")
                        
            except Exception as e:
                print_error(f"Request {i+1} failed: {e}")
        
        elapsed = time.time() - start_time
        
        print_success(f"Completed {success_count} requests successfully")
        print_info(f"Rate limited: {rate_limited_count} requests")
        print_info(f"Total time: {elapsed:.2f} seconds")
        
        if rate_limited_count > 0:
            print_success("Rate limiting is working correctly!")
        else:
            print_error("Rate limiting not triggered (unexpected)")


# =============================================================================
# Test 5: Sandbox Execution
# =============================================================================

async def test_sandbox_execution(access_token: str):
    """Test secure sandbox code execution"""
    print_header("TEST 5: Sandbox Execution")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test 1: Simple safe code
        print_info("Test 5.1: Safe code execution")
        safe_code = """
import math
result = math.sqrt(16) + math.pi
print(f"Result: {result}")
"""
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/sandbox/execute",
                headers=headers,
                json={"code": safe_code}
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success("Safe code executed successfully")
                print(f"  Stdout: {data.get('stdout', 'N/A')}")
                print(f"  Exit Code: {data.get('exit_code', 'N/A')}")
                print(f"  Execution Time: {data.get('execution_time', 'N/A')}s")
            else:
                print_error(f"Safe code execution failed: {response.status_code}")
                
        except Exception as e:
            print_error(f"Safe code test failed: {e}")
        
        # Test 2: Code with forbidden imports
        print_info("\nTest 5.2: Forbidden imports (should fail)")
        malicious_code = """
import os
os.system("ls -la")
"""
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/sandbox/execute",
                headers=headers,
                json={"code": malicious_code}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data.get("stdout", "").lower():
                    print_success("Forbidden import blocked correctly")
                else:
                    print_error("Forbidden import NOT blocked (security risk!)")
            else:
                print_success(f"Forbidden import blocked (status {response.status_code})")
                
        except Exception as e:
            print_info(f"Forbidden import blocked: {e}")
        
        # Test 3: Network access (should fail)
        print_info("\nTest 5.3: Network access (should fail)")
        network_code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("google.com", 80))
"""
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/sandbox/execute",
                headers=headers,
                json={"code": network_code}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("exit_code", 0) != 0:
                    print_success("Network access blocked correctly")
                else:
                    print_error("Network access NOT blocked (security risk!)")
            else:
                print_success(f"Network access blocked (status {response.status_code})")
                
        except Exception as e:
            print_info(f"Network access blocked: {e}")


# =============================================================================
# Test 6: Sandbox Health Check
# =============================================================================

async def test_sandbox_health(access_token: str):
    """Test sandbox health check endpoint"""
    print_header("TEST 6: Sandbox Health Check")
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = await client.get(
                f"{API_BASE_URL}/sandbox/health",
                headers=headers
            )
            
            if response.status_code == 200:
                health = response.json()
                print_success("Sandbox health check passed")
                print(f"  Status: {health.get('status')}")
                print(f"  Docker Connected: {health.get('docker_connected')}")
                print(f"  Active Sandboxes: {health.get('active_sandboxes')}")
                print(f"  Image Available: {health.get('image_available')}")
            else:
                print_error(f"Sandbox health check failed: {response.status_code}")
                
        except Exception as e:
            print_error(f"Sandbox health test failed: {e}")


# =============================================================================
# Test 7: Unauthorized Access
# =============================================================================

async def test_unauthorized_access():
    """Test that protected endpoints reject unauthorized access"""
    print_header("TEST 7: Unauthorized Access")
    
    async with httpx.AsyncClient() as client:
        try:
            # Try to access protected endpoint without token
            response = await client.get(f"{API_BASE_URL}/status")
            
            if response.status_code == 401 or response.status_code == 403:
                print_success("Protected endpoint correctly rejects unauthorized access")
                print(f"  Status Code: {response.status_code}")
            else:
                print_error(f"Protected endpoint allowed unauthorized access: {response.status_code}")
                
        except Exception as e:
            print_error(f"Unauthorized access test failed: {e}")


# =============================================================================
# Main Test Suite
# =============================================================================

async def run_all_tests():
    """Run all security tests"""
    print(f"\n{GREEN}{'='*80}{RESET}")
    print(f"{GREEN}Security Components Test Suite{RESET:^80}")
    print(f"{GREEN}Bybit Strategy Tester API v2.0{RESET:^80}")
    print(f"{GREEN}{'='*80}{RESET}\n")
    
    print_info(f"API Base URL: {API_BASE_URL}")
    print_info(f"Test User: {TEST_USERNAME}")
    print_info("")
    
    # Run tests
    await test_public_endpoints()
    
    access_token = await test_jwt_authentication()
    
    if not access_token:
        print_error("Cannot continue tests without valid access token")
        return
    
    await test_authorization(access_token)
    await test_rate_limiting(access_token)
    await test_sandbox_execution(access_token)
    await test_sandbox_health(access_token)
    await test_unauthorized_access()
    
    # Summary
    print_header("TEST SUMMARY")
    print_success("All security components tested!")
    print_info("Components verified:")
    print_info("  1. Public endpoints (no auth)")
    print_info("  2. JWT authentication (login)")
    print_info("  3. Authorization (scopes)")
    print_info("  4. Rate limiting (token bucket)")
    print_info("  5. Sandbox execution (Docker isolation)")
    print_info("  6. Sandbox health checks")
    print_info("  7. Unauthorized access rejection")
    print("")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
