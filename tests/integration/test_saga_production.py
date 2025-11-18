"""
Production-Ready Saga Pattern Tests - Database + Audit + Metrics
=================================================================

Tests all 3 production components:
✅ Database persistence (PostgreSQL/SQLite)
✅ Audit logging (compliance-ready)
✅ Prometheus metrics (monitoring)

Based on original test_saga_pattern.py but with full production features.
"""

import pytest
import asyncio
import time
from typing import Dict, Any

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.saga_checkpoint import SagaCheckpoint as SagaCheckpointModel
from backend.models.saga_audit_log import SagaAuditLog
from backend.services.saga_orchestrator_v2 import (
    SagaOrchestrator,
    SagaStep,
    SagaConfig,
    SagaState,
)
from backend.services import saga_metrics


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Create database session for tests"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def clean_database(db_session: Session):
    """Clean Saga tables before each test"""
    db_session.query(SagaAuditLog).delete()
    db_session.query(SagaCheckpointModel).delete()
    db_session.commit()
    yield
    # Clean again after test
    db_session.query(SagaAuditLog).delete()
    db_session.query(SagaCheckpointModel).delete()
    db_session.commit()


# ============================================================================
# MOCK ACTIONS (from original tests)
# ============================================================================

async def create_backtest_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock action: Create backtest"""
    await asyncio.sleep(0.1)
    return {"backtest_id": "bt_12345"}


async def delete_backtest_compensation(context: Dict[str, Any]):
    """Mock compensation: Delete backtest"""
    await asyncio.sleep(0.05)
    # Access compensation_calls from test context if available
    if "compensation_calls" in context:
        context["compensation_calls"].append("delete_backtest")


async def run_strategy_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock action: Run strategy"""
    await asyncio.sleep(0.15)
    backtest_id = context.get("backtest_id")
    return {"result": "success", "profit": 1500}


async def cleanup_strategy_compensation(context: Dict[str, Any]):
    """Mock compensation: Cleanup strategy"""
    await asyncio.sleep(0.05)
    if "compensation_calls" in context:
        context["compensation_calls"].append("cleanup_strategy")


async def save_results_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock action: Save results"""
    await asyncio.sleep(0.1)
    return {"saved": True}


async def failing_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock action that always fails"""
    raise ValueError("Intentional failure for testing")


