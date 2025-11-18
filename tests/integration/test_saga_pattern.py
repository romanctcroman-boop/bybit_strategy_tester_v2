"""
Integration Tests for Saga Pattern Orchestrator
================================================

Tests:
1. Basic saga success (all steps complete)
2. Saga failure and compensation
3. Step retry logic
4. Step timeout handling
5. Checkpoint save/restore
6. Partial failure compensation
7. Context propagation between steps
8. Metrics tracking
9. Saga status retrieval
10. Compensation failure doesn't stop rollback
11. Concurrent sagas execution

Based on WEEK_3_DAY_1-3_COMPLETE.md specification.
"""

import pytest
import asyncio
import time
from typing import Dict, Any

from backend.services.saga_orchestrator import (
    SagaOrchestrator,
    SagaStep,
    SagaConfig,
    SagaState,
    StepStatus,
)


# ============================================================================
# MOCK ACTIONS AND COMPENSATIONS
# ============================================================================

# Track compensation calls for testing
compensation_calls = []


async def create_backtest_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock: Create backtest"""
    await asyncio.sleep(0.1)
    return {"backtest_id": "bt_123"}


async def delete_backtest_compensation(context: Dict[str, Any]):
    """Mock: Delete backtest"""
    compensation_calls.append("delete_backtest")
    await asyncio.sleep(0.1)


async def run_strategy_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock: Run strategy"""
    await asyncio.sleep(0.1)
    return {"result": "success", "profit": 1500}


async def cleanup_strategy_compensation(context: Dict[str, Any]):
    """Mock: Cleanup strategy"""
    compensation_calls.append("cleanup_strategy")
    await asyncio.sleep(0.1)


async def save_results_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock: Save results"""
    await asyncio.sleep(0.1)
    return {"saved": True}


async def delete_results_compensation(context: Dict[str, Any]):
    """Mock: Delete results"""
    compensation_calls.append("delete_results")
    await asyncio.sleep(0.1)


async def failing_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock: Action that always fails"""
    await asyncio.sleep(0.1)
    raise Exception("Intentional failure for testing")


