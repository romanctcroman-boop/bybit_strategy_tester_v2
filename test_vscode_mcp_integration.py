"""
🧪 Test VS Code ↔ MCP Server Integration
Тестирование взаимодействия через CLI (как из VS Code tasks)
"""

import asyncio
import sys
from pathlib import Path

# Добавляем mcp-server в путь
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from vscode_integration import call_mcp_router, quick_task, pipeline_task
from vscode_integration import workflow_code_review, workflow_strategy_development


async def test_simple_query():
    """Test 1: Простой запрос к Sonar Pro"""
    print("\n" + "="*70)
    print("🧪 TEST 1: Simple Query (Sonar Pro)")
    print("="*70)
    
    result = await quick_task(
        task_type="explain",
        prompt="What is the MCP (Model Context Protocol)?",
        context={}
    )
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Agent: {result['agent']}")
    print(f"✅ Result:\n{result['result'][:500]}...")


async def test_code_generation():
    """Test 2: Генерация кода через DeepSeek"""
    print("\n" + "="*70)
    print("🧪 TEST 2: Code Generation (DeepSeek)")
    print("="*70)
    
    result = await quick_task(
        task_type="code-generation",
        prompt="Create a Python function to validate email address using regex",
        context={"language": "python"}
    )
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Agent: {result['agent']}")
    print(f"✅ Generated Code:\n{result['result'][:500]}...")


async def test_workflow():
    """Test 3: Workflow - Code Review"""
    print("\n" + "="*70)
    print("🧪 TEST 3: Workflow - Code Review (Multi-Agent)")
    print("="*70)
    
    # Создаем тестовый файл
    test_file = Path(__file__).parent / "mcp-server" / "multi_agent_router.py"
    
    result = await workflow_code_review(str(test_file))
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Steps Completed: {len(result.get('results', []))}")
    
    for i, step in enumerate(result.get('results', []), 1):
        print(f"\n  Step {i}: {step.get('step_name')}")
        print(f"    Agent: {step.get('agent')}")
        print(f"    Status: {step.get('status')}")
        if step.get('result'):
            preview = str(step.get('result'))[:200]
            print(f"    Result: {preview}...")


async def test_strategy_development():
    """Test 4: Strategy Development Workflow"""
    print("\n" + "="*70)
    print("🧪 TEST 4: Strategy Development Workflow")
    print("="*70)
    
    result = await workflow_strategy_development(
        "RSI mean reversion strategy with dynamic thresholds based on volatility"
    )
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Steps Completed: {len(result.get('results', []))}")
    
    for i, step in enumerate(result.get('results', []), 1):
        print(f"\n  Step {i}: {step.get('step_name')}")
        print(f"    Agent: {step.get('agent')}")
        print(f"    Status: {step.get('status')}")
        if step.get('result'):
            preview = str(step.get('result'))[:200]
            print(f"    Result: {preview}...")


async def test_mcp_direct():
    """Test 5: Direct MCP Router Call"""
    print("\n" + "="*70)
    print("🧪 TEST 5: Direct MCP Router (Perplexity sonar-pro)")
    print("="*70)
    
    result = await call_mcp_router(
        task_type="research",
        data={
            "query": "Latest cryptocurrency market trends for BTC and ETH",
            "context": {}
        }
    )
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Agent: {result['agent']}")
    print(f"✅ Research:\n{result['result'][:500]}...")


async def main():
    """Run all integration tests"""
    print("🚀 VS Code ↔ MCP Server Integration Tests")
    print("="*70)
    print("Testing Copilot → Script → MCP → Perplexity AI (sonar-pro)")
    print("="*70)
    
    tests = [
        ("Simple Query (Sonar Pro)", test_simple_query),
        ("Code Generation (DeepSeek)", test_code_generation),
        ("MCP Direct Call", test_mcp_direct),
        ("Code Review Workflow", test_workflow),
        ("Strategy Development", test_strategy_development),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            await test_func()
            results.append((test_name, True))
            print(f"\n✅ {test_name} - PASSED")
        except Exception as e:
            results.append((test_name, False))
            print(f"\n❌ {test_name} - FAILED: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 INTEGRATION TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All integration tests passed!")
        print("\n✅ VS Code ↔ MCP ↔ Perplexity AI - FULLY OPERATIONAL")
    else:
        print("\n⚠️  Some tests failed. Check MCP server logs.")


if __name__ == "__main__":
    asyncio.run(main())