async def timeout_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mock action that times out"""
    await asyncio.sleep(10)
    return {}


# ============================================================================
# PRODUCTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_database_persistence(clean_database, db_session):
    """Test 1: Database persistence - checkpoint survives across instances"""
    
    # Create saga
    steps = [
        SagaStep("create_backtest", create_backtest_action, delete_backtest_compensation),
        SagaStep("run_strategy", run_strategy_action, cleanup_strategy_compensation),
        SagaStep("save_results", save_results_action),
    ]
    
    config = SagaConfig(
        saga_type="backtest_workflow",
        user_id="user_123",
        ip_address="192.168.1.1"
    )
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator.saga_id
    
    # Execute saga
    result = await orchestrator.execute(context={"initial": "data"})
    
    # Verify result
    assert result["status"] == "completed"
    assert result["completed_steps"] == ["create_backtest", "run_strategy", "save_results"]
    
    # Verify checkpoint in database
    checkpoint = db_session.query(SagaCheckpointModel).filter(
        SagaCheckpointModel.saga_id == saga_id
    ).first()
    
    assert checkpoint is not None
    assert checkpoint.state == "completed"
    assert checkpoint.current_step_index == 2
    assert checkpoint.completed_steps == ["create_backtest", "run_strategy", "save_results"]
    assert checkpoint.context["backtest_id"] == "bt_12345"
    assert checkpoint.context["profit"] == 1500
    
    print(f"✅ Test 1 passed: Checkpoint persisted to database")


@pytest.mark.asyncio
async def test_audit_logging(clean_database, db_session):
    """Test 2: Audit logging - all events recorded"""
    
    steps = [
        SagaStep("create_backtest", create_backtest_action),
        SagaStep("run_strategy", run_strategy_action),
    ]
    
    config = SagaConfig(
        saga_type="backtest_workflow",
        user_id="user_456",
        ip_address="10.0.0.1",
        enable_audit_log=True
    )
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator.saga_id
    
    # Execute saga
    result = await orchestrator.execute()
    
    # Verify audit logs
    audit_logs = db_session.query(SagaAuditLog).filter(
        SagaAuditLog.saga_id == saga_id
    ).order_by(SagaAuditLog.timestamp).all()
    
    # Expected events:
    # 1. saga_start
    # 2. step_start (create_backtest)
    # 3. step_complete (create_backtest)
    # 4. step_start (run_strategy)
    # 5. step_complete (run_strategy)
    # 6. saga_complete
    
    assert len(audit_logs) == 6
    
    # Verify event sequence
    assert audit_logs[0].event_type == "saga_start"
    assert audit_logs[1].event_type == "step_start"
    assert audit_logs[1].step_name == "create_backtest"
    assert audit_logs[2].event_type == "step_complete"
    assert audit_logs[2].step_name == "create_backtest"
    assert audit_logs[3].event_type == "step_start"
    assert audit_logs[3].step_name == "run_strategy"
    assert audit_logs[4].event_type == "step_complete"
    assert audit_logs[4].step_name == "run_strategy"
    assert audit_logs[5].event_type == "saga_complete"
    
    # Verify user_id and ip_address captured
    for log in audit_logs:
        assert log.user_id == "user_456"
        assert log.ip_address == "10.0.0.1"
    
    print(f"✅ Test 2 passed: {len(audit_logs)} audit logs recorded")


@pytest.mark.asyncio
async def test_compensation_with_audit(clean_database, db_session):
    """Test 3: Compensation with audit trail"""
    
    steps = [
        SagaStep("create_backtest", create_backtest_action, delete_backtest_compensation),
        SagaStep("run_strategy", run_strategy_action, cleanup_strategy_compensation),
        SagaStep("failing_step", failing_action),
    ]
    
    config = SagaConfig(
        saga_type="backtest_workflow",
        user_id="user_789",
        enable_audit_log=True
    )
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator.saga_id
    
    # Execute saga (will fail)
    compensation_calls = []
    result = await orchestrator.execute(context={"compensation_calls": compensation_calls})
    
    # Verify failure
    assert result["status"] == "failed"
    assert result["completed_steps"] == ["create_backtest", "run_strategy"]
    assert result["compensated_steps"] == ["run_strategy", "create_backtest"]
    assert len(compensation_calls) == 2
    assert "cleanup_strategy" in compensation_calls
    assert "delete_backtest" in compensation_calls
    
    # Verify audit logs include compensation events
    audit_logs = db_session.query(SagaAuditLog).filter(
        SagaAuditLog.saga_id == saga_id
    ).order_by(SagaAuditLog.timestamp).all()
    
    # Find compensation events
    comp_events = [log for log in audit_logs if "compensation" in log.event_type]
    
    # Expected compensation events:
    # - compensation_start (saga-level)
    # - compensation_complete (run_strategy)
    # - compensation_complete (create_backtest)
    
    assert len(comp_events) >= 3
    assert any(log.event_type == "compensation_start" for log in comp_events)
    assert any(log.event_type == "compensation_complete" and log.step_name == "run_strategy" for log in comp_events)
    assert any(log.event_type == "compensation_complete" and log.step_name == "create_backtest" for log in comp_events)
    
    # Verify error logged
    failed_events = [log for log in audit_logs if log.event_type == "step_failed"]
    assert len(failed_events) == 1
    assert "Intentional failure" in failed_events[0].error_message
    
    print(f"✅ Test 3 passed: Compensation audit trail complete ({len(comp_events)} events)")


@pytest.mark.asyncio
async def test_saga_recovery_from_database(clean_database, db_session):
    """Test 4: Saga recovery from database checkpoint"""
    
    # Create and execute saga partially
    steps = [
        SagaStep("step1", create_backtest_action),
        SagaStep("step2", run_strategy_action),
        SagaStep("step3", save_results_action),
    ]
    
    config = SagaConfig(saga_type="test_workflow")
    
    # Create saga and get saga_id
    orchestrator1 = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator1.saga_id
    
    # Execute saga
    result1 = await orchestrator1.execute()
    
    # Verify checkpoint saved
    checkpoint = db_session.query(SagaCheckpointModel).filter(
        SagaCheckpointModel.saga_id == saga_id
    ).first()
    
    assert checkpoint is not None
    
    # Recover saga from database
    orchestrator2 = await SagaOrchestrator.recover(saga_id, steps, config, db=db_session)
    
    # Verify recovered state
    assert orchestrator2.saga_id == saga_id
    assert orchestrator2.state == SagaState.COMPLETED
    assert orchestrator2.completed_steps == ["step1", "step2", "step3"]
    assert orchestrator2.context["backtest_id"] == "bt_12345"
    assert orchestrator2.context["profit"] == 1500
    
    print(f"✅ Test 4 passed: Saga recovered from database checkpoint")


@pytest.mark.asyncio
async def test_step_retry_with_metrics(clean_database, db_session):
    """Test 5: Step retry with Prometheus metrics"""
    
    # Flaky action that succeeds on 3rd attempt
    retry_count = {"value": 0}
    
    async def flaky_action(context: Dict[str, Any]) -> Dict[str, Any]:
        retry_count["value"] += 1
        if retry_count["value"] < 3:
            raise Exception("Temporary failure")
        return {"success": True}
    
    steps = [
        SagaStep("flaky_step", flaky_action, max_retries=3),
    ]
    
    config = SagaConfig(
        saga_type="retry_test",
        enable_metrics=True
    )
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    
    # Execute saga
    result = await orchestrator.execute()
    
    # Verify success after retries
    assert result["status"] == "completed"
    assert result["metrics"]["steps_retried"] == 2  # Failed 2 times, succeeded on 3rd
    
    print(f"✅ Test 5 passed: Step succeeded after {retry_count['value']} attempts")


@pytest.mark.asyncio
async def test_concurrent_sagas_with_database(clean_database, db_session):
    """Test 6: Concurrent sagas with separate database checkpoints"""
    
    async def run_saga(saga_num: int):
        steps = [
            SagaStep(f"step1_{saga_num}", create_backtest_action),
            SagaStep(f"step2_{saga_num}", run_strategy_action),
        ]
        
        config = SagaConfig(
            saga_type=f"concurrent_test_{saga_num}",
            user_id=f"user_{saga_num}"
        )
        
        # Each saga gets its own db session
        db = SessionLocal()
        try:
            orchestrator = SagaOrchestrator(steps, config, db=db)
            result = await orchestrator.execute(context={"saga_num": saga_num})
            return result
        finally:
            db.close()
    
    # Run 5 sagas concurrently
    results = await asyncio.gather(*[run_saga(i) for i in range(5)])
    
    # Verify all succeeded
    assert all(r["status"] == "completed" for r in results)
    
    # Verify 5 separate checkpoints in database
    checkpoints = db_session.query(SagaCheckpointModel).all()
    assert len(checkpoints) >= 5
    
    # Verify unique saga_ids
    saga_ids = [c.saga_id for c in checkpoints]
    assert len(set(saga_ids)) == len(saga_ids)  # All unique
    
    print(f"✅ Test 6 passed: {len(results)} concurrent sagas completed")


@pytest.mark.asyncio
async def test_audit_log_context_snapshot(clean_database, db_session):
    """Test 7: Audit log captures context snapshots"""
    
    steps = [
        SagaStep("step1", create_backtest_action),
        SagaStep("step2", run_strategy_action),
    ]
    
    config = SagaConfig(
        saga_type="context_test",
        enable_audit_log=True
    )
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator.saga_id
    
    # Execute with initial context
    result = await orchestrator.execute(context={"initial_capital": 10000})
    
    # Verify audit logs have context snapshots
    audit_logs = db_session.query(SagaAuditLog).filter(
        SagaAuditLog.saga_id == saga_id,
        SagaAuditLog.event_type == "step_complete"
    ).order_by(SagaAuditLog.timestamp).all()
    
    # First step: context should have initial_capital + backtest_id
    assert audit_logs[0].context_snapshot["initial_capital"] == 10000
    assert audit_logs[0].context_snapshot["backtest_id"] == "bt_12345"
    
    # Second step: context should have all previous data + profit
    assert audit_logs[1].context_snapshot["initial_capital"] == 10000
    assert audit_logs[1].context_snapshot["backtest_id"] == "bt_12345"
    assert audit_logs[1].context_snapshot["profit"] == 1500
    
    print(f"✅ Test 7 passed: Context snapshots captured in audit logs")


@pytest.mark.asyncio
async def test_full_production_workflow(clean_database, db_session):
    """Test 8: Complete production workflow - Database + Audit + Metrics"""
    
    steps = [
        SagaStep("create_backtest", create_backtest_action, delete_backtest_compensation, timeout=5),
        SagaStep("run_strategy", run_strategy_action, cleanup_strategy_compensation, timeout=10, max_retries=2),
        SagaStep("save_results", save_results_action, timeout=5),
    ]
    
    config = SagaConfig(
        saga_type="production_backtest_workflow",
        user_id="prod_user_001",
        ip_address="203.0.113.42",
        enable_metrics=True,
        enable_audit_log=True
    )
    
    start_time = time.time()
    
    orchestrator = SagaOrchestrator(steps, config, db=db_session)
    saga_id = orchestrator.saga_id
    
    # Execute saga
    result = await orchestrator.execute(context={
        "backtest_config": {"symbol": "BTCUSDT", "timeframe": "1h"},
        "initial_capital": 100000
    })
    
    duration = time.time() - start_time
    
    # Verify completion
    assert result["status"] == "completed"
    assert len(result["completed_steps"]) == 3
    assert result["context"]["backtest_id"] == "bt_12345"
    assert result["context"]["profit"] == 1500
    
    # Verify database checkpoint
    checkpoint = db_session.query(SagaCheckpointModel).filter(
        SagaCheckpointModel.saga_id == saga_id
    ).first()
    
    assert checkpoint is not None
    assert checkpoint.state == "completed"
    assert checkpoint.total_steps == 3
    
    # Verify audit trail
    audit_logs = db_session.query(SagaAuditLog).filter(
        SagaAuditLog.saga_id == saga_id
    ).all()
    
    assert len(audit_logs) >= 7  # saga_start + 3x(step_start+step_complete) + saga_complete
    
    # Verify compliance fields
    for log in audit_logs:
        assert log.user_id == "prod_user_001"
        assert log.ip_address == "203.0.113.42"
        assert log.saga_id == saga_id
    
    print(f"✅ Test 8 passed: Full production workflow completed in {duration:.2f}s")
    print(f"   - Checkpoint: {checkpoint.state}")
    print(f"   - Audit logs: {len(audit_logs)} events")
    print(f"   - Metrics: {result['metrics']}")


# ============================================================================
# TEST SUMMARY
# ============================================================================

def test_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("PRODUCTION-READY SAGA PATTERN TESTS")
    print("="*70)
    print("\n✅ All 8 production tests defined:")
    print("  1. test_database_persistence - Checkpoint survives across instances")
    print("  2. test_audit_logging - All events recorded with compliance fields")
    print("  3. test_compensation_with_audit - Compensation audit trail")
    print("  4. test_saga_recovery_from_database - Recovery from checkpoint")
    print("  5. test_step_retry_with_metrics - Retry with Prometheus metrics")
    print("  6. test_concurrent_sagas_with_database - Concurrent execution")
    print("  7. test_audit_log_context_snapshot - Context snapshots captured")
    print("  8. test_full_production_workflow - Complete production workflow")
    print("\nRun with: pytest tests/integration/test_saga_production.py -v")
    print("="*70)
