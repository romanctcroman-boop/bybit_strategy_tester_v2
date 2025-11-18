"""
Test script для проверки Sandbox Executor
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.sandbox_executor import SandboxExecutor, execute_code_in_sandbox
from backend.core.code_validator import validate_code


# =============================================================================
# Test Cases
# =============================================================================

# Test 1: Simple safe code
SAFE_CODE = """
import numpy as np
import pandas as pd

# Simple calculation
data = np.array([1, 2, 3, 4, 5])
mean_value = np.mean(data)
print(f"Mean: {mean_value}")

# Pandas test
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
print(f"DataFrame shape: {df.shape}")
print("Safe code executed successfully!")
"""

# Test 2: Dangerous code (should be blocked)
DANGEROUS_CODE = """
import os
import subprocess

# Try to access filesystem
files = os.listdir('/')
print(files)

# Try to execute command
subprocess.run(['ls', '-la'])
"""

# Test 3: Network attempt (should be blocked)
NETWORK_CODE = """
import requests

# Try to make HTTP request
response = requests.get('https://google.com')
print(response.status_code)
"""

# Test 4: Eval/exec (should be blocked)
EVAL_CODE = """
code = "print('Hello')"
eval(code)
exec(code)
"""

# Test 5: Infinite loop (should timeout)
TIMEOUT_CODE = """
while True:
    pass
"""


async def test_validation():
    """Test code validator"""
    print("\n" + "="*80)
    print("TEST: Code Validation")
    print("="*80)
    
    test_cases = [
        ("Safe code", SAFE_CODE),
        ("Dangerous code (os)", DANGEROUS_CODE),
        ("Network code", NETWORK_CODE),
        ("Eval/exec code", EVAL_CODE)
    ]
    
    for name, code in test_cases:
        print(f"\n--- {name} ---")
        result = validate_code(code)
        print(f"Valid: {result.is_valid}")
        print(f"Risk Score: {result.risk_score}")
        print(f"Risk Level: {result.risk_level}")
        
        if result.violations:
            print("\nViolations:")
            for v in result.violations[:3]:  # Show first 3
                print(f"  - {v['message']} (line {v.get('lineno', '?')})")
        
        if result.warnings:
            print(f"\nWarnings: {len(result.warnings)}")


async def test_sandbox_execution():
    """Test sandbox executor"""
    print("\n" + "="*80)
    print("TEST: Sandbox Execution")
    print("="*80)
    
    # Test 1: Safe code
    print("\n--- Test 1: Safe Code ---")
    result = await execute_code_in_sandbox(SAFE_CODE, timeout=30)
    print(f"Success: {result.success}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Stdout:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr:\n{result.stderr}")
    
    # Test 2: Dangerous code (should be blocked by validator)
    print("\n--- Test 2: Dangerous Code (should be blocked) ---")
    result = await execute_code_in_sandbox(DANGEROUS_CODE, timeout=30)
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    if result.validation_result:
        print(f"Risk Score: {result.validation_result.risk_score}")
        print(f"Violations: {len(result.validation_result.violations)}")
    
    # Test 3: Code with timeout
    print("\n--- Test 3: Timeout Test (will take 10 seconds) ---")
    result = await execute_code_in_sandbox(TIMEOUT_CODE, timeout=10)
    print(f"Success: {result.success}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Error: {result.error}")


async def test_resource_limits():
    """Test resource usage monitoring"""
    print("\n" + "="*80)
    print("TEST: Resource Limits")
    print("="*80)
    
    # Memory-intensive code
    memory_code = """
import numpy as np

# Allocate 500MB array
data = np.zeros((500 * 1024 * 1024 // 8,), dtype=np.float64)
print(f"Allocated {data.nbytes / (1024**2):.0f} MB")
print("Memory test completed")
"""
    
    print("\n--- Memory Usage Test ---")
    result = await execute_code_in_sandbox(memory_code, timeout=30)
    print(f"Success: {result.success}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    
    if result.resource_usage:
        print("\nResource Usage:")
        print(f"  Memory: {result.resource_usage.get('memory_usage_mb', 0):.2f} MB")
        print(f"  Memory %: {result.resource_usage.get('memory_percent', 0):.2f}%")
        print(f"  CPU %: {result.resource_usage.get('cpu_percent', 0):.2f}%")
    
    print(f"\nStdout:\n{result.stdout}")


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("SANDBOX EXECUTOR TEST SUITE")
    print("="*80)
    
    # Test 1: Validation only
    await test_validation()
    
    # Test 2: Sandbox execution
    await test_sandbox_execution()
    
    # Test 3: Resource limits
    await test_resource_limits()
    
    print("\n" + "="*80)
    print("TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
