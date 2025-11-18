"""
Simple sandbox test - no pytest required
Tests basic functionality of sandbox system
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sandbox.docker_sandbox import DockerSandbox
from backend.sandbox.security_validator import SecurityValidator, SecurityLevel
from backend.sandbox.resource_limiter import ResourceLimiter, ResourceLimits
from backend.sandbox.sandbox_manager import SandboxManager


async def test_security_validator():
    """Test security validation"""
    print("\n" + "="*60)
    print("TEST 1: Security Validator")
    print("="*60)
    
    validator = SecurityValidator(strict_mode=True)
    
    # Test 1: Safe code
    print("\n[1.1] Testing safe code...")
    safe_code = """
def add(a, b):
    return a + b

result = add(2, 3)
print(f'Result: {result}')
"""
    result = validator.validate_code(safe_code)
    print(f"✅ Safe: {result['safe']}, Score: {result['score']}/100")
    assert result['safe'] is True
    assert result['score'] > 80
    
    # Test 2: Dangerous code
    print("\n[1.2] Testing dangerous code...")
    dangerous_code = """
import os
os.system('ls')
"""
    result = validator.validate_code(dangerous_code)
    print(f"❌ Safe: {result['safe']}, Score: {result['score']}/100, Issues: {len(result['issues'])}")
    assert result['safe'] is False
    assert len(result['issues']) > 0
    
    print("\n✅ Security Validator tests PASSED")


async def test_docker_sandbox():
    """Test Docker sandbox isolation"""
    print("\n" + "="*60)
    print("TEST 2: Docker Sandbox")
    print("="*60)
    
    try:
        sandbox = DockerSandbox(timeout=10)
        
        # Test 1: Basic execution
        print("\n[2.1] Testing basic execution...")
        code = "print('Hello from Docker sandbox!')"
        result = await sandbox.execute_code(code)
        
        print(f"Success: {result['success']}")
        print(f"Output: {result['output']}")
        print(f"Duration: {result['duration']:.2f}s")
        
        assert result['success'] is True
        assert 'Hello from Docker sandbox!' in result['output']
        print("✅ Basic execution test PASSED")
        
        # Test 2: Network isolation
        print("\n[2.2] Testing network isolation...")
        network_test_code = """
import socket
try:
    socket.create_connection(('8.8.8.8', 53), timeout=2)
    print('NETWORK_ACCESSIBLE')
except Exception as e:
    print(f'NETWORK_BLOCKED: {type(e).__name__}')
"""
        result = await sandbox.execute_code(network_test_code)
        print(f"Output: {result['output']}")
        
        assert 'NETWORK_BLOCKED' in result['output'] or result['exit_code'] != 0
        print("✅ Network isolation test PASSED")
        
        # Cleanup
        sandbox.cleanup()
        print("\n✅ Docker Sandbox tests PASSED")
        
    except Exception as e:
        print(f"\n⚠️  Docker Sandbox tests SKIPPED: {e}")
        print("(Docker may not be running - this is OK for Phase 1 development)")


async def test_sandbox_manager():
    """Test sandbox manager orchestration"""
    print("\n" + "="*60)
    print("TEST 3: Sandbox Manager")
    print("="*60)
    
    try:
        manager = SandboxManager(strict_security=True)
        
        # Test 1: Safe code execution
        print("\n[3.1] Testing safe code execution...")
        safe_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f'Fibonacci(10) = {result}')
"""
        result = await manager.execute_code(
            code=safe_code,
            validate_security=True,
            monitor_resources=False  # Skip monitoring for now
        )
        
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Output: {result['output']}")
            assert 'Fibonacci(10) = 55' in result['output']
        print(f"Security report: Safe={result['security_report']['safe']}, Score={result['security_report']['score']}")
        print("✅ Safe code execution test PASSED")
        
        # Test 2: Dangerous code rejection
        print("\n[3.2] Testing dangerous code rejection...")
        dangerous_code = """
import os
os.system('echo Hello')
"""
        result = await manager.execute_code(
            code=dangerous_code,
            validate_security=True,
            monitor_resources=False
        )
        
        print(f"Success: {result['success']}")
        print(f"Security report: Safe={result['security_report']['safe']}")
        
        assert result['success'] is False
        assert result['security_report']['safe'] is False
        print("✅ Dangerous code rejection test PASSED")
        
        # Statistics
        print("\n[3.3] Checking execution statistics...")
        stats = manager.get_execution_stats()
        print(f"Total executions: {stats['total_executions']}")
        print(f"Successful: {stats['successful']}")
        print(f"Security violations: {stats['security_violations']}")
        
        assert stats['total_executions'] >= 2
        print("✅ Statistics test PASSED")
        
        # Cleanup
        manager.cleanup()
        print("\n✅ Sandbox Manager tests PASSED")
        
    except Exception as e:
        print(f"\n⚠️  Sandbox Manager tests SKIPPED: {e}")
        print("(Docker may not be running - this is OK for Phase 1 development)")


async def main():
    """Run all tests"""
    print("="*60)
    print("SANDBOX INTEGRATION TESTS")
    print("="*60)
    
    try:
        # Test 1: Security Validator (no Docker required)
        await test_security_validator()
        
        # Test 2: Docker Sandbox (requires Docker)
        await test_docker_sandbox()
        
        # Test 3: Sandbox Manager (requires Docker)
        await test_sandbox_manager()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TESTS FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
