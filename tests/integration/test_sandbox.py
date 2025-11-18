"""
Bybit Strategy Tester V2 - Sandbox Integration Tests
=====================================================
Purpose: End-to-end testing of sandbox executor functionality
Coverage:
    - Basic execution
    - Security validation
    - Resource limits
    - Timeout handling
    - Docker isolation
Author: Multi-Agent System (DeepSeek + Perplexity AI)
Created: 2025-11-01
"""

import asyncio
import pytest
import time
from pathlib import Path

from backend.services.sandbox_executor import (
    SandboxExecutor,
    SandboxExecutionResult,
)
from backend.core.code_validator import SecurityLevel


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def executor():
    """Create sandbox executor instance"""
    executor = SandboxExecutor(
        timeout=30,
        memory_limit="256m",
        cpu_limit=0.5,
    )
    yield executor
    executor.close()


# ==============================================================================
# TEST: BASIC EXECUTION
# ==============================================================================

@pytest.mark.asyncio
async def test_basic_execution(executor):
    """Test basic code execution"""
    code = """
print("Hello from sandbox!")
result = 2 + 2
print(f"Result: {result}")
"""
    
    result = await executor.execute(code)
    
    assert result.success == True
    assert result.exit_code == 0
    assert "Hello from sandbox!" in result.stdout
    assert "Result: 4" in result.stdout
    assert result.execution_time > 0


@pytest.mark.asyncio
async def test_pandas_execution(executor):
    """Test pandas code execution"""
    code = """
import pandas as pd
import numpy as np

# Create test data
df = pd.DataFrame({
    'close': [100, 102, 101, 103, 105, 104, 106]
})

# Calculate SMA
sma = df['close'].rolling(window=3).mean()

print("SMA calculated:")
print(sma.tolist())
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert "SMA calculated" in result.stdout
    assert result.validation_result.security_score >= 90


@pytest.mark.asyncio
async def test_vectorbt_execution(executor):
    """Test vectorbt code execution"""
    code = """
import vectorbt as vbt
import pandas as pd
import numpy as np

# Create price data
price = pd.Series([100, 102, 101, 103, 105, 104, 106])

# Calculate indicators
sma_fast = vbt.MA.run(price, window=2)
sma_slow = vbt.MA.run(price, window=3)

print("Fast SMA:", sma_fast.ma.values[-1])
print("Slow SMA:", sma_slow.ma.values[-1])
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert "Fast SMA" in result.stdout
    assert "Slow SMA" in result.stdout


# ==============================================================================
# TEST: SECURITY VALIDATION
# ==============================================================================

@pytest.mark.asyncio
async def test_dangerous_os_blocked(executor):
    """Test that os module is blocked"""
    code = """
import os
os.system('ls -la /')
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert result.validation_result is not None
    assert result.validation_result.security_score < 70
    assert any("os" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_dangerous_eval_blocked(executor):
    """Test that eval() is blocked"""
    code = """
