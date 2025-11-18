"""
Tests for Saga Pattern Orchestrator - Week 3 Day 2-3
====================================================

Test Coverage:
- ✅ Basic saga execution (all steps succeed)
- ✅ Saga failure and compensation (rollback)
- ✅ Step retry logic
- ✅ Step timeout handling
- ✅ Checkpoint save/restore
- ✅ Compensation in reverse order
- ✅ Partial failure (some steps succeed)
- ✅ Context propagation between steps
- ✅ Metrics tracking
- ✅ Concurrent sagas
"""

import asyncio
import pytest
from typing import List

from backend.orchestrator.saga import (
    SagaOrchestrator,
    SagaConfig,
    SagaStep,
    SagaState,
    StepStatus
)


@pytest.fixture
def saga_config():
    """Saga configuration for tests"""
    return SagaConfig(
        redis_url="redis://localhost:6379/15",
        checkpoint_prefix="test_saga",
        checkpoint_ttl=3600
    )


@pytest.mark.asyncio
async def test_basic_saga_success(saga_config):
    """Test 1: All steps succeed"""
    executed_steps = []
    
    async def step1_action(context):
        executed_steps.append("step1")
        return {"result1": "data1"}
    
    async def step2_action(context):
        executed_steps.append("step2")
        assert context["result1"] == "data1"  # Context from step1
        return {"result2": "data2"}
    
    async def step3_action(context):
        executed_steps.append("step3")
        assert context["result2"] == "data2"  # Context from step2
        return {"result3": "data3"}
    
    steps = [
        SagaStep("step1", step1_action),
        SagaStep("step2", step2_action),
        SagaStep("step3", step3_action)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute(context={"initial": "value"})
    
    await orchestrator.disconnect()
    
    assert result["status"] == "completed"
    assert len(executed_steps) == 3
    assert executed_steps == ["step1", "step2", "step3"]
    assert orchestrator.state == SagaState.COMPLETED


@pytest.mark.asyncio
async def test_saga_failure_and_compensation(saga_config):
    """Test 2: Step fails, compensation runs in reverse order"""
    executed_steps = []
    compensated_steps = []
    
    async def step1_action(context):
        executed_steps.append("step1")
        return {"user_id": 123}
    
    async def step1_compensation(result):
        compensated_steps.append("step1_compensate")
    
    async def step2_action(context):
        executed_steps.append("step2")
        return {"payment_id": 456}
    
    async def step2_compensation(result):
        compensated_steps.append("step2_compensate")
    
    async def step3_action(context):
        executed_steps.append("step3")
        raise Exception("Step 3 failed!")
    
    steps = [
        SagaStep("step1", step1_action, step1_compensation),
        SagaStep("step2", step2_action, step2_compensation),
        SagaStep("step3", step3_action)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute()
    
    await orchestrator.disconnect()
    
    assert result["status"] == "failed"
    assert "Step 3 failed!" in result["error"]
    # Step3 will be retried 3 times (max_retries=3 by default)
    assert "step1" in executed_steps and "step2" in executed_steps
    assert executed_steps.count("step3") == 4  # 1 initial + 3 retries
    # Compensation in REVERSE order
    assert compensated_steps == ["step2_compensate", "step1_compensate"]
    assert orchestrator.state == SagaState.FAILED


@pytest.mark.asyncio
async def test_step_retry_logic(saga_config):
    """Test 3: Step fails first 2 times, succeeds on 3rd"""
    attempts = {"count": 0}
    
    async def flaky_action(context):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise Exception(f"Attempt {attempts['count']} failed")
        return {"success": True}
    
    steps = [SagaStep("flaky_step", flaky_action, max_retries=3)]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute()
    
    await orchestrator.disconnect()
    
    assert result["status"] == "completed"
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_step_timeout(saga_config):
    """Test 4: Step times out"""
    async def slow_action(context):
        await asyncio.sleep(10)  # Too slow
        return {}
    
    steps = [SagaStep("slow_step", slow_action, timeout=1)]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute()
    
    await orchestrator.disconnect()
    
    assert result["status"] == "failed"
    assert "Timeout" in result["error"] or "Max retries" in result["error"]


@pytest.mark.asyncio
async def test_checkpoint_save_restore(saga_config):
    """Test 5: Checkpoint save and restore"""
    async def step1_action(context):
        return {"step1_done": True}
    
    steps = [SagaStep("step1", step1_action)]
    
    orchestrator = SagaOrchestrator(steps, saga_config, saga_id="test-saga-123")
    await orchestrator.connect()
    
    # Execute and save checkpoint
    result = await orchestrator.execute()
    assert result["status"] == "completed"
    
    # Create new orchestrator and restore
    new_orchestrator = SagaOrchestrator(steps, saga_config)
    await new_orchestrator.connect()
    
    restored = await new_orchestrator.restore_from_checkpoint("test-saga-123")
    
    await orchestrator.disconnect()
    await new_orchestrator.disconnect()
    
    assert restored is True
    assert new_orchestrator.saga_id == "test-saga-123"
    assert new_orchestrator.state == SagaState.COMPLETED


@pytest.mark.asyncio
async def test_partial_failure(saga_config):
    """Test 6: Steps 1-2 succeed, step 3 fails"""
    executed_steps = []
    compensated_steps = []
    
    async def step1_action(context):
        executed_steps.append(1)
        return {"data": "step1"}
    
    async def step1_compensation(result):
        compensated_steps.append(1)
    
    async def step2_action(context):
        executed_steps.append(2)
        return {"data": "step2"}
    
    async def step2_compensation(result):
        compensated_steps.append(2)
    
    async def step3_action(context):
        executed_steps.append(3)
        raise Exception("Failure at step 3")
    
    async def step3_compensation(result):
        compensated_steps.append(3)
    
    steps = [
        SagaStep("step1", step1_action, step1_compensation),
        SagaStep("step2", step2_action, step2_compensation),
        SagaStep("step3", step3_action, step3_compensation)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute()
    
    await orchestrator.disconnect()
    
    assert result["status"] == "failed"
    # Step3 retries (1 initial + 3 retries = 4 attempts)
    assert executed_steps.count(1) == 1
    assert executed_steps.count(2) == 1
    assert executed_steps.count(3) == 4  # 1 initial + 3 retries
    assert compensated_steps == [2, 1]  # Reverse order, excluding step3 (didn't complete)


@pytest.mark.asyncio
async def test_context_propagation(saga_config):
    """Test 7: Context data flows between steps"""
    async def step1_action(context):
        assert context["initial"] == "value"
        return {"from_step1": "data1"}
    
    async def step2_action(context):
        assert context["from_step1"] == "data1"
        return {"from_step2": "data2"}
    
    async def step3_action(context):
        assert context["from_step1"] == "data1"
        assert context["from_step2"] == "data2"
        return {"final": "result"}
    
    steps = [
        SagaStep("step1", step1_action),
        SagaStep("step2", step2_action),
        SagaStep("step3", step3_action)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute(context={"initial": "value"})
    
    await orchestrator.disconnect()
    
    assert result["status"] == "completed"
    assert orchestrator.context["final"] == "result"


@pytest.mark.asyncio
async def test_metrics_tracking(saga_config):
    """Test 8: Metrics are tracked correctly"""
    async def step_action(context):
        return {}
    
    steps = [SagaStep("step", step_action)]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    await orchestrator.execute()
    
    metrics = orchestrator.get_metrics()
    
    await orchestrator.disconnect()
    
    assert metrics["sagas_started"] == 1
    assert metrics["sagas_completed"] == 1
    assert metrics["steps_executed"] == 1


@pytest.mark.asyncio
async def test_saga_status(saga_config):
    """Test 9: Saga status reporting"""
    async def step_action(context):
        return {}
    
    steps = [
        SagaStep("step1", step_action),
        SagaStep("step2", step_action)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    # Get status before execution
    status_before = await orchestrator.get_saga_status()
    assert status_before["state"] == "idle"
    
    await orchestrator.execute()
    
    # Get status after execution
    status_after = await orchestrator.get_saga_status()
    
    await orchestrator.disconnect()
    
    assert status_after["state"] == "completed"
    assert status_after["total_steps"] == 2
    assert status_after["completed_steps"] == 2


@pytest.mark.asyncio
async def test_compensation_failure_doesnt_stop_rollback(saga_config):
    """Test 10: Failed compensation doesn't stop other compensations"""
    compensated_steps = []
    
    async def step1_action(context):
        return {}
    
    async def step1_compensation(result):
        compensated_steps.append(1)
    
    async def step2_action(context):
        return {}
    
    async def step2_compensation(result):
        # This compensation fails
        raise Exception("Compensation failed!")
    
    async def step3_action(context):
        raise Exception("Trigger rollback")
    
    steps = [
        SagaStep("step1", step1_action, step1_compensation),
        SagaStep("step2", step2_action, step2_compensation),
        SagaStep("step3", step3_action)
    ]
    
    orchestrator = SagaOrchestrator(steps, saga_config)
    await orchestrator.connect()
    
    result = await orchestrator.execute()
    
    await orchestrator.disconnect()
    
    assert result["status"] == "failed"
    # Step1 compensation should still run even though step2 compensation failed
    assert 1 in compensated_steps


@pytest.mark.asyncio
async def test_concurrent_sagas(saga_config):
    """Test 11: Multiple sagas can run concurrently"""
    async def step_action(context):
        await asyncio.sleep(0.1)
        return {"saga_id": context["saga_id"]}
    
    async def run_saga(saga_id: str):
        steps = [SagaStep("step", step_action)]
        orchestrator = SagaOrchestrator(steps, saga_config, saga_id=saga_id)
        await orchestrator.connect()
        result = await orchestrator.execute(context={"saga_id": saga_id})
        await orchestrator.disconnect()
        return result
    
    # Run 3 sagas concurrently
    results = await asyncio.gather(
        run_saga("saga-1"),
        run_saga("saga-2"),
        run_saga("saga-3")
    )
    
    assert len(results) == 3
    assert all(r["status"] == "completed" for r in results)
    assert results[0]["saga_id"] == "saga-1"
    assert results[1]["saga_id"] == "saga-2"
    assert results[2]["saga_id"] == "saga-3"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
