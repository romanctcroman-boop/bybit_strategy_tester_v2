"""
Simple tests for horizontal scaling system
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from unittest.mock import Mock, MagicMock
import redis

# Mock Redis for testing
redis_mock = MagicMock()


def test_redis_consumer_group():
    """Test Redis consumer group"""
    print("\n" + "=" * 70)
    print("Testing Redis Consumer Group")
    print("=" * 70)
    
    from backend.scaling.redis_consumer_groups import RedisConsumerGroup
    
    # Create mock Redis
    mock_redis = Mock()
    mock_redis.xgroup_create = Mock(side_effect=redis.ResponseError("BUSYGROUP"))
    mock_redis.xadd = Mock(return_value=b"1-0")
    
    # Create consumer group
    consumer = RedisConsumerGroup(
        redis_client=mock_redis,
        stream_name="test_stream",
        group_name="test_group"
    )
    
    assert consumer.stream_name == "test_stream"
    assert consumer.group_name == "test_group"
    
    # Test add task
    task_id = consumer.add_task(
        task_type="backtest",
        task_data={"backtest_id": 123}
    )
    
    assert task_id is not None
    mock_redis.xadd.assert_called_once()
    
    print("✅ RedisConsumerGroup initialization works")
    print("✅ Task adding works")


def test_worker_health_monitor():
    """Test worker health monitoring"""
    print("\n" + "=" * 70)
    print("Testing Worker Health Monitor")
    print("=" * 70)
    
    from backend.scaling.dynamic_worker_scaling import WorkerHealthMonitor
    
    # Create mock Redis
    mock_redis = Mock()
    mock_redis.hset = Mock()
    mock_redis.setex = Mock()
    
    # Create monitor
    monitor = WorkerHealthMonitor(mock_redis)
    
    # Register worker
    monitor.register_worker(
        worker_id="worker1",
        metadata={"hostname": "localhost"}
    )
    
    mock_redis.hset.assert_called_once()
    
    # Update heartbeat
    monitor.update_heartbeat(
        worker_id="worker1",
        metrics={"tasks_processed": 10}
    )
    
    mock_redis.setex.assert_called_once()
    
    print("✅ Worker registration works")
    print("✅ Heartbeat update works")


def test_dynamic_worker_scaler():
    """Test dynamic worker scaling"""
    print("\n" + "=" * 70)
    print("Testing Dynamic Worker Scaler")
    print("=" * 70)
    
    from backend.scaling.dynamic_worker_scaling import (
        DynamicWorkerScaler,
        WorkerHealthMonitor,
        ScalingConfig
    )
    
    # Create mocks
    mock_redis = Mock()
    mock_redis.llen = Mock(return_value=150)  # High queue depth
    mock_redis.hgetall = Mock(return_value={})  # Empty workers for now
    
    monitor = WorkerHealthMonitor(mock_redis)
    
    config = ScalingConfig(
        min_workers=1,
        max_workers=10,
        target_queue_depth=100
    )
    
    scaler = DynamicWorkerScaler(
        redis_client=mock_redis,
        config=config,
        health_monitor=monitor
    )
    
    # Test scale up decision (with high queue depth)
    should_scale = scaler.should_scale_up(queue_depth=150, active_workers=2)
    assert should_scale is True
    
    # Test that scale_down needs more workers than min
    # (won't scale down with 1 active worker when min is 1)
    should_scale_down = scaler.should_scale_down(queue_depth=10, active_workers=1)
    assert should_scale_down is False
    
    print("✅ Scale up decision works")
    print("✅ Scale down decision works")


def test_load_balancer():
    """Test load balancer"""
    print("\n" + "=" * 70)
    print("Testing Load Balancer")
    print("=" * 70)
    
    from backend.scaling.load_balancer import LoadBalancer, LoadBalancingStrategy
    
    # Create mock Redis
    mock_redis = Mock()
    mock_redis.hset = Mock()
    
    # Create load balancer
    lb = LoadBalancer(
        redis_client=mock_redis,
        strategy=LoadBalancingStrategy.ROUND_ROBIN
    )
    
    # Register workers
    lb.register_worker("worker1", weight=1, max_concurrent_tasks=10)
    lb.register_worker("worker2", weight=1, max_concurrent_tasks=10)
    lb.register_worker("worker3", weight=1, max_concurrent_tasks=10)
    
    assert len(lb.workers) == 3
    
    # Test task assignment
    worker_id = lb.get_next_worker()
    assert worker_id is not None
    assert worker_id in ["worker1", "worker2", "worker3"]
    
    # Assign task
    assigned_worker = lb.assign_task("task123")
    assert assigned_worker in ["worker1", "worker2", "worker3"]
    
    # Check worker stats
    stats = lb.get_worker_stats()
    assert len(stats) == 3
    
    print("✅ Worker registration works")
    print("✅ Task assignment works")
    print("✅ Worker stats work")


def test_health_checks():
    """Test health check system"""
    print("\n" + "=" * 70)
    print("Testing Health Check System")
    print("=" * 70)
    
    from backend.scaling.health_checks import (
        HealthMonitor,
        HealthCheck,
        CircuitBreaker,
        HealthStatus
    )
    
    # Test circuit breaker
    circuit = CircuitBreaker(failure_threshold=3, timeout_seconds=5)
    
    # Test function
    call_count = [0]
    
    def test_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise Exception("Test failure")
        return True
    
    # Should fail first 2 times
    for i in range(2):
        try:
            circuit.call(test_func)
        except Exception:
            pass
    
    # Should succeed on 3rd time
    result = circuit.call(test_func)
    assert result is True
    
    print("✅ Circuit breaker works")
    
    # Test health monitor
    mock_redis = Mock()
    mock_redis.xadd = Mock()
    mock_redis.setex = Mock()
    
    monitor = HealthMonitor(mock_redis)
    
    # Register health check
    check_func = Mock(return_value=True)
    monitor.register_health_check(
        service_id="service1",
        check_func=check_func
    )
    
    assert "service1" in monitor.health_checks
    
    # Perform check
    result = monitor.check_service("service1")
    assert result is not None
    assert result.status == HealthStatus.HEALTHY
    
    print("✅ Health monitoring works")


def test_scaling_config():
    """Test scaling configuration"""
    print("\n" + "=" * 70)
    print("Testing Scaling Configuration")
    print("=" * 70)
    
    from backend.scaling.dynamic_worker_scaling import ScalingConfig
    
    config = ScalingConfig(
        min_workers=2,
        max_workers=20,
        target_queue_depth=100,
        cpu_threshold=75.0
    )
    
    assert config.min_workers == 2
    assert config.max_workers == 20
    assert config.target_queue_depth == 100
    assert config.cpu_threshold == 75.0
    
    print("✅ ScalingConfig initialization works")


def test_integration():
    """Test component integration"""
    print("\n" + "=" * 70)
    print("Testing Component Integration")
    print("=" * 70)
    
    from backend.scaling import (
        WorkerHealthMonitor,
        DynamicWorkerScaler,
        LoadBalancer,
        HealthMonitor,
        ScalingConfig
    )
    
    # Create mock Redis
    mock_redis = Mock()
    mock_redis.hset = Mock()
    mock_redis.setex = Mock()
    mock_redis.llen = Mock(return_value=50)
    mock_redis.xadd = Mock()
    
    # Create components
    health_monitor = WorkerHealthMonitor(mock_redis)
    config = ScalingConfig(min_workers=1, max_workers=5)
    scaler = DynamicWorkerScaler(mock_redis, config, health_monitor)
    load_balancer = LoadBalancer(mock_redis)
    health_service = HealthMonitor(mock_redis)
    
    # Register workers
    for i in range(3):
        worker_id = f"worker{i}"
        health_monitor.register_worker(worker_id)
        load_balancer.register_worker(worker_id)
    
    # Get stats (skip metrics that need real worker data)
    stats = load_balancer.get_worker_stats()
    assert len(stats) == 3  # We registered 3 workers
    
    print("✅ Component integration works")
    print("✅ All components initialized successfully")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("HORIZONTAL SCALING TESTS")
    print("=" * 70)
    
    try:
        test_redis_consumer_group()
        test_worker_health_monitor()
        test_dynamic_worker_scaler()
        test_load_balancer()
        test_health_checks()
        test_scaling_config()
        test_integration()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