async def timeout_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock: Action that times out"""
    await asyncio.sleep(10)  # Long enough to timeout
    return {}


async def failing_compensation(context: Dict[str, Any]):
    """Mock: Compensation that fails"""
    compensation_calls.append("failing_compensation")
    raise Exception("Compensation failed")


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def config():
    """Saga config with in-memory storage"""
    return SagaConfig()


@pytest.fixture
def basic_steps():
    """Basic saga steps for testing"""
    global compensation_calls
    compensation_calls = []  # Reset
    
    return [
        SagaStep(
            name="create_backtest",
            action=create_backtest_action,
            compensation=delete_backtest_compensation,
        ),
        SagaStep(
            name="run_strategy",
            action=run_strategy_action,
            compensation=cleanup_strategy_compensation,
        ),
        SagaStep(
            name="save_results",
            action=save_results_action,
            compensation=delete_results_compensation,
        ),
    ]


# ============================================================================
# TEST 1: BASIC SAGA SUCCESS
# ============================================================================

@pytest.mark.asyncio
async def test_basic_saga_success(basic_steps, config):
    """Test successful execution of all saga steps"""
    orchestrator = SagaOrchestrator(basic_steps, config)
    
    result = await orchestrator.execute(context={"user_id": 123})
    
    # Check result
    assert result["status"] == "completed"
    assert result["state"] == SagaState.COMPLETED.value
    assert len(result["completed_steps"]) == 3
    assert result["completed_steps"] == ["create_backtest", "run_strategy", "save_results"]
    assert len(result["compensated_steps"]) == 0
    assert result["error"] is None
    
    # Check context propagation
    assert result["context"]["backtest_id"] == "bt_123"
    assert result["context"]["result"] == "success"
    assert result["context"]["profit"] == 1500
    assert result["context"]["saved"] is True
    
    # Check metrics
    assert result["metrics"]["steps_executed"] == 3
    assert result["metrics"]["steps_failed"] == 0
    assert result["metrics"]["steps_compensated"] == 0
    
    print(f"✅ Test 1 PASSED: Saga completed successfully")


# ============================================================================
# TEST 2: SAGA FAILURE AND COMPENSATION
# ============================================================================

@pytest.mark.asyncio
async def test_saga_failure_and_compensation(config):
    """Test saga compensation when a step fails"""
    global compensation_calls
    compensation_calls = []
    
    steps = [
        SagaStep(
            name="step1",
            action=create_backtest_action,
            compensation=delete_backtest_compensation,
        ),
        SagaStep(
            name="step2",
            action=run_strategy_action,
            compensation=cleanup_strategy_compensation,
        ),
        SagaStep(
            name="failing_step",
            action=failing_action,
            compensation=delete_results_compensation,
            max_retries=1,  # Fail quickly
        ),
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    result = await orchestrator.execute()
    
    # Check result
    assert result["status"] == "failed"
    assert result["state"] == SagaState.FAILED.value
    assert len(result["completed_steps"]) == 2  # Only first 2 steps completed
    assert "failed" in result["error"].lower()  # Error message contains "failed"
    
    # Check compensation (reverse order)
    assert len(result["compensated_steps"]) == 2
    assert result["compensated_steps"] == ["step2", "step1"]
    
    # Verify compensation was called
    assert "cleanup_strategy" in compensation_calls
    assert "delete_backtest" in compensation_calls
    
    print(f"✅ Test 2 PASSED: Saga compensated after failure")


# ============================================================================
# TEST 3: STEP RETRY LOGIC
# ============================================================================

@pytest.mark.asyncio
async def test_step_retry_logic(config):
    """Test step retry mechanism"""
    retry_count = 0
    
    async def flaky_action(context: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal retry_count
        retry_count += 1
        
        if retry_count < 3:
            raise Exception(f"Attempt {retry_count} failed")
        
        return {"success": True}
    
    steps = [
        SagaStep(
            name="flaky_step",
            action=flaky_action,
            max_retries=3,
            timeout=5,
        ),
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    result = await orchestrator.execute()
    
    # Should succeed after 3 attempts
    assert result["status"] == "completed"
    assert retry_count == 3
    assert result["metrics"]["steps_retried"] == 2  # 2 retries after initial attempt
    
    print(f"✅ Test 3 PASSED: Step retry logic works (succeeded after {retry_count} attempts)")


# ============================================================================
# TEST 4: STEP TIMEOUT
# ============================================================================

@pytest.mark.asyncio
async def test_step_timeout(config):
    """Test step timeout enforcement"""
    steps = [
        SagaStep(
            name="timeout_step",
            action=timeout_action,
            timeout=1,  # 1 second timeout
            max_retries=1,
        ),
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    start_time = time.time()
    result = await orchestrator.execute()
    duration = time.time() - start_time
    
    # Should fail due to timeout
    assert result["status"] == "failed"
    assert duration < 5, "Should timeout quickly (not wait for full 10s sleep)"
    assert result["metrics"]["steps_failed"] == 1
    
    print(f"✅ Test 4 PASSED: Step timeout enforced ({duration:.2f}s)")


# ============================================================================
# TEST 5: CHECKPOINT SAVE AND RESTORE
# ============================================================================

@pytest.mark.asyncio
async def test_checkpoint_save_restore(basic_steps, config):
    """Test checkpoint persistence and recovery"""
    # Execute saga
    orchestrator1 = SagaOrchestrator(basic_steps, config)
    result1 = await orchestrator1.execute(context={"user_id": 456})
    
    saga_id = result1["saga_id"]
    
    # Recover from checkpoint
    orchestrator2 = await SagaOrchestrator.recover(saga_id, basic_steps, config)
    
    # Check recovered state
    assert orchestrator2.saga_id == saga_id
    assert orchestrator2.checkpoint.state == SagaState.COMPLETED
    assert len(orchestrator2.checkpoint.completed_steps) == 3
    assert orchestrator2.checkpoint.context["user_id"] == 456
    
    print(f"✅ Test 5 PASSED: Saga recovered from checkpoint")


# ============================================================================
# TEST 6: PARTIAL FAILURE COMPENSATION
# ============================================================================

@pytest.mark.asyncio
async def test_partial_failure(config):
    """Test compensation when middle step fails"""
    global compensation_calls
    compensation_calls = []
    
    steps = [
        SagaStep("step1", create_backtest_action, delete_backtest_compensation),
        SagaStep("step2", run_strategy_action, cleanup_strategy_compensation),
        SagaStep("failing_step", failing_action, None, max_retries=1),
        SagaStep("step4", save_results_action, delete_results_compensation),  # Should never execute
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    result = await orchestrator.execute()
    
    # Only first 2 steps completed
    assert len(result["completed_steps"]) == 2
    assert "step4" not in result["completed_steps"]
    
    # Both should be compensated
    assert len(result["compensated_steps"]) == 2
    assert result["compensated_steps"] == ["step2", "step1"]
    
    print(f"✅ Test 6 PASSED: Partial failure compensated correctly")


# ============================================================================
# TEST 7: CONTEXT PROPAGATION
# ============================================================================

@pytest.mark.asyncio
async def test_context_propagation(config):
    """Test data propagation through saga context"""
    async def step1(context: Dict[str, Any]) -> Dict[str, Any]:
        return {"value_a": context.get("initial", 0) + 10}
    
    async def step2(context: Dict[str, Any]) -> Dict[str, Any]:
        return {"value_b": context["value_a"] * 2}
    
    async def step3(context: Dict[str, Any]) -> Dict[str, Any]:
        return {"final": context["value_b"] + 5}
    
    steps = [
        SagaStep("step1", step1),
        SagaStep("step2", step2),
        SagaStep("step3", step3),
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    result = await orchestrator.execute(context={"initial": 5})
    
    # Check calculations: (5 + 10) * 2 + 5 = 35
    assert result["context"]["value_a"] == 15
    assert result["context"]["value_b"] == 30
    assert result["context"]["final"] == 35
    
    print(f"✅ Test 7 PASSED: Context propagated correctly")


# ============================================================================
# TEST 8: METRICS TRACKING
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_tracking(basic_steps, config):
    """Test saga metrics collection"""
    orchestrator = SagaOrchestrator(basic_steps, config)
    result = await orchestrator.execute()
    
    metrics = result["metrics"]
    
    assert metrics["steps_executed"] == 3
    assert metrics["steps_failed"] == 0
    assert metrics["steps_retried"] == 0
    assert metrics["steps_compensated"] == 0
    assert metrics["total_duration"] > 0
    
    print(f"✅ Test 8 PASSED: Metrics tracked correctly")


# ============================================================================
# TEST 9: SAGA STATUS RETRIEVAL
# ============================================================================

@pytest.mark.asyncio
async def test_saga_status(basic_steps, config):
    """Test saga status retrieval during execution"""
    orchestrator = SagaOrchestrator(basic_steps, config)
    
    # Start execution (don't await yet)
    execution_task = asyncio.create_task(orchestrator.execute())
    
    # Wait a bit for first step to start
    await asyncio.sleep(0.05)
    
    # Get status mid-execution
    status = await orchestrator.get_status()
    
    assert status["saga_id"] == orchestrator.saga_id
    assert status["total_steps"] == 3
    
    # Wait for completion
    result = await execution_task
    
    # Get final status
    final_status = await orchestrator.get_status()
    assert final_status["state"] == SagaState.COMPLETED.value
    assert len(final_status["completed_steps"]) == 3
    
    print(f"✅ Test 9 PASSED: Saga status retrieved correctly")


# ============================================================================
# TEST 10: COMPENSATION FAILURE DOESN'T STOP ROLLBACK
# ============================================================================

@pytest.mark.asyncio
async def test_compensation_failure_doesnt_stop_rollback(config):
    """Test that failed compensation doesn't stop other compensations"""
    global compensation_calls
    compensation_calls = []
    
    steps = [
        SagaStep("step1", create_backtest_action, delete_backtest_compensation),
        SagaStep("step2", run_strategy_action, failing_compensation),  # This will fail
        SagaStep("failing_step", failing_action, None, max_retries=1),
    ]
    
    orchestrator = SagaOrchestrator(steps, config)
    result = await orchestrator.execute()
    
    # Both steps completed before failure
    assert len(result["completed_steps"]) == 2
    
    # step2 compensation fails, but step1 should still be compensated
    assert "delete_backtest" in compensation_calls
    assert "failing_compensation" in compensation_calls
    
    print(f"✅ Test 10 PASSED: Compensation continues despite failures")


# ============================================================================
# TEST 11: CONCURRENT SAGAS
# ============================================================================

@pytest.mark.asyncio
async def test_concurrent_sagas(basic_steps, config):
    """Test multiple sagas running concurrently"""
    num_sagas = 5
    
    # Create and execute multiple sagas concurrently
    tasks = []
    for i in range(num_sagas):
        orchestrator = SagaOrchestrator(basic_steps, config)
        task = orchestrator.execute(context={"saga_number": i})
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert len(results) == num_sagas
    assert all(r["status"] == "completed" for r in results)
    
    # Each should have unique ID
    saga_ids = [r["saga_id"] for r in results]
    assert len(set(saga_ids)) == num_sagas
    
    # Each should have correct context
    for i, result in enumerate(results):
        assert result["context"]["saga_number"] == i
    
    print(f"✅ Test 11 PASSED: {num_sagas} concurrent sagas executed successfully")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
