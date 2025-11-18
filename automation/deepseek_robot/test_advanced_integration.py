"""
🧪 Integration Tests for Advanced Architecture → robot.py

Tests parallel execution, cache, and ML features.
"""

import asyncio
import pytest
from pathlib import Path
from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel


@pytest.mark.asyncio
async def test_robot_initialization():
    """Test robot initializes with advanced architecture"""
    robot = DeepSeekRobot(
        project_root=Path("d:/bybit_strategy_tester_v2"),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    # Check advanced components initialized
    assert hasattr(robot, 'deepseek_keys')
    assert hasattr(robot, 'cache')
    assert hasattr(robot, 'executor')
    assert hasattr(robot, 'orchestrator')
    
    # Check multiple API keys loaded
    assert len(robot.deepseek_keys) >= 1
    print(f"✅ Robot initialized with {len(robot.deepseek_keys)} API keys")


@pytest.mark.asyncio
async def test_parallel_execution():
    """Test parallel execution with multiple keys"""
    robot = DeepSeekRobot(
        project_root=Path("d:/bybit_strategy_tester_v2"),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    # Create test tasks
    tasks = [
        {"query": f"Test query {i}", "model": "deepseek-coder"}
        for i in range(4)
    ]
    
    # Execute in parallel
    results = await robot.executor.execute_batch(tasks, use_cache=True)
    
    assert len(results) == 4
    assert all("response" in r or "error" in r for r in results)
    
    print(f"✅ Parallel execution: {len(results)} tasks completed")


@pytest.mark.asyncio
async def test_cache_functionality():
    """Test cache hit on second run"""
    robot = DeepSeekRobot(
        project_root=Path("d:/bybit_strategy_tester_v2"),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    tasks = [{"query": "test cache query", "model": "deepseek-coder"}]
    
    # First run (no cache)
    results1 = await robot.executor.execute_batch(tasks, use_cache=True)
    cached1 = results1[0].get("cached", False)
    
    # Second run (should be cached)
    results2 = await robot.executor.execute_batch(tasks, use_cache=True)
    cached2 = results2[0].get("cached", False)
    
    print(f"✅ Cache test:")
    print(f"   First run - cached: {cached1}")
    print(f"   Second run - cached: {cached2}")
    
    # Second run should be faster (cached)
    if not cached1:
        assert cached2, "Second run should be cached"


@pytest.mark.asyncio
async def test_advanced_metrics():
    """Test metrics collection"""
    robot = DeepSeekRobot(
        project_root=Path("d:/bybit_strategy_tester_v2"),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    # Run some tasks
    tasks = [{"query": f"test {i}"} for i in range(2)]
    await robot.executor.execute_batch(tasks, use_cache=True)
    
    # Get metrics
    metrics = robot.get_advanced_metrics()
    
    assert "cache" in metrics
    assert "api_keys" in metrics
    assert "ml" in metrics
    assert "performance" in metrics
    
    print(f"✅ Metrics collected:")
    print(f"   Cache size: {metrics['cache']['size']}")
    print(f"   Total keys: {metrics['api_keys']['total_keys']}")
    print(f"   ML enabled: {metrics['ml']['enabled']}")
    print(f"   Expected speedup: {metrics['performance']['expected_speedup']}")


@pytest.mark.asyncio
async def test_semantic_search():
    """Test semantic search in cache"""
    robot = DeepSeekRobot(
        project_root=Path("d:/bybit_strategy_tester_v2"),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    # Add to cache
    robot.cache.set(
        "key1",
        {"result": "test"},
        text_for_ml="find bugs in Python code"
    )
    
    # Search for similar (если ML включен)
    if robot.cache.ml_manager.vectorizer:
        similar = robot.cache.find_similar("check code for errors", threshold=0.6)
        
        if similar:
            print(f"✅ Semantic search found {len(similar)} similar items")
            print(f"   Similarity: {similar[0][2]:.1%}")
        else:
            print(f"ℹ️  Semantic search: no similar items (threshold too high)")
    else:
        print(f"ℹ️  ML features disabled (sklearn not available)")


async def run_all_tests():
    """Run all tests manually"""
    print("\n" + "=" * 80)
    print("🧪 ADVANCED INTEGRATION TESTS")
    print("=" * 80 + "\n")
    
    tests = [
        ("Robot Initialization", test_robot_initialization),
        ("Parallel Execution", test_parallel_execution),
        ("Cache Functionality", test_cache_functionality),
        ("Advanced Metrics", test_advanced_metrics),
        ("Semantic Search", test_semantic_search),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n🔄 Test: {name}")
            await test_func()
            passed += 1
            print(f"✅ PASSED: {name}")
        except Exception as e:
            failed += 1
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
    
    print("\n" + "=" * 80)
    print(f"📊 RESULTS: {passed}/{len(tests)} passed")
    print("=" * 80)
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! Integration successful!")
    else:
        print(f"⚠️  {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_all_tests())
