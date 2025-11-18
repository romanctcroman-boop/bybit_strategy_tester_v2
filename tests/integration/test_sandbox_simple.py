"""
Simplified Sandbox Integration Test
Quick test for Docker sandbox execution
"""

import asyncio
import pytest
from backend.services.sandbox_executor import SandboxExecutor


@pytest.mark.asyncio
async def test_sandbox_basic():
    """Test basic sandbox execution"""
    executor = SandboxExecutor()
    
    code = 'print("Hello from sandbox!")'
    result = await executor.execute(code, timeout=30)
    
    print(f"\n✅ Success: {result.success}")
    print(f"✅ Exit code: {result.exit_code}")
    print(f"✅ Output: {result.stdout}")
    print(f"✅ Execution time: {result.execution_time:.2f}s")
    
    assert result.success == True
    assert result.exit_code == 0
    assert "Hello from sandbox!" in result.stdout


@pytest.mark.asyncio
async def test_sandbox_pandas():
    """Test pandas in sandbox"""
    executor = SandboxExecutor()
    
    code = """
import pandas as pd
import numpy as np

df = pd.DataFrame({'price': [100, 102, 101, 103]})
sma = df['price'].rolling(window=2).mean()
print(f"SMA: {sma.tolist()}")
"""
    
    result = await executor.execute(code, timeout=60)
    
    print(f"\n✅ Pandas test success: {result.success}")
    print(f"✅ Output: {result.stdout}")
    
    assert result.success == True
    assert "SMA:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
