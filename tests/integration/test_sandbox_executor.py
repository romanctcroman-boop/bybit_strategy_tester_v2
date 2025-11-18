"""
Integration tests для Sandbox Executor
pytest tests/integration/test_sandbox_executor.py -v
"""

import pytest
import asyncio
from pathlib import Path

from backend.services.sandbox_executor import (
    SandboxExecutor,
    SandboxExecutionResult,
    execute_code_in_sandbox
)
from backend.core.code_validator import CodeValidator, RiskLevel


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def executor():
    """Create sandbox executor instance"""
    executor = SandboxExecutor(
        timeout=30,
        validate_code=True,
        max_risk_score=30
    )
    yield executor
    executor.cleanup()


@pytest.fixture
def safe_code():
    """Sample safe Python code"""
    return """
import numpy as np
import pandas as pd

# Simple calculation
data = np.array([1, 2, 3, 4, 5])
result = np.mean(data)
print(f"Result: {result}")
"""


@pytest.fixture
def dangerous_code_os():
    """Code that imports blacklisted module (os)"""
    return """
import os

# Try to access filesystem
files = os.listdir('/')
print(files)
"""


@pytest.fixture
def dangerous_code_eval():
    """Code that uses dangerous builtin (eval)"""
    return """
code = "print('Hello')"
result = eval(code)
"""


@pytest.fixture
def dangerous_code_file_io():
    """Code that tries file I/O"""
    return """
with open('/etc/passwd', 'r') as f:
    data = f.read()
    print(data)
"""


@pytest.fixture
def timeout_code():
    """Code that will timeout"""
    return """
import time
while True:
    time.sleep(0.1)
"""


# =============================================================================
# Code Validator Tests
# =============================================================================

def test_validator_safe_code(safe_code):
    """Test that safe code passes validation"""
    validator = CodeValidator()
    result = validator.validate(safe_code)
    
    assert result.is_valid
    assert result.risk_score < 30
    assert result.risk_level == RiskLevel.LOW
    assert len(result.violations) == 0


def test_validator_dangerous_os(dangerous_code_os):
    """Test that code with 'os' module is blocked"""
    validator = CodeValidator()
    result = validator.validate(dangerous_code_os)
    
    assert not result.is_valid
    assert result.risk_score > 30
    assert any('os' in v['message'].lower() for v in result.violations)


def test_validator_dangerous_eval(dangerous_code_eval):
    """Test that code with 'eval' is blocked"""
    validator = CodeValidator()
    result = validator.validate(dangerous_code_eval)
    
    assert not result.is_valid
    assert result.risk_score > 30
    assert any('eval' in v['message'].lower() for v in result.violations)


def test_validator_dangerous_file_io(dangerous_code_file_io):
    """Test that code with file I/O is blocked"""
    validator = CodeValidator()
    result = validator.validate(dangerous_code_file_io)
    
    assert not result.is_valid
    assert result.risk_score > 30
    assert any('open' in v['message'].lower() or 'file' in v['message'].lower() 
               for v in result.violations)


# =============================================================================
# Sandbox Executor Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_safe_code(executor, safe_code):
    """Test execution of safe code"""
    result = await executor.execute(safe_code, timeout=30)
    
    assert result.success
    assert result.exit_code == 0
    assert "Result: 3.0" in result.stdout
    assert result.execution_time < 30
    assert result.validation_result is not None
    assert result.validation_result.is_valid


@pytest.mark.asyncio
async def test_execute_dangerous_code_blocked(executor, dangerous_code_os):
    """Test that dangerous code is blocked by validator"""
    result = await executor.execute(dangerous_code_os, timeout=30)
    
    assert not result.success
    assert result.exit_code == -1
    assert result.error is not None
    assert "validation" in result.error.lower() or "security" in result.error.lower()
    assert result.validation_result is not None
    assert not result.validation_result.is_valid


@pytest.mark.asyncio
async def test_execute_timeout(executor, timeout_code):
    """Test timeout handling"""
    result = await executor.execute(timeout_code, timeout=5)
    
    assert not result.success
    assert result.execution_time >= 5  # Should take at least timeout duration
    assert result.execution_time < 10  # But not much longer