code = "print('hacked!')"
eval(code)
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("eval" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_dangerous_exec_blocked(executor):
    """Test that exec() is blocked"""
    code = """
exec("import os; os.system('rm -rf /')")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("exec" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_dangerous_subprocess_blocked(executor):
    """Test that subprocess is blocked"""
    code = """
import subprocess
subprocess.call(['ls', '-la'])
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("subprocess" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_dangerous_file_io_blocked(executor):
    """Test that file I/O is blocked"""
    code = """
with open('/etc/passwd', 'r') as f:
    data = f.read()
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("open" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_dangerous_import_blocked(executor):
    """Test that __import__ is blocked"""
    code = """
os_module = __import__('os')
os_module.system('whoami')
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("__import__" in str(v) for v in result.validation_result.violations)


# ==============================================================================
# TEST: RESOURCE LIMITS
# ==============================================================================

@pytest.mark.asyncio
async def test_timeout_enforcement():
    """Test that timeout is enforced"""
    executor = SandboxExecutor(timeout=5)  # 5 second timeout
    
    code = """
import time
print("Starting long computation...")
time.sleep(10)  # Sleep longer than timeout
print("This should never print")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.TIMEOUT
    assert result.execution_time >= 5  # At least timeout duration
    assert result.execution_time < 15  # Not too much longer
    
    executor.close()


@pytest.mark.asyncio
async def test_memory_limit():
    """Test memory limit (soft test - just verify execution)"""
    executor = SandboxExecutor(memory_limit="256m")
    
    code = """
import numpy as np

# Allocate some memory (but not too much)
arr = np.zeros((1000, 1000))  # ~8MB
print(f"Array shape: {arr.shape}")
print(f"Memory usage: {arr.nbytes / 1024 / 1024:.2f} MB")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert result.resource_usage is not None
    # Memory usage should be tracked
    assert "memory_usage_mb" in result.resource_usage
    
    executor.close()


@pytest.mark.asyncio
async def test_cpu_limit():
    """Test CPU limit (soft test - just verify execution)"""
    executor = SandboxExecutor(cpu_limit=0.5)  # Half a core
    
    code = """
import time

# CPU-intensive task
start = time.time()
result = sum(i ** 2 for i in range(1000000))
duration = time.time() - start

print(f"Computed: {result}")
print(f"Duration: {duration:.3f}s")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert result.resource_usage is not None
    # CPU usage should be tracked
    assert "cpu_percent" in result.resource_usage
    
    executor.close()


# ==============================================================================
# TEST: ERROR HANDLING
# ==============================================================================

@pytest.mark.asyncio
async def test_syntax_error_handling(executor):
    """Test handling of syntax errors"""
    code = """
print("Missing closing quote)
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("syntax" in str(v).lower() for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_runtime_error_handling(executor):
    """Test handling of runtime errors"""
    code = """
# This will cause a ZeroDivisionError
result = 1 / 0
"""
    
    result = await executor.execute(code)
    
    # Should pass validation but fail at runtime
    assert result.status == ExecutionStatus.FAILED
    assert result.exit_code != 0
    assert "ZeroDivisionError" in result.stderr


@pytest.mark.asyncio
async def test_import_error_handling(executor):
    """Test handling of import errors"""
    code = """
import nonexistent_module_xyz
"""
    
    result = await executor.execute(code)
    
    # Should pass validation (unknown module warning) but fail at runtime
    assert result.status in [ExecutionStatus.FAILED, ExecutionStatus.VALIDATION_FAILED]
    if result.status == ExecutionStatus.FAILED:
        assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr


# ==============================================================================
# TEST: DOCKER ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_network_isolation(executor):
    """Test that network access is blocked (via validation)"""
    code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('google.com', 80))
"""
    
    result = await executor.execute(code)
    
    # Should be blocked by validation
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    assert any("socket" in str(v) for v in result.validation_result.violations)


@pytest.mark.asyncio
async def test_filesystem_isolation():
    """Test that filesystem is isolated (read-only)"""
    # Note: This test verifies validation blocks file I/O
    # Actual Docker read-only enforcement is tested at Docker level
    executor = SandboxExecutor()
    
    code = """
# Try to write to filesystem
with open('/tmp/test.txt', 'w') as f:
    f.write('test')
"""
    
    result = await executor.execute(code)
    
    # Should be blocked by validation
    assert result.status == ExecutionStatus.VALIDATION_FAILED
    
    executor.close()


# ==============================================================================
# TEST: CONVENIENCE FUNCTIONS
# ==============================================================================

@pytest.mark.asyncio
async def test_execute_strategy_convenience():
    """Test convenience function execute_strategy()"""
    code = """
print("Using convenience function")
result = 42
print(f"The answer: {result}")
"""
    
    result = await execute_strategy(code, timeout=30)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "The answer: 42" in result.stdout


# ==============================================================================
# TEST: EDGE CASES
# ==============================================================================

@pytest.mark.asyncio
async def test_empty_code(executor):
    """Test execution with empty code"""
    code = ""
    
    result = await executor.execute(code)
    
    # Should succeed (empty script is valid Python)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_whitespace_only_code(executor):
    """Test execution with whitespace-only code"""
    code = "   \n\n\t\n   "
    
    result = await executor.execute(code)
    
    # Should succeed (whitespace is valid Python)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_very_long_output(executor):
    """Test handling of very long output"""
    code = """
# Generate lots of output
for i in range(1000):
    print(f"Line {i}: " + "x" * 100)
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert len(result.stdout) > 100000  # Should have lots of output


@pytest.mark.asyncio
async def test_unicode_handling(executor):
    """Test Unicode string handling"""
    code = """
print("Hello 世界! 🚀")
print("Привет мир!")
print("مرحبا بالعالم")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert "世界" in result.stdout
    assert "Привет" in result.stdout


# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_multiple_sequential_executions():
    """Test multiple sequential executions"""
    executor = SandboxExecutor()
    
    code = "print('Test execution')"
    
    results = []
    for i in range(5):
        result = await executor.execute(code)
        results.append(result)
    
    # All should succeed
    assert all(r.status == ExecutionStatus.SUCCESS for r in results)
    assert all(r.exit_code == 0 for r in results)
    
    executor.close()


@pytest.mark.asyncio
async def test_concurrent_executions():
    """Test concurrent executions (with separate executors)"""
    code = "import time; time.sleep(1); print('Done')"
    
    # Run 3 concurrent executions
    tasks = [execute_strategy(code, timeout=10) for _ in range(3)]
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(r.status == ExecutionStatus.SUCCESS for r in results)
    assert all(r.exit_code == 0 for r in results)


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
