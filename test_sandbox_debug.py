"""Quick test to debug sandbox executor"""
import asyncio
from backend.services.sandbox_executor import SandboxExecutor

async def main():
    code = """
import numpy as np

data = np.array([1, 2, 3])
result = np.mean(data)
print(f"Result: {result}")
"""
    
    executor = SandboxExecutor()
    result = await executor.execute(code, timeout=30)
    
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"Execution time: {result.execution_time:.2f}s")
    print("=" * 60)
    print("STDOUT:")
    print(result.stdout)
    print("=" * 60)
    print("STDERR:")
    print(result.stderr)
    print("=" * 60)
    print(f"Error: {result.error}")
    print("=" * 60)
    
    executor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