@pytest.mark.asyncio
async def test_execute_without_validation(dangerous_code_os):
    """Test execution without validation (for debugging)"""
    # Note: This should still fail at Docker level (no 'os' access in container)
    executor = SandboxExecutor(validate_code=False)
    try:
        result = await executor.execute(dangerous_code_os, timeout=10)
        
        # Code passes validation but fails at runtime
        # because 'os' module operations are restricted in container
        assert not result.success or "permission denied" in result.stderr.lower()
        
    finally:
        executor.cleanup()


@pytest.mark.asyncio
async def test_resource_usage_monitoring(executor):
    """Test resource usage statistics"""
    code = """
import numpy as np

# Allocate 100MB array
data = np.zeros((100 * 1024 * 1024 // 8,), dtype=np.float64)
print(f"Allocated {data.nbytes / (1024**2):.0f} MB")
"""
    
    result = await executor.execute(code, timeout=30)
    
    assert result.success
    assert result.resource_usage is not None
    assert 'memory_usage_mb' in result.resource_usage
    assert result.resource_usage['memory_usage_mb'] > 0


@pytest.mark.asyncio
async def test_convenience_function(safe_code):
    """Test convenience function"""
    result = await execute_code_in_sandbox(safe_code, timeout=30)
    
    assert result.success
    assert result.exit_code == 0
    assert "Result: 3.0" in result.stdout


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_empty_code(executor):
    """Test execution of empty code"""
    result = await executor.execute("", timeout=10)
    
    # Empty code is valid but produces no output
    assert result.success
    assert result.exit_code == 0
    assert result.stdout == ""


@pytest.mark.asyncio
async def test_syntax_error(executor):
    """Test execution of code with syntax error"""
    code = """
print('Hello'
"""  # Missing closing parenthesis
    
    result = await executor.execute(code, timeout=10)
    
    # Syntax error should be caught
    # Either by AST parser (validation) or Python interpreter (runtime)
    assert not result.success
    assert result.exit_code != 0 or result.error is not None


@pytest.mark.asyncio
async def test_runtime_error(executor):
    """Test execution of code with runtime error"""
    code = """
x = 1 / 0  # Division by zero
"""
    
    result = await executor.execute(code, timeout=10)
    
    assert not result.success
    assert result.exit_code != 0
    assert "division" in result.stderr.lower() or "zerodivision" in result.stderr.lower()


@pytest.mark.asyncio
async def test_result_serialization(executor, safe_code):
    """Test result serialization to dict"""
    result = await executor.execute(safe_code, timeout=30)
    
    result_dict = result.to_dict()
    
    assert isinstance(result_dict, dict)
    assert 'success' in result_dict
    assert 'exit_code' in result_dict
    assert 'stdout' in result_dict
    assert 'stderr' in result_dict
    assert 'execution_time' in result_dict
    assert 'resource_usage' in result_dict
    assert 'validation' in result_dict


# =============================================================================
# Security Tests
# =============================================================================

@pytest.mark.asyncio
async def test_network_isolation(executor):
    """Test that network access is blocked"""
    code = """
import socket

try:
    # Try to create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('google.com', 80))
    print("SECURITY BREACH: Network access allowed!")
except Exception as e:
    print(f"Network blocked (expected): {e}")
"""
    
    # This code imports 'socket' which is blacklisted
    # So it should be blocked at validation stage
    result = await executor.execute(code, timeout=10)
    
    assert not result.success
    # Should be blocked by validator, not reach Docker
    assert "validation" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_filesystem_isolation(executor):
    """Test that filesystem access is blocked"""
    code = """
import pathlib

try:
    # Try to read sensitive file
    path = pathlib.Path('/etc/passwd')
    content = path.read_text()
    print("SECURITY BREACH: File access allowed!")
except Exception as e:
    print(f"Filesystem blocked (expected): {e}")
"""
    
    # Even if this passes validation, Docker container is read-only
    # (except /output directory)
    result = await executor.execute(code, timeout=10)
    
    # Should succeed (pathlib is allowed) but file read will fail
    if result.success:
        assert "blocked" in result.stdout.lower() or "permission" in result.stdout.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
