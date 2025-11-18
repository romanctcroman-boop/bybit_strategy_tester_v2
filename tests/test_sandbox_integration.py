"""
Integration tests for sandbox subsystem
Tests Docker isolation, security validation, resource monitoring, and manager orchestration
"""

import asyncio
import pytest
from pathlib import Path

from backend.sandbox import (
    DockerSandbox,
    SecurityValidator,
    ResourceLimiter,
    SandboxManager,
    SecurityLevel,
    ResourceLimits
)


class TestDockerSandbox:
    """Test Docker-based isolation"""
    
    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """Test basic code execution in Docker"""
        sandbox = DockerSandbox()
        
        code = "print('Hello from Docker sandbox!')"
        result = await sandbox.execute_code(code)
        
        assert result["success"] is True
        assert "Hello from Docker sandbox!" in result["output"]
        assert result["exit_code"] == 0
        
        sandbox.cleanup()
    
    @pytest.mark.asyncio
    async def test_network_isolation(self):
        """Test that network is disabled"""
        sandbox = DockerSandbox(network_disabled=True)
        
        code = """
import socket
try:
    socket.create_connection(('google.com', 80), timeout=2)
    print('NETWORK_ACCESSIBLE')
except Exception as e:
    print(f'NETWORK_BLOCKED: {e}')
"""
        result = await sandbox.execute_code(code)
        
        assert "NETWORK_BLOCKED" in result["output"]
        assert "NETWORK_ACCESSIBLE" not in result["output"]
        
        sandbox.cleanup()
    
    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        """Test that timeout is enforced"""
        sandbox = DockerSandbox(timeout=2)
        
        code = """
import time
print('Starting infinite loop')
time.sleep(10)
print('Should not reach here')
"""
        result = await sandbox.execute_code(code)
        
        assert result["timeout_exceeded"] is True
        assert "Starting infinite loop" in result["output"]
        assert "Should not reach here" not in result["output"]
        
        sandbox.cleanup()
    
    @pytest.mark.asyncio
    async def test_readonly_filesystem(self):
        """Test that filesystem is read-only except /tmp"""
        sandbox = DockerSandbox()
        
        # Try to write to root - should fail
        code = """
try:
    with open('/test.txt', 'w') as f:
        f.write('test')
    print('ROOT_WRITABLE')
except Exception as e:
    print(f'ROOT_READONLY: {type(e).__name__}')

# Try to write to /tmp - should succeed
try:
    with open('/tmp/test.txt', 'w') as f:
        f.write('test')
    print('TMP_WRITABLE')
except Exception as e:
    print(f'TMP_FAILED: {e}')
"""
        result = await sandbox.execute_code(code)
        
        assert "ROOT_READONLY" in result["output"]
        assert "TMP_WRITABLE" in result["output"]
        
        sandbox.cleanup()


class TestSecurityValidator:
    """Test static security analysis"""
    
    def test_safe_code(self):
        """Test validation of safe code"""
        validator = SecurityValidator()
        
        code = """
def add(a, b):
    return a + b

result = add(2, 3)
print(result)
"""
        result = validator.validate_code(code)
        
        assert result["safe"] is True
        assert result["score"] > 80
        assert len(result["issues"]) == 0
    
    def test_dangerous_imports(self):
        """Test detection of dangerous imports"""
        validator = SecurityValidator(strict_mode=True)
        
        code = """
import os
import sys
os.system('ls')
"""
        result = validator.validate_code(code)
        
        assert result["safe"] is False
        assert result["security_level"].value >= SecurityLevel.HIGH.value
        assert any(issue["type"] == "dangerous_import" for issue in result["issues"])
    
    def test_dangerous_functions(self):
        """Test detection of dangerous function calls"""
        validator = SecurityValidator()
        
        code = """
user_input = "malicious code"
eval(user_input)
"""
        result = validator.validate_code(code)
        
        assert result["safe"] is False
        assert result["security_level"] == SecurityLevel.CRITICAL
        assert any(issue["type"] == "dangerous_function" for issue in result["issues"])
    
    def test_dangerous_attributes(self):
        """Test detection of dangerous attribute access"""
        validator = SecurityValidator()
        
        code = """
class MyClass:
    pass

obj = MyClass()
globals_access = obj.__class__.__bases__[0].__subclasses__()
"""
        result = validator.validate_code(code)
        
        assert len(result["issues"]) > 0
        assert any(issue["type"] == "dangerous_attribute" for issue in result["issues"])
    
    def test_javascript_validation(self):
        """Test validation of JavaScript code"""
        validator = SecurityValidator()
        
        code = """
const fs = require('fs');
eval('malicious code');
"""
        result = validator.validate_code(code, language='javascript')
        
        assert result["safe"] is False
        assert len(result["issues"]) > 0


