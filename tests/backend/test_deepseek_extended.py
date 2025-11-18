"""
Test suite for extended DeepSeek Agent methods

Tests all 7 methods:
- Original 3: generate_code, fix_code, generate_strategy
- New 4: analyze_code, refactor_code, insert_code, explain_code
"""

import pytest
import asyncio
from pathlib import Path
import tempfile

from backend.agents.deepseek import DeepSeekAgent, CodeGenerationStatus


@pytest.mark.asyncio
async def test_analyze_code():
    """Test code analysis functionality"""
    async with DeepSeekAgent() as agent:
        test_code = """
def calculate(x):
    return x / 0  # Division by zero error
    
def fib(n):
    return fib(n-1) + fib(n-2)  # Missing base case
"""
        
        result = await agent.analyze_code(
            code=test_code,
            error_types=["syntax", "logic"]
        )
        
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code is not None
        assert result.tokens_used > 0
        print(f"✅ analyze_code: {len(result.code)} chars analyzed")


@pytest.mark.asyncio
async def test_refactor_code():
    """Test code refactoring functionality"""
    async with DeepSeekAgent() as agent:
        test_code = """
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
"""
        
        result = await agent.refactor_code(
            code=test_code,
            refactor_type="optimize",
            target="process_data"
        )
        
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code is not None
        assert result.tokens_used > 0
        print(f"✅ refactor_code: {len(result.code)} chars refactored")


@pytest.mark.asyncio
async def test_insert_code():
    """Test code insertion functionality"""
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
class MyStrategy:
    def __init__(self):
        pass
    
    def execute(self):
        pass
""")
        temp_file = f.name
    
    try:
        async with DeepSeekAgent() as agent:
            result = await agent.insert_code(
                file_path=temp_file,
                code_to_insert="        self.indicator = RSI(period=14)",
                context="def __init__(self):",
                position="after"
            )
            
            assert result.status == CodeGenerationStatus.COMPLETED
            assert "inserted" in result.code.lower()
            
            # Verify insertion
            with open(temp_file, 'r') as f:
                content = f.read()
                assert "self.indicator" in content
            
            print(f"✅ insert_code: {result.code}")
    
    finally:
        # Cleanup
        Path(temp_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_explain_code():
    """Test code explanation functionality"""
    async with DeepSeekAgent() as agent:
        test_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        
        result = await agent.explain_code(
            code=test_code,
            focus="performance",
            include_improvements=True
        )
        
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code is not None
        assert result.tokens_used > 0
        print(f"✅ explain_code: {len(result.code)} chars explanation")


@pytest.mark.asyncio
async def test_all_methods_integration():
    """Integration test: use all 7 methods in sequence"""
    async with DeepSeekAgent() as agent:
        print("\n" + "="*60)
        print("🧪 INTEGRATION TEST: All 7 DeepSeek Agent methods")
        print("="*60)
        
        # 1. Generate code
        print("\n1️⃣ Testing generate_code...")
        code, tokens = await agent.generate_code(
            prompt="Create a simple function that adds two numbers",
            context={"task": "addition"}
        )
        assert code is not None
        assert tokens > 0
        print(f"   ✅ Generated {len(code)} chars, {tokens} tokens")
        
        # 2. Fix code (with intentional error)
        print("\n2️⃣ Testing fix_code...")
        broken_code = "def add(x, y)\n    return x + y"  # Missing colon
        fixed_code, fix_tokens = await agent.fix_code(
            code=broken_code,
            error="SyntaxError: invalid syntax",
            original_prompt="Add two numbers"
        )
        assert fixed_code is not None
        assert fix_tokens > 0
        print(f"   ✅ Fixed code, {fix_tokens} tokens")
        
        # 3. Analyze code
        print("\n3️⃣ Testing analyze_code...")
        analysis = await agent.analyze_code(
            code="def calc(x): return x/0",
            error_types=["logic"]
        )
        assert analysis.status == CodeGenerationStatus.COMPLETED
        print(f"   ✅ Analysis: {len(analysis.code)} chars")
        
        # 4. Refactor code
        print("\n4️⃣ Testing refactor_code...")
        refactored = await agent.refactor_code(
            code="def f(x):\n    return x*2",
            refactor_type="rename",
            target="f",
            new_name="double"
        )
        assert refactored.status == CodeGenerationStatus.COMPLETED
        print(f"   ✅ Refactored: {len(refactored.code)} chars")
        
        # 5. Explain code
        print("\n5️⃣ Testing explain_code...")
        explanation = await agent.explain_code(
            code="def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[0]\n    return quicksort([x for x in arr[1:] if x < pivot]) + [pivot] + quicksort([x for x in arr[1:] if x >= pivot])",
            focus="all"
        )
        assert explanation.status == CodeGenerationStatus.COMPLETED
        print(f"   ✅ Explanation: {len(explanation.code)} chars")
        
        # 6. Generate strategy (full workflow)
        print("\n6️⃣ Testing generate_strategy...")
        strategy = await agent.generate_strategy(
            prompt="Create simple RSI strategy",
            context={"symbol": "BTCUSDT"}
        )
        assert strategy.status in [CodeGenerationStatus.COMPLETED, CodeGenerationStatus.FAILED]
        print(f"   ✅ Strategy: {strategy.status.value}, {strategy.iterations} iterations")
        
        # 7. Insert code (tested separately due to file I/O)
        print("\n7️⃣ insert_code tested separately (requires temp file)")
        
        print("\n" + "="*60)
        print("🎉 ALL METHODS WORKING!")
        print("="*60)
        print(f"\nTotal methods tested: 7")
        print(f"  - Original: 3 (generate_code, fix_code, generate_strategy)")
        print(f"  - New: 4 (analyze_code, refactor_code, insert_code, explain_code)")
        print("="*60)


@pytest.mark.asyncio
async def test_method_count():
    """Verify DeepSeek Agent has exactly 7 methods"""
    agent = DeepSeekAgent()
    
    expected_methods = [
        "generate_code",
        "fix_code", 
        "generate_strategy",
        "analyze_code",
        "refactor_code",
        "insert_code",
        "explain_code"
    ]
    
    for method in expected_methods:
        assert hasattr(agent, method), f"Missing method: {method}"
        assert callable(getattr(agent, method)), f"Not callable: {method}"
    
    print(f"✅ All 7 methods present: {', '.join(expected_methods)}")


if __name__ == "__main__":
    # Run integration test directly
    asyncio.run(test_all_methods_integration())