class TestResourceLimiter:
    """Test runtime resource monitoring"""
    
    @pytest.mark.asyncio
    async def test_resource_tracking(self):
        """Test basic resource tracking"""
        limits = ResourceLimits(
            max_cpu_percent=100.0,
            max_memory_mb=512,
            max_execution_time=30
        )
        limiter = ResourceLimiter(limits)
        
        # Execute code in Docker
        sandbox = DockerSandbox()
        code = "print('Resource tracking test')"
        result = await sandbox.execute_code(code)
        
        # Start monitoring (container already finished, but test the API)
        if result["container_id"]:
            await limiter.start_monitoring(result["container_id"], interval=0.1)
            await asyncio.sleep(0.5)
            await limiter.stop_monitoring()
            
            report = limiter.get_usage_report()
            assert report is not None
        
        sandbox.cleanup()
    
    def test_violation_detection(self):
        """Test detection of resource limit violations"""
        limits = ResourceLimits(
            max_cpu_percent=50.0,  # Low limit to trigger violation
            max_memory_mb=100      # Low limit to trigger violation
        )
        limiter = ResourceLimiter(limits)
        
        # Create a mock usage that violates limits
        from backend.sandbox.resource_limiter import ResourceUsage
        import time
        
        violation_usage = ResourceUsage(
            cpu_percent=75.0,  # Exceeds 50%
            memory_mb=150.0,   # Exceeds 100MB
            execution_time=5.0,
            io_operations=100,
            timestamp=time.time()
        )
        
        # Check violation
        has_violation = limiter._check_violations(violation_usage)
        assert has_violation is True


class TestSandboxManager:
    """Test high-level sandbox orchestration"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete execution workflow with all features"""
        manager = SandboxManager(strict_security=True)
        
        code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f'Fibonacci(10) = {result}')
"""
        
        result = await manager.execute_code(
            code=code,
            validate_security=True,
            monitor_resources=True
        )
        
        assert result["success"] is True
        assert "Fibonacci(10) = 55" in result["output"]
        assert result["security_report"] is not None
        assert result["security_report"]["safe"] is True
        
        manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_security_rejection(self):
        """Test that dangerous code is rejected"""
        manager = SandboxManager(strict_security=True)
        
        dangerous_code = """
import os
os.system('rm -rf /')
"""
        
        result = await manager.execute_code(
            code=dangerous_code,
            validate_security=True
        )
        
        assert result["success"] is False
        assert result["security_report"] is not None
        assert result["security_report"]["safe"] is False
        
        manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_batch_execution(self):
        """Test batch execution of multiple code snippets"""
        manager = SandboxManager()
        
        codes = [
            {"code": "print('Test 1')", "language": "python"},
            {"code": "print('Test 2')", "language": "python"},
            {"code": "print('Test 3')", "language": "python"}
        ]
        
        results = await manager.execute_batch(codes)
        
        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert "Test 1" in results[0]["output"]
        assert "Test 2" in results[1]["output"]
        assert "Test 3" in results[2]["output"]
        
        manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_execution_stats(self):
        """Test execution statistics tracking"""
        manager = SandboxManager()
        
        # Execute some code
        await manager.execute_code("print('Test 1')")
        await manager.execute_code("print('Test 2')")
        
        stats = manager.get_execution_stats()
        
        assert stats["total_executions"] == 2
        assert stats["successful"] == 2
        assert stats["success_rate"] == 100.0
        
        manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_sandbox_functionality(self):
        """Test sandbox test functionality"""
        manager = SandboxManager()
        
        test_passed = await manager.test_sandbox()
        
        assert test_passed is True
        
        manager.cleanup()


@pytest.mark.asyncio
async def test_full_integration():
    """
    Full integration test:
    1. Create manager
    2. Execute safe code
    3. Execute dangerous code
    4. Check statistics
    5. Cleanup
    """
    print("\n" + "="*60)
    print("FULL INTEGRATION TEST")
    print("="*60)
    
    manager = SandboxManager(
        strict_security=True,
        resource_limits=ResourceLimits(
            max_cpu_percent=100.0,
            max_memory_mb=512,
            max_execution_time=30
        )
    )
    
    # Test 1: Safe code
    print("\n[Test 1] Executing safe code...")
    safe_result = await manager.execute_code(
        code="print('Hello, secure world!')",
        validate_security=True,
        monitor_resources=True
    )
    print(manager.format_execution_report(safe_result))
    assert safe_result["success"] is True
    
    # Test 2: Dangerous code
    print("\n[Test 2] Executing dangerous code...")
    dangerous_result = await manager.execute_code(
        code="import os; os.system('ls')",
        validate_security=True,
        monitor_resources=True
    )
    print(manager.format_execution_report(dangerous_result))
    assert dangerous_result["success"] is False
    
    # Test 3: Statistics
    print("\n[Test 3] Execution statistics...")
    stats = manager.get_execution_stats()
    print(f"Total executions: {stats['total_executions']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Security violations: {stats['security_violations']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    
    assert stats["total_executions"] == 2
    assert stats["security_violations"] == 1
    
    # Cleanup
    print("\n[Test 4] Cleanup...")
    manager.cleanup()
    
    print("\n✅ ALL INTEGRATION TESTS PASSED")
    print("="*60)


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_full_integration())
